import json
import math
import random
import time

import requests
from alpaca.common import exceptions
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import (AssetClass, OrderSide, OrderStatus,
                                  TimeInForce)
from alpaca.trading.requests import (ClosePositionRequest, GetOrdersRequest,
                                     LimitOrderRequest, MarketOrderRequest)
from flask import Flask, abort, render_template, request

import app
import config
from components import vars
from components.api_alpaca import api

# Declaring some variables
accountInfo = api.get_account()
slippage = config.RISK_EXPOSURE + 1


# Check if our account is restricted from trading.
def tradingValid():
    if accountInfo.trading_blocked:
        return 'Error: Account is currently restricted from trading.'
    elif int(accountInfo.daytrade_count) > 3 and not config.DAYTRADE_ALLOW:
        return 'Error: Approaching Day Trade Limit'
    else:
        return True

    
def checkOpenOrder(ticker, side):
    orderParams = GetOrdersRequest(status='all', limit=20, nested=False, symbols=[ticker])
    orders = api.get_orders(filter=orderParams)
    canceled_orders = []
    
    if orders:  # Check if there are any orders
        for order in orders:
            if side == 'buy': #order.side == side and side == 'buy':
                # Skip canceling the old buy order
                continue
            elif order.status in [OrderStatus.CANCELED, OrderStatus.FILLED]:
                continue
            else:
                try:
                    api.cancel_order_by_id(order_id=order.id)
                    canceled_orders.append(order.id)
                except Exception as e:
                    print(f"Error canceling order {order.id}: {e}")
        
        counter = len(canceled_orders)
        response = f"Checked {counter} open order(s) for symbol {ticker}"
        print(response)
    else:
        response = f"No open orders found for symbol {ticker}"
        print(response)
    
    return canceled_orders

    

def checkAssetClass(ticker):
    asset = api.get_asset(ticker)
    if asset.tradable:
        return asset.asset_class
    else:
        return None


def calcQuantity(price):
    if config.MARGIN_ALLOW == True:
        buyingPower = float(accountInfo.daytrading_buying_power)
    else:    
        buyingPower = float(accountInfo.non_marginable_buying_power)
    quantity = (buyingPower * config.RISK_EXPOSURE) / price  # Position Size Based on Risk Exposure
    return quantity


def calcRR(price):
    stopLoss = round((((0.1*config.RISK) * price) - price)*-1, 2)
    takeProfit = round((((0.1*config.RISK)*config.REWARD) * price) + price, 2)
    return stopLoss, takeProfit
    
# ============================== Execution Logic =================================
def executeOrder(webhook_message):
    symbol_WH,side_WH,price_WH,quantity_WH,comment_WH,orderID_WH = vars.webhook(webhook_message)
    
    if not tradingValid():
        return "Trade not valid"
    
    checkOpenOrder(symbol_WH, side_WH)
      
    if side_WH == 'buy':
        result = executeBuyOrder(symbol_WH, price_WH)
    elif side_WH == 'sell':
            result = executeSellOrder(symbol_WH, orderID_WH)
            #if orderID_WH != 'Tp':
            #    time.sleep(3)
    else:
        result = "Invalid order side"
    return result
    
def executeBuyOrder(symbol, price):
    checkCrypto = checkAssetClass(symbol)
    slippage_price = price * slippage
    quantity = calcQuantity(slippage_price)
    client_order_id = f"skybot1_{random.randrange(100000000)}"
    if checkCrypto == AssetClass.CRYPTO:
        if float(accountInfo.non_marginable_buying_power)*0.3 > 30000:
            qtyrsk = (50000*0.26)/price
        else:
            qtyrsk = ((float(accountInfo.daytrading_buying_power)/2)*0.26)/price
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=quantity*1.1,
            side='buy',
            time_in_force='gtc',
            client_order_id=client_order_id
        )
        response = f"Market Order, buy: {symbol}. {quantity} shares, 'gtc'."
    else:
        stopLoss, takeProfit = calcRR(price)
        take_profit = {"limit_price": takeProfit}
        stop_loss = {"stop_price": stopLoss}
        orderData = LimitOrderRequest(
            symbol=symbol,
            qty=round(quantity),
            side='buy',
            type='limit',
            time_in_force='gtc',
            limit_price=round(slippage_price,2),
            order_class='bracket',
            take_profit=take_profit,
            stop_loss=stop_loss,
            client_order_id=client_order_id
        )
        response = f"Limit Order, buy: {symbol} @ {slippage_price}. {round(quantity)} shares, 'gtc'."
    
    print(response)
    return api.submit_order(orderData)

def executeSellOrder(symbol, orderID):
    if orderID == 'Tp':
        close_options = ClosePositionRequest(percentage=config.TAKEPROFIT_POSITION*100) 
        return api.close_position(symbol, close_options=close_options)
    else:
        return api.close_position(symbol)


