from alpaca.trading.client import TradingClient
import config

api = TradingClient(config.API_KEY, config.API_SECRET, paper=True)
