from flask import Flask, render_template, request, abort, jsonify
from alpaca.trading import MarketOrderRequest, LimitOrderRequest, ClosePositionRequest, GetOrdersRequest, OrderSide, TimeInForce, AssetClass
from alpaca.trading.client import TradingClient
from alpaca.common import exceptions
import config, json, requests, math, random, app, ast, re
import components.techanalysis.ta_indicators as ta
from threading import Lock
from alpaca.data import StockBarsRequest, TimeFrame, TimeFrameUnit, StockHistoricalDataClient, BaseBarsRequest
from datetime import datetime, timedelta
from tradingview_screener import Scanner, Query, Column


start_date = datetime(2022, 6, 1)
end_date = datetime.today() - timedelta(minutes=15)
window_size = 3

# Testing trading view module
q = Query().select('name', 'close', 'volume', 'relative_volume_10d_calc')\
    .where(
        Column('market_cap_basic').between(1_000_000, 50_000_000), 
        Column('relative_volume_10d_calc') > 1.2, 
        Column('MACD.macd') >= 'MACD.signal'
    )\
    .order_by('volume', ascending=False)
df = q.get_scanner_data()





def test():
    dataset = BarDataset("SPY",window_size)
    dataset.organize_bars()
    data = dataset.get_data()
    print(df)
    return data



class BarDataset:
    def __init__(self, ticker,candles):
        self.api = StockHistoricalDataClient(config.API_KEY, config.API_SECRET)
        # 15min lag for free subscriptions
        self.params = BaseBarsRequest(
            symbol_or_symbols=ticker,
            start=start_date,
            #end=end_date,
            limit=candles,
            timeframe=TimeFrame(1,TimeFrameUnit.Day)
            )
        self.data = {}
    
    def add_bar(self, bar):
        symbol = bar["symbol"]
        if symbol not in self.data:
            self.data[symbol] = []
        self.data[symbol].append(bar)
    
    def clean_bars(self, payload):
        payload = str(payload)
        payload = payload.replace("data=", "").strip()
        payload = payload.replace(", tzinfo=datetime.timezone.utc", "").strip()
        # Remove the newline characters and replace single quotes with double quotes
        payload = payload.replace("\n", "").replace("'", '"')
        # Identify datetime strings and convert them to ISO 8601 format
        payload = re.sub(r"datetime\.datetime\((.*?)\)", r'"\1"', payload)
        # Convert the cleaned payload to a dictionary
        payload_dict = ast.literal_eval(payload)
        json_str = json.dumps(payload_dict)
        return payload_dict

    def organize_bars(self):
        bars = self.api.get_stock_bars(self.params)
        cleaned_payload = self.clean_bars(bars)
        for symbol, bars in cleaned_payload.items():
            for bar in bars:
                timestamp_str = bar['timestamp']
                timestamp = datetime.strptime(timestamp_str, "%Y, %m, %d, %H, %M")
                bar['timestamp'] = timestamp.strftime("%Y-%m-%dT%H:%M:%S")
                self.add_bar(bar)


    def get_data(self):
        return list(self.data.values())
    



