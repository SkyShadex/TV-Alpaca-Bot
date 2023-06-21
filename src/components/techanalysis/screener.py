from flask import Flask, render_template, request, abort, jsonify
from alpaca.trading import MarketOrderRequest, LimitOrderRequest, ClosePositionRequest, GetOrdersRequest, OrderSide, TimeInForce, AssetClass
from alpaca.trading.client import TradingClient
from alpaca.common import exceptions
import config, json, requests, math, random, app, ast, re
import components.techanalysis.ta_indicators as ta
from threading import Lock
from alpaca.data import StockBarsRequest, TimeFrame, TimeFrameUnit, StockHistoricalDataClient, BaseBarsRequest
from datetime import datetime

api = StockHistoricalDataClient(config.API_KEY, config.API_SECRET)
start_date = datetime(2022, 6, 1)
end_date= datetime(2023, 1, 1)
window_size = 150
params = BaseBarsRequest(symbol_or_symbols="SPY", start=start_date, end=end_date, limit=window_size*2, timeframe=TimeFrame(1,TimeFrameUnit.Day))




def test():
    bars = api.get_stock_bars(params)

    dataset = BarDataset()
    dataset.organize_bars(dataset.clean_bars(bars))
    data = dataset.get_data()
    sma = ta.calculate_sma(data[0], window_size=window_size, parameter_index='close')  # Calculate SMA for the first parameter
    print(sma)
    return data



class BarDataset:
    def __init__(self):
        self.data = {}
    
    def add_bar(self, bar):
        symbol = bar["symbol"]
        if symbol not in self.data:
            self.data[symbol] = []
        self.data[symbol].append(bar)
    
    def clean_bars(self, payload):
        payload = str(payload)
        # Clean the payload string
        payload = payload.replace("data=", "").strip()
        # Replace datetime objects with their string representations
        payload = re.sub(r"datetime.datetime\(([^)]*)\)", r'"\1"', payload)
        # Convert the cleaned payload to a dictionary
        payload_dict = ast.literal_eval(payload)
        # Convert the dictionary to a JSON string
        json_str = json.dumps(payload_dict)
        return payload_dict
    
    def organize_bars(self, payload):
        cleaned_payload = self.clean_bars(payload)
        for symbol, bars in cleaned_payload.items():
            for bar in bars:
                self.add_bar(bar)

    def get_data(self):
        #return self.data
        return list(self.data.values())