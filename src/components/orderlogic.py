from flask import Flask, render_template, request, abort
#import alpaca_trade_api as tradeapi
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, ClosePositionRequest, GetOrdersRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass
from alpaca.common import exceptions
import app
import config, json, requests, math, random
from components import vars
from threading import Lock

# Declaring some variables
api = TradingClient(config.API_KEY, config.API_SECRET, paper=True)
accountInfo = api.get_account()
slippage = config.RISK_EXPOSURE + 1
order_lock = Lock()


# Check if our account is restricted from trading.
def tradingValid():
    if accountInfo.trading_blocked:
        response = 'Error: Account is currently restricted from trading.'
        print(response)
        return response
    elif (int(accountInfo.daytrade_count) > 3) and config.DAYTRADE_ALLOW == False: # Check if were approaching PDT limit
        response = 'Error: Approaching Day Trade Limit'
        print(response)
        return response
    else:
        return True
    
def checkOpenOrder(ticker, side):
    opposite_side = 'sell' if side == 'buy' else 'buy'

    orderParams = GetOrdersRequest(status='open', limit=5, nested=True, symbols=[ticker])
    orders = api.get_orders(filter=orderParams)

    for order in orders:
        if order.side == opposite_side:
            api.cancel_order_by_id(order_id=order.id)
            response = f"Replaced open {opposite_side} order for symbol {ticker}"
            print(response)

    return

def checkAssetClass(ticker):
    assest = api.get_asset(ticker)
    if assest.tradable:
        print(f'{ticker} is a {assest.asset_class} asset.')
        return assest.asset_class
    else:
        print(f'{ticker} is not tradable')

def calcQuantity(price):
    cashAvailable = float(accountInfo.non_marginable_buying_power)
    quantity = (cashAvailable * config.RISK_EXPOSURE) / price  # Position Size Based on Risk Exposure
    return quantity




# ============================== Execution Logic =================================
def executeOrder(webhook_message):
    symbol_WH, side_WH, price_WH, qty_WH, comment_WH, orderID_WH = vars.webhook(webhook_message)
    
    if not tradingValid():
        return "Trade not valid"

    order_lock.acquire()
    try:
        checkOpenOrder(symbol_WH,side_WH)
        
        if side_WH == 'buy':
            result = executeBuyOrder(symbol_WH, price_WH)
        elif side_WH == 'sell':
            result = executeSellOrder(symbol_WH, orderID_WH)
        else:
            result = "Invalid order side"
    finally:
        order_lock.release()

    return result
    
def executeBuyOrder(symbol, price):
    quantity = calcQuantity(price)
    client_order_id=f"skybot1_{random.randrange(100000000)}"
    if checkAssetClass(symbol) == AssetClass.CRYPTO:
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side='buy',
            time_in_force='gtc',
            client_order_id=client_order_id
        )
        response = f"Market Order, buy: {symbol}. {quantity} shares, 'gtc'."
    else:
        take_profit = {"limit_price": price * config.REWARD}
        stop_loss = {"stop_price": price * config.BREAKEVEN}
        orderData = LimitOrderRequest(
            symbol=symbol,
            qty=round(quantity),
            side='buy',
            type='limit',
            time_in_force='gtc',
            limit_price=price,
            order_class='bracket',
            take_profit=take_profit,
            stop_loss=stop_loss,
            client_order_id=client_order_id
        )
        response = f"Limit Order, buy: {symbol} @ {price}. {round(quantity)} shares, 'gtc'."
    
    print(response)
    return api.submit_order(orderData)

def executeSellOrder(symbol, orderID):
    if orderID == 'TP':
        close_options = ClosePositionRequest(percentage=config.TAKEPROFIT_POSITION)
        return api.close_position(symbol, close_options=close_options)
    else:
        return api.close_position(symbol)


