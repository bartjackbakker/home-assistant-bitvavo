"""Constants for the Bitvavo integration."""
from datetime import timedelta

DOMAIN = "bitvavo"

# Config
CONF_API_SECRET = "api_secret"

CONF_BALANCES = "balances"
CONF_MARKETS = "markets"
CONF_OPEN_ORDERS = "open_orders"
CONF_TICKERS = "tickers"
CONF_ASSET_TICKERS = "asset_tickers"
CONF_SHOW_EMPTY_ASSETS = "show_empty_assets"

PLATFORMS = ["sensor"]

# Currency
CURRENCY_ICONS = {
    "BTC": "mdi:currency-btc",
    "ETH": "mdi:currency-eth",
    "EUR": "mdi:currency-eur",
    "LTC": "mdi:litecoin",
    "USDC": "mdi:currency-usd",
}

DEFAULT_COIN_ICON = "mdi:currency-usd"

ASSET_VALUE_CURRENCIES = {"USDC", "EUR", "BTC"}
ASSET_VALUE_BASE = "EUR"
ATTRIBUTION = "Bitvavo.com"

# Setup
SCAN_INTERVAL = timedelta(seconds=20)
