from components.Clients.Alpaca.api_alpaca import api
from components.Clients.Alpaca import DataAnalysis as da
from components.Clients.Alpaca.price_data import get_ohlc_alpaca


df = da.collectOrders()
symbols = df['symbols'].unique()
portfolio = get_ohlc_alpaca(symbols,int(365))