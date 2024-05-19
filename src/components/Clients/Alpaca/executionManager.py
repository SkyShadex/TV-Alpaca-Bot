import random
import datetime
import pytz
import math
from alpaca.trading.enums import (AssetClass, OrderStatus)
from alpaca.trading.requests import (ClosePositionRequest, GetOrdersRequest,
                                     LimitOrderRequest, MarketOrderRequest)

import config
from commons import vars
from components.Clients.Alpaca.api_alpaca import api
import logging


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
    orderParams = GetOrdersRequest(status='open', limit=20, nested=False, symbols=[ticker])  # type: ignore
    orders = api.get_orders(filter=orderParams)
    canceled_orders = []    
    if orders:  # Check if there are any orders
        for order in orders:
            if side == 'buy' or order.status in [OrderStatus.CANCELED, OrderStatus.FILLED]: #order.side == side and side == 'buy':  # type: ignore
                continue
            else:
                try:
                    api.cancel_order_by_id(order_id=order.id)  # type: ignore
                    canceled_orders.append(order.id)  # type: ignore
                except Exception as e:
                    print(f"Error canceling order {order.id}: {e}")  # type: ignore
        
        # counter = len(canceled_orders)
    return canceled_orders

def checkAssetClass(ticker):
    asset = api.get_asset(ticker)
    if asset.tradable: # type: ignore
        return asset.asset_class  # type: ignore
    else:
        return None

def calcQuantity(ticker,price,weight=1.0): 
    accountInfo = api.get_account()   
    if config.MARGIN_ALLOW == True:
        buyingPower = float(accountInfo.regt_buying_power)  # type: ignore
    else:    
        buyingPower = float(accountInfo.non_marginable_buying_power)  # type: ignore
 
    quantity = max((buyingPower * config.RISK_EXPOSURE * weight),1) / price  # Position Size Based on Risk Exposure  

    if quantity == 0.0:
        return 1.0
    
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
        result = entryOrder(symbol_WH,price_WH,orderID_WH)
    elif side_WH == 'sell':
        result = exitOrder(symbol_WH,orderID=orderID_WH)
    else:
        result = "Invalid order side"
    return result
    
def entryOrder(symbol,price,orderID,side='buy',isMarketOrder=False,weight=1.0):
    if price == 0:
        print(f'price error: {symbol},{price},{side},{orderID}')
        return
    checkCrypto = checkAssetClass(symbol)
    slippage_price = price * slippage
    quantity = calcQuantity(symbol,slippage_price,weight)
    client_order_id = f"skybot1_{orderID}{random.randrange(100000000)}"
    tif = 'day'
    if checkCrypto == AssetClass.CRYPTO:
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=round(quantity,2),
            side=side,
            time_in_force=tif,
            client_order_id=client_order_id
        )
        # else:
        #     orderData = LimitOrderRequest(
        #             symbol=symbol,
        #             qty=quantity,
        #             side=side,
        #             type='limit',
        #             time_in_force='day',
        #             limit_price=round(slippage_price,2),
        #             client_order_id=client_order_id
        #         )
        response = f"Market Order, {side}: {symbol}. {quantity:.2f} shares, {tif}."
    else:
        if side == 'sell':
            quantity = max(int(quantity),1)
        else:
            quantity = round(quantity,9)
        extCheck = extendedHoursCheck()
        stopLoss, takeProfit = calcRR(price)
        take_profit = {"limit_price": takeProfit}
        stop_loss = {"stop_price": stopLoss}
        tif = 'day'
        if config.EXTENDTRADE_ALLOW and extCheck: 
            if not isMarketOrder: 
                orderData = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    type='limit',
                    time_in_force=tif,
                    limit_price=round(slippage_price,2),
                    extended_hours=str(extCheck),
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    client_order_id=client_order_id
                )
            else:    
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=tif,
                    extended_hours=str(extCheck),
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id
                )
        else:
            if not isMarketOrder: 
                orderData = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    type='limit',
                    time_in_force=tif,
                    limit_price=round(slippage_price,2),
                    # order_class='bracket',
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id
                )
            else:    
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=tif,
                    # order_class='bracket',
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id
                )   
        response = f"Order {side}: {symbol} @ {slippage_price}. {quantity:.2f} shares, {tif}."
    
    print(response)
    logging.info(f"{entryOrder.__name__} {response}")
    res = api.submit_order(orderData)
    return res

def exitOrder(symbol,client=api.client['DEV'], orderID="",live=False):
    # if 'tp' in orderID and False:
    #     close_options = ClosePositionRequest(percentage=config.TAKEPROFIT_POSITION*100)
    #     return api.close_position(symbol, close_options=close_options)
    # else:
    res = client.close_position(symbol)
    return res

def optionsOrder(symbol,price,client=api.client['DEV'],orderID="",side='buy',quantity=1,isMarketOrder=False,weight=1.0,tif='day',bet=100.0,vol_limit=5):
    if isMarketOrder:
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=side,
            time_in_force=tif,
        )
    else:
        qty = quantity
        if side != 'sell': 
            portfolio_Corrected = bet * weight
            qty = min(max(math.floor(portfolio_Corrected / (100 * price)),1),vol_limit)  

        orderData = LimitOrderRequest(
                        symbol=symbol,
                        qty=qty,
                        side=side,
                        type='limit',
                        time_in_force=tif,
                        limit_price=round(price,2)
                    ) 
    response = f"Order {side}: {orderID} @ {price:.3f}. {qty:.2f} contracts, '{tif}'."    
    print(response)
    logging.info(f"{optionsOrder.__name__} {response}")
    return client.submit_order(orderData)

# //--------------------- PROD ENV ---------------------------------//

def entryOrderProd(symbol,price,orderID,side='buy',isMarketOrder=False,weight=1.0):
    client = api.client['LIVE']
    if price == 0:
        print(f'[PROD]: price error: {symbol},{price},{side},{orderID}')
        return
    
    asset = client.get_asset(symbol)

    if not asset:
        print(f'[PROD]: DNE: {symbol},{price},{side},{orderID}')
        return
    
    if not asset.tradable:
        return
    
    acct_info_prod = client.get_account() 
    buyingpower = max(float(acct_info_prod.regt_buying_power)-500,1) # In order to keep a cash balance
    quantity = max((buyingpower * config.RISK_EXPOSURE * weight),1.1) / price

    if quantity == 0.0:
        quantity = 1.0 

    client_order_id = f"skybot1_prod{orderID}{random.randrange(100000000)}"
    if asset.asset_class == AssetClass.CRYPTO:
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=round(quantity,2),
            side=side,
            time_in_force='day',
            client_order_id=client_order_id
        )
        response = f"Market Order, {side}: {symbol}. {quantity} shares."
    else:
        if side == 'sell':
            quantity = max(int(quantity),1)
        else:
            quantity = round(quantity,9)

        extCheck = extendedHoursCheck()
        tif = 'day'
        if config.EXTENDTRADE_ALLOW and extCheck:    
            orderData = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=tif,
                extended_hours=str(extCheck),
                client_order_id=client_order_id
            )
        else:   
            orderData = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=tif,
                client_order_id=client_order_id
            )   
        response = f"[PROD]: Order {side}: {symbol} @ {price}. {quantity:.2f} shares, {tif}."
    print(response)
    logging.info(f"{entryOrderProd.__name__} {response}")
    res = client.submit_order(orderData)
    return res
