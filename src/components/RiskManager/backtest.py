from flask import Flask, render_template, request, abort
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, ClosePositionRequest, GetOrdersRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass, OrderStatus
from alpaca.common import exceptions
import app
import config, json, requests, math, random, time
from components import vars
from components.api_alpaca import api
import pandas as pd


def collectOrders():
    orderParams = GetOrdersRequest(status='closed', limit=500, nested=False)
    orders = api.get_orders(filter=orderParams)
    
    df_data = [vars.extract_order_response(order) for order in orders if order.status.value == 'filled']
    df = pd.DataFrame(df_data)
    print(df)
    df.to_csv('logs/orders.csv', index=False)
    