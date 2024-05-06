from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest
from alpaca.trading.models import TradeAccount
from components.Clients.Alpaca.api_alpaca import api
from components.Clients.Alpaca.portfolio import parse_positions
from components.Clients.Alpaca.executionManager import exitOrder,optionsOrder
from components.Clients.Alpaca.Strategy.OptionsOI import Strategy_PricingModel
from components.Clients.Alpaca.price_data import get_latest_quote
from pytz import timezone
import datetime as dt
import numpy as np
import math
import config
from flask import Flask
from flask_caching import Cache
import time
import redis
import re

redis_client = redis.Redis(host='redis-stack-server', port=6379, decode_responses=True)
ts = redis_client.ts()
if not redis_client.exists("pnl"):
    ts.create("pnl")

def initialize_globals():
    # Set initial highest_equity in Redis
    redis_client.set('highest_equity_date', str(dt.date.today()))
    redis_client.set('highest_equity', float(api.get_account().last_equity)) #type: ignore
    redis_client.set('portfolio_delta', 0)

# Initialize global variables for the first request in each thread
initialize_globals()

def alpaca_rebalance():
    return
    currentDate = str(date.today())
    current_equity = float(api.get_account().equity)
    goal = config.PORTFOLIO_REBAL / 100

    # Retrieve highest_equity from Redis
    highest_equity = float(redis_client.get('highest_equity'))
    portfolio_pnl = math.log(current_equity / highest_equity)
    print(f"Daily P/L || Current: {portfolio_pnl:.4f}% Goal: {goal:.4f}%")

    try:
        ts.add("pnl", int(time.time()), portfolio_pnl)
    except Exception as e:
        print(e)

    if (portfolio_pnl > goal): 
        print(f"Rebalancing Portfolio...")
        api.close_all_positions(True)
        
        # Update highest_equity in Redis
        if redis_client.set('highest_equity', current_equity):
            print(f"Updated highest_equity: {current_equity}")

    
    if redis_client.get('highest_equity_date') != currentDate:
        if redis_client.set('highest_equity_date', currentDate) and redis_client.set('highest_equity', current_equity):
            print(f"Updating: {currentDate} {current_equity}")

    # The Redis client automatically handles atomic operations

def managePNL(client=api.client['DEV'],tp=0.1,sl=-0.05):
    current_time = dt.datetime.now(timezone('US/Eastern')).time()
    if dt.time(16, 30) <= current_time or current_time <= dt.time(10,30):
        print('trading blockout hours for options')
        return

    starttime = dt.datetime.now()
    pos_raw = client.get_all_positions()
    if not pos_raw:
        return
    pos = parse_positions(pos_raw)
    if pos.empty:
        return
    manageOptions(client,pos)
    elapsed_time = (dt.datetime.now() - starttime).total_seconds() // 60
    print(f'Portfolio sweep complete ({elapsed_time} mins)...')

