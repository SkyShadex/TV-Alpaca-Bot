import random
import datetime
import pytz

from alpaca.trading.enums import (AssetClass, OrderStatus)
from alpaca.trading.requests import (ClosePositionRequest, GetOrdersRequest,
                                     LimitOrderRequest, MarketOrderRequest)

import config
from commons import vars
from components.Clients.Alpaca.api_alpaca import api

# Declaring some variables
accountInfo = api.get_account()
slippage = 1-(config.SLIPPAGE/100)

# Check if our account is restricted from trading.
def tradingValid():
    if accountInfo.trading_blocked:  # type: ignore
        return 'Error: Account is currently restricted from trading.'
    elif int(accountInfo.daytrade_count) > 3 and not config.DAYTRADE_ALLOW:  # type: ignore
        return 'Error: Approaching Day Trade Limit'
    else:
        return True

    
def checkOpenOrder(ticker, side):
    orderParams = GetOrdersRequest(status='all', limit=20, nested=False, symbols=[ticker])  # type: ignore
    orders = api.get_orders(filter=orderParams)
    canceled_orders = []
    
    if orders:  # Check if there are any orders
        for order in orders:
            if side == 'buy' or order.status in [OrderStatus.CANCELED, OrderStatus.FILLED]: #order.side == side and side == 'buy':  # type: ignore
                # Skip canceling the old buy order
                continue
            else:
                try:
                    api.cancel_order_by_id(order_id=order.id)  # type: ignore
                    canceled_orders.append(order.id)  # type: ignore
                except Exception as e:
                    print(f"Error canceling order {order.id}: {e}")  # type: ignore
        
        counter = len(canceled_orders)
        #response = f"Checked {counter} open order(s) for symbol {ticker}"
        #print(response)
    #else:
        #response = f"No open orders found for symbol {ticker}"
        #print(response)
    
    return canceled_orders

def checkAssetClass(ticker):
    asset = api.get_asset(ticker)
    if asset.tradable: # type: ignore
        return asset.asset_class  # type: ignore
    else:
        return None

def calcQuantity(price):    
    if config.MARGIN_ALLOW == True:
        buyingPower = float(accountInfo.regt_buying_power)  # type: ignore
        #buyingPower = float(accountInfo.daytrading_buying_power)
    else:    
        buyingPower = float(accountInfo.non_marginable_buying_power)  # type: ignore
        
    if float(accountInfo.long_market_value) < float(accountInfo.cash):     # type: ignore
        quantity = (buyingPower * config.RISK_EXPOSURE) / price  # Position Size Based on Risk Exposure
    # else:
    #     quantity = (buyingPower * (config.RISK_EXPOSURE*0.5)) / price  # Position Size Based on Risk Exposure
        
    return quantity

def calcRR(price):
    stopLoss = round((((0.1*config.RISK) * price) - price)*-1, 2)
    takeProfit = round((((0.1*config.RISK)*config.REWARD) * price) + price, 2)
    return stopLoss, takeProfit

def extendedHoursCheck():
    current_time = datetime.datetime.now().astimezone(pytz.timezone('US/Eastern'))
    trading_hours_start = current_time.replace(hour=9, minute=30, second=0, microsecond=0)
    trading_hours_end = current_time.replace(hour=16, minute=0, second=0, microsecond=0)

    if current_time < trading_hours_start or current_time >= trading_hours_end:
        return True
    else:
        return False

    
# ============================== Execution Logic =================================
def executeOrder(webhook_message):
    symbol_WH,side_WH,price_WH,quantity_WH,comment_WH,orderID_WH = vars.webhook(webhook_message)
    
    checkOpenOrder(symbol_WH, side_WH)
      
    if side_WH == 'buy':
        result = executeBuyOrder(symbol_WH, price_WH,orderID_WH)
    elif side_WH == 'sell':
            result = executeSellOrder(symbol_WH, orderID_WH)
    else:
        result = "Invalid order side"
    return result
    
def executeBuyOrder(symbol, price,orderID):
    isMarketOrder = False
    checkCrypto = checkAssetClass(symbol)
    slippage_price = price * slippage
    quantity = calcQuantity(slippage_price)
    client_order_id = f"skybot1_{orderID}{random.randrange(100000000)}"
    if checkCrypto == AssetClass.CRYPTO:
        if True:
            orderData = MarketOrderRequest(
                symbol=symbol,
                qty=round(quantity,2),
                side='buy',
                time_in_force='gtc',
                client_order_id=client_order_id
            )
        else:
            orderData = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side='buy',
                    type='limit',
                    time_in_force='day',
                    limit_price=round(slippage_price,2),
                    client_order_id=client_order_id
                )
        response = f"Market Order, buy: {symbol}. {quantity} shares, 'gtc'."
    else:
        extCheck = extendedHoursCheck()
        stopLoss, takeProfit = calcRR(price)
        take_profit = {"limit_price": takeProfit}
        stop_loss = {"stop_price": stopLoss}
        # if quantity == 0:
        #     quantity = 1
        if config.EXTENDTRADE_ALLOW and extCheck: 
            print('Extended Hours!')
            if not isMarketOrder: 
                orderData = LimitOrderRequest(
                    symbol=symbol,
                    qty=round(quantity,9),
                    side='buy',
                    type='limit',
                    time_in_force='day',
                    limit_price=round(slippage_price,2),
                    extended_hours=str(extCheck),
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    client_order_id=client_order_id
                )
            else:    
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=round(quantity,9),
                    side='buy',
                    time_in_force='day',
                    extended_hours=str(extCheck),
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id
                )
        else:
            if not isMarketOrder: 
                orderData = LimitOrderRequest(
                    symbol=symbol,
                    qty=round(quantity,9),
                    side='buy',
                    type='limit',
                    time_in_force='day',
                    limit_price=round(slippage_price,2),
                    # order_class='bracket',
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id
                )
            else:    
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=round(quantity,9),
                    side='buy',
                    time_in_force='day',
                    # order_class='bracket',
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id
                )   
        response = f"Limit Order, buy: {symbol} @ {slippage_price}. {round(quantity)} shares, 'gtc'."
    
    print(response)
    return api.submit_order(orderData)

def executeSellOrder(symbol, orderID):
    if 'tp' in orderID and False:
        close_options = ClosePositionRequest(percentage=config.TAKEPROFIT_POSITION*100)
        return api.close_position(symbol, close_options=close_options)
    else:
        return api.close_position(symbol)


