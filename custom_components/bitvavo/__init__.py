"""Gather the market details from Bitvavo."""
from __future__ import annotations

import logging
import asyncio

from bitvavo.BitvavoClient import BitvavoClient
from bitvavo.BitvavoExceptions import BitvavoException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ASSET_VALUE_BASE,
    ASSET_VALUE_CURRENCIES,
    CONF_API_SECRET,
    CONF_MARKETS,
    CONF_SHOW_EMPTY_ASSETS,
    DOMAIN,
    PLATFORMS,
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Bitvavo from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    markets = entry.data[CONF_MARKETS]
    show_empty_assets = entry.options.get(CONF_SHOW_EMPTY_ASSETS, True)
    loop = asyncio.get_event_loop()

    try:
        client = await loop.run_in_executor(None, BitvavoClient,api_key, api_secret)
    except BitvavoException as error:
        _LOGGER.error("Bitvavo API error: %s", error)
        raise ConfigEntryNotReady from error

    coordinator = BitvavoDataUpdateCoordinator(hass, client, show_empty_assets, markets)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Bitvavo config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok


class BitvavoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to get the latest data from Bitvavo."""

    def __init__(
        self, hass, client, show_empty_assets, markets, balances: list | None = None
    ):
        """Initialize the data object."""
        self._client = client
        self._show_empty_assets = show_empty_assets
        self._markets = markets

        self.asset_currencies = ASSET_VALUE_CURRENCIES

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    @staticmethod
    def _prep_markets(marketscfg, markets, tickers, orderbook_tickers):
        """Prepare markets data."""

        tickers_dict = {}

        for market in marketscfg:
            if market not in tickers_dict:
                tickers_dict[market] = {}
                ticker_details = next(
                    item for item in tickers if item["market"] == market
                )
                market_details = next(
                    item for item in markets if item["market"] == market
                )
                orderbook_ticker_details = next(
                    item for item in orderbook_tickers if item["market"] == market
                )
                combined_details_dict = {
                    **ticker_details,
                    **market_details,
                    **orderbook_ticker_details,
                }
                tickers_dict[market].update(combined_details_dict)

        return tickers_dict

    @staticmethod
    def _prep_tickers(asset_currencies, tickers):
        """Prepare tickers data."""

        asset_tickers_dict = {}

        for asset in asset_currencies:
            # Skip the ASSET_VALUE_BASE as we calculate it differently
            if asset != ASSET_VALUE_BASE:
                currency = f"{asset}-{ASSET_VALUE_BASE}"

                if currency not in asset_tickers_dict:
                    asset_tickers_dict[currency] = {}
                    ticker_details = next(
                        item for item in tickers if item["market"] == currency
                    )
                    asset_tickers_dict[currency].update(ticker_details)

        return asset_tickers_dict

    @staticmethod
    def _prep_balances(balances, tickers, show_empty_assets):
        """Prepare balances data."""

        balances_dict = {}

        for balance in balances:
            if balance["symbol"] not in balances_dict:
                total_balance = float(balance["available"]) + float(balance["inOrder"])

                if not show_empty_assets:
                    if total_balance == 0.0:
                        continue

                balances_dict[balance["symbol"]] = {}
                balances_dict[balance["symbol"]].update(balance)
                base_asset_ticker_details = None

                if ASSET_VALUE_BASE not in balance["symbol"]:
                    # Prevent that we try to search ASSET_VALUE_BASE+ASSET_VALUE_BASE (e.g. BTCBTC)
                    base_asset_symbol = str(balance["symbol"] + "-" + ASSET_VALUE_BASE)
                    try:
                        base_asset_ticker_details = next(
                            item
                            for item in tickers
                            if item["market"] == base_asset_symbol
                        )
                    except StopIteration:
                        continue
                else:
                    balances_dict[balance["symbol"]][
                        "asset_value_in_base_asset"
                    ] = total_balance

                if base_asset_ticker_details:
                    # If we can find a pair with ASSET_VALUE_BASE, include it in the dict
                    balances_dict[balance["symbol"]][ASSET_VALUE_BASE] = {}
                    balances_dict[balance["symbol"]][ASSET_VALUE_BASE].update(
                        base_asset_ticker_details
                    )
                    balances_dict[balance["symbol"]][
                        "asset_value_in_base_asset"
                    ] = total_balance * float(base_asset_ticker_details["price"])

        return balances_dict

    @staticmethod
    def _prep_total_base_asset(balances):
        """Prepare total base asset value data."""

        total_base_asset_value = 0.0

        for balance in balances:
            try:
                asset_value = balances[balance]["asset_value_in_base_asset"]

                total_base_asset_value += float(asset_value)
            except KeyError:
                continue

        return total_base_asset_value

    async def _async_update_data(self):
        """Fetch Bitvavo data."""
        tickers = await self._client.get_price_ticker()
        orderbook_tickers = await self._client.get_best_orderbook_ticker()
        markets = await self._client.get_markets()
        balances = await self._client.get_balance()
        open_orders = await self._client.get_open_orders()

        result_dict = {
            "tickers": self._prep_markets(
                self._markets, tickers, markets, orderbook_tickers
            )
        }

        result_dict["asset_tickers"] = self._prep_tickers(
            self.asset_currencies, tickers
        )

        result_dict["balances"] = self._prep_balances(
            balances, tickers, self._show_empty_assets
        )

        result_dict["total_base_asset"] = self._prep_total_base_asset(
            result_dict["balances"]
        )

        if open_orders:
            result_dict["open_orders"] = open_orders
        else:
            result_dict["open_orders"] = []

        return result_dict