def manageOptions(client,pos):
    positions=pos.loc[
        (pos['asset_class'].str.contains("us_option",case=False)) &
        # ((pos['unrealized_plpc'] > tp)) & 
        # (pos['market_value'] > pos['breakeven']) & 
        (pos['qty_available'] > 0)
    ].copy()

    if positions.empty:
        return
    
    valid_orders = []
    stoploss_orders = []
    portfolio_delta = []
    for index, row in positions.iterrows():
        try:
            orders = client.get_orders(filter=GetOrdersRequest(status='open', limit=300, nested=False, symbols=[row.symbol])) #type: ignore
            isOpenOrder = True if orders else False
            if isOpenOrder:
                continue
            res = checkPrices(row)
            if res is None or len(res) < 4:
                continue
            portfolio_delta.append(res[3])
            if res[0]:
                if res[2]:
                    stoploss_orders.append((row.symbol))
                else:
                    valid_orders.append((row.symbol, res[1], max(row.qty_available // 2, 1)))

        except Exception as e:
            print("managePNL ",e)
            continue

    redis_client.set('portfolio_delta', float(sum(portfolio_delta)))

    if valid_orders or stoploss_orders:
        print("positions found to close")
        print(f"portfolio delta: {sum(portfolio_delta):.2f}")

        if len(stoploss_orders)>0:
            for symbol in stoploss_orders:
                try:
                    exitOrder(symbol,client)
                    print(f"Stop Loss hit for {symbol}")
                except Exception as e:
                    print("managePNL ",e)
                    continue
        
        if len(valid_orders)>0:
            for symbol, take_profit, quantity in valid_orders:
                try:
                    result = optionsOrder(symbol,take_profit,client=client,quantity=quantity,side='sell',isMarketOrder=False)
                    # print(f"Order placed for {symbol}, take profit: {take_profit}, quantity: {quantity}")
                except Exception as e:
                    print("managePNL ",e)
                    continue

def checkPrices(row):
    match = re.match(r'^([A-Za-z]+)(\d{6})([PC])(\d+)$', row.symbol)
    base_symbol, expiry, option_type, strike_price = match.groups()
    strike_price = int(strike_price) / 1000.0
    expiry = f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}"
    expiry_date = dt.datetime.strptime(expiry, "%Y-%m-%d")
    today_date = dt.datetime.today()
    days_to_expiry = (expiry_date - today_date).days
    option_type = "put" if option_type == 'P' else "call"


    # Model fitting and data fetching based on the base symbol
    opm = Strategy_PricingModel()
    sell = False
    opm.getData(base_symbol,startoffset=max(days_to_expiry-15,1),maxTime=days_to_expiry+15,limit=100)
    # opm.printStats = True
    opm.fitModel()
    modeled_price,delta = opm.forecast(strike_price,days_to_expiry,option_type)
    try:
        quote = get_latest_quote(row.symbol,'options').iloc[0]
        liquid_spread_worst = np.log(quote.bid_price/modeled_price) if quote.bid_price > 0.0 else -1.0
        liquid_plpc_worst = np.log(quote.bid_price/row.cost_per_unit) if quote.bid_price > 0.0 else -1.0
        liquid_spread_mid = np.log(quote.mid_price/modeled_price)
        liquid_plpc_mid = np.log(quote.mid_price/row.cost_per_unit)
        # print(f'{liquid_spread_worst:.2%} {liquid_plpc_worst:.2%} {liquid_spread_mid:.2%} {liquid_plpc_mid:.2%}')
    except Exception as e:
        print(e)

    model_spread_entry = np.log(row.cost_per_unit/modeled_price)
    model_spread_current = np.log(row.current_price/modeled_price)

    tp=float(row.cost_per_unit)+modeled_price/2
    target_spread = np.abs(opm.target_spread)/2
    expiry_exit = days_to_expiry < 4
    badDelta = np.abs(delta) < 0.4
    pnl = liquid_plpc_worst > 2.0
    marketOrder = badDelta or pnl or expiry_exit #(model_spread_entry > target_spread and model_spread_current > target_spread) or 
    limitOrder = model_spread_entry < -target_spread and liquid_spread_mid < -target_spread and liquid_plpc_worst > 0.0
    sell = marketOrder or limitOrder
    
    if sell:
        print(f"{row.symbol} Strike: {strike_price} Days: {days_to_expiry} PnL Liq: {liquid_plpc_worst:.1%} PnL: {row.unrealized_plpc:.1%}\n Target: {target_spread:.1%}  Entry: {model_spread_entry:.1%} Current: {model_spread_current:.1%} Model: {modeled_price:.2f} Delta: {delta:.2f}")    

    return [sell,tp,marketOrder,delta]

def reversalDCA(client=api.client['DEV'],exposure_Target=0.05):
    pos_raw = client.get_all_positions()
    if not pos_raw:
        return
    pos = parse_positions(pos_raw)

    try:
        acct_info_prod = client.get_account()
    except:
        return
    equity = float(acct_info_prod.equity) #type: ignore
    buyingpower_nm = float(acct_info_prod.non_marginable_buying_power) #type: ignore
    exposure_Current = buyingpower_nm / equity
    
    exposure_Ratio = exposure_Current / exposure_Target

    if not(exposure_Ratio <= 1.25): #only checking if excess cash to deploy
        damper = 1
        adjustment_factor = abs((1 / exposure_Ratio)-1)*damper if exposure_Ratio > 1 else abs(exposure_Ratio-1)*damper
        for index, position in pos.iterrows():
            if "option" in position['asset_class']:
                continue

            symbol = position['symbol']
            current_quantity = abs(position['qty_available'])
            side = position['side']
            
            new_quantity = current_quantity * adjustment_factor
            quantity_diff = new_quantity
            
            if "short" in side and current_quantity < 2:
                continue

            # Place an order to adjust the position
            if quantity_diff != 0: # and position['unrealized_plpc'] < 0:
                qty = int(math.ceil(quantity_diff)) if "short" in side else round(quantity_diff,9)
                side_order = 'buy' if ((exposure_Ratio > 1 and "long" in side) or (exposure_Ratio < 1 and "sell" in side)) else 'sell'
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_order,
                    time_in_force='day',
                )
                print(symbol,round(exposure_Ratio,3),round(adjustment_factor,3),round(quantity_diff,3),side)
                try:
                    client.submit_order(orderData)
                except Exception as e:
                    print(f'{symbol}: {e}')
                    try:
                        client.submit_order(MarketOrderRequest(symbol=symbol,notional=1.0,side=side_order,time_in_force='day'))
                    except Exception as e:
                        print(f'Err 2. {symbol}: {e}')
    print(round((float(client.get_account().non_marginable_buying_power)/float(client.get_account().equity))/exposure_Target,3)) #type: ignore




    


# In your Flask route or application setup, call initialize_globals() to set up the initial highest_equity in Redis.