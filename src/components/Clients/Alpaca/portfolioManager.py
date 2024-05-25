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
import threading
import time
import redis
import json
import logging
import pandas as pd

redis_client = redis.Redis(host=str(config.DB_HOST), port=int(str(config.DB_PORT)), decode_responses=True)
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

# def alpaca_rebalance(): #TODO: Deprecate
#     return
#     currentDate = str(date.today())
#     current_equity = float(api.get_account().equity)
#     goal = config.PORTFOLIO_REBAL / 100

#     # Retrieve highest_equity from Redis
#     highest_equity = float(redis_client.get('highest_equity'))
#     portfolio_pnl = math.log(current_equity / highest_equity)
#     print(f"Daily P/L || Current: {portfolio_pnl:.4f}% Goal: {goal:.4f}%")

#     try:
#         ts.add("pnl", int(time.time()), portfolio_pnl)
#     except Exception as e:
#         print(e)

#     if (portfolio_pnl > goal): 
#         print(f"Rebalancing Portfolio...")
#         api.close_all_positions(True)
        
#         # Update highest_equity in Redis
#         if redis_client.set('highest_equity', current_equity):
#             print(f"Updated highest_equity: {current_equity}")

    
#     if redis_client.get('highest_equity_date') != currentDate:
#         if redis_client.set('highest_equity_date', currentDate) and redis_client.set('highest_equity', current_equity):
#             print(f"Updating: {currentDate} {current_equity}")

def managePNL():
    if not api.trading_hours():print('trading blockout hours');return
    
    print(f'Portfolio Check Start...')
    starttime = dt.datetime.now()

    for id,client in api.client.items():
        pos_raw = client.get_all_positions()
        if not pos_raw:continue

        pos = parse_positions(pos_raw)
        if pos.empty:continue

        if not api.trading_hours(resume_time=9,pause_time=16):continue

        manageOptions(client,pos)

        
    elapsed_time = (dt.datetime.now() - starttime).total_seconds() // 60
    print(f'Portfolio Check complete ({elapsed_time} mins)...')
    

def manageOptions(client,pos):
    positions=pos.loc[
        (pos['asset_class'].str.contains("us_option",case=False)) &
        (pos['qty_available'] > 0)
    ].copy()

    if positions.empty:
        return
    
    limit_orders = []
    stoploss_orders = []
    portfolio_delta = []
    for i, row in positions.iterrows():
        try:
            orders = client.get_orders(filter=GetOrdersRequest(status='open', limit=300, nested=False, symbols=[row.symbol])) #type: ignore
            isOpenOrder = True if orders else False
            if isOpenOrder:
                continue
            
            res = checkPrices(row)

            portfolio_delta.append(res[3]*row.qty)

            if res[0]:
                if res[2]:
                    stoploss_orders.append(row.symbol)
                else:
                    volume = max(res[4]//10,1)
                    limit_orders.append((row.symbol, res[1], min(row.qty_available, volume)))

        except Exception as e:
            logging.exception(f"{manageOptions.__name__} Error: {e}")
            continue

    if portfolio_delta is not None:
        # pass this to the database
        if client is api.client['DEV']:
            redis_client.set('portfolio_delta', float(sum(portfolio_delta)))
        else:
            redis_client.set('portfolio_delta_live', float(sum(portfolio_delta)))    

    if limit_orders or stoploss_orders:
        print("positions found to close")
        print(f"portfolio delta: {sum(portfolio_delta):.2f}")

        if len(stoploss_orders)>0:
            for symbol in stoploss_orders:
                try:
                    exitOrder(symbol,client)
                    print(f"Stop Loss hit for {symbol}")
                except Exception as e:
                    if "options market orders are only allowed during market hours" in str(e):
                        logging.debug(f"{manageOptions.__name__} Error 2: {e}")
                    else:
                        logging.exception(f"{manageOptions.__name__} Error 2: {e}")
                    continue
        
        if len(limit_orders)>0:
            for symbol, take_profit, quantity in limit_orders:
                try:
                    result = optionsOrder(symbol,take_profit,orderID=symbol,client=client,quantity=quantity,side='sell',isMarketOrder=False)
                    # print(f"Order placed for {symbol}, take profit: {take_profit}, quantity: {quantity}")
                except Exception as e:
                    if "options market orders are only allowed during market hours" in str(e):
                        logging.debug(f"{manageOptions.__name__} Error 3: {e}")
                    else:
                        logging.exception(f"{manageOptions.__name__} Error 3: {e}")
                    continue

def checkPrices(row):
    base_symbol,strike_price,days_to_expiry,option_type = api.parseOptSym(row.symbol) #type: ignore
    if days_to_expiry < 3:
        return [True,0.0,True,0.0]
    # moved inside of class
    # Model fitting and data fetching based on the base symbol
    opm = Strategy_PricingModel()
    try:
        opm.getData(base_symbol,startoffset=max(days_to_expiry-15,1),maxTime=days_to_expiry+15,limit=100)
        # opm.printStats = True
        opm.fitModel()
        modeled_price,delta = opm.forecast(strike_price,days_to_expiry,option_type)
    except Exception as e:
        logging.exception(f"{checkPrices.__name__} Error: {e}")
        return [False,0.0,False,0.0]

    try:
        quote = get_latest_quote(row.symbol,'options').iloc[0]
        if quote.bid_price == 0.0 or quote.mid_price == 0.0:
            print(row.symbol,quote.bid_price,quote.mid_price)
            return [False,0.0,False,delta]
        
        # Fixing an error on alpaca's end
        # print(f'[{row.symbol}] {row.current_price} {row.current_price/row.qty}')
        # print(f'[{row.symbol}] {row.cost_basis} {row.avg_entry_price}')
        # print(f'[{row.symbol}] {row.unrealized_plpc:.2%}')

        # hotfix for alpaca options contract rounding error
        if row.unrealized_plpc >= 10: #row.cost_per_unit < 0.01 and row.cost_per_unit != 0.0:
            row.cost_per_unit = round(100*row.cost_per_unit,2)

        liquid_spread_worst = np.log(quote.bid_price/modeled_price)
        liquid_plpc_worst = np.log(quote.bid_price/row.cost_per_unit)
        liquid_spread_mid = np.log(quote.mid_price/modeled_price)
        liquid_plpc_mid = np.log(quote.mid_price/row.cost_per_unit)
        
        # logging.info(f'[{row.symbol}] {row.cost_per_unit} P/L: [{liquid_plpc_mid:.2%},{liquid_plpc_worst:.2%},{row.unrealized_plpc:.2%}]  % of Spread: [{liquid_spread_mid:.2%} {liquid_spread_worst:.2%}]')

        # Exit conditions
        tp=max(float(row.cost_per_unit),quote.mid_price)
        # target_spread = np.abs(opm.target_spread)
        time_exit = days_to_expiry < 4
        badDelta = np.abs(delta) < 0.2
        stoploss = max(liquid_plpc_mid,liquid_plpc_worst) < api.adjustmentTimed(startValue=-0.7,finalValue=-0.9,startDate=dt.datetime(2024, 5, 23),period=30)
        pnl = max(liquid_plpc_mid,liquid_plpc_worst) > api.adjustmentTimed(startValue=2.0,finalValue=3.0,startDate=dt.datetime(2024, 5, 23),period=30) # and quote.mid_price >= modeled_price ///// previously needed to check midprice to place safer market orders. switched to limit orders. also changed to vw_midprice
        marketOrder = time_exit
        reason = "delta" if badDelta else "time" if time_exit else "stoploss"
        sell = marketOrder or pnl
        simple_midprice = ((quote.ask_price+quote.bid_price)/2)
        conditions = [sell,[time_exit,days_to_expiry],[badDelta,round(delta,2)],pnl,marketOrder,[simple_midprice<quote.mid_price,round(simple_midprice,2),round(quote.mid_price,2)]]
        if sell:
            print(f'[{row.symbol}]: {row.cost_per_unit:.4f} P/L: {liquid_plpc_mid:.2%} of Spread: {liquid_spread_mid:.2%}')
            logging.info(f'{row.symbol} {conditions}')
            logging.info(f'[{row.symbol}] {row.cost_per_unit} P/L: [{liquid_plpc_mid:.2%} {liquid_plpc_worst:.2%}]  % of Spread: [{liquid_spread_mid:.2%} {liquid_spread_worst:.2%}]')
            logging.info(f"{row.symbol} Strike: {strike_price} Model Price: {modeled_price:.2f} Mid Price: {quote.mid_price:.2f} Mid2: {simple_midprice:.2f} Delta: {delta:.2f}")    
            
        return [sell,tp,marketOrder,delta,quote.mid_v,reason]

    except Exception as e:
        logging.exception(f"{checkPrices.__name__} Error: {e}")
        return [False,0.0,False,delta]

def reversalDCA(client=api.client['DEV'],exposure_Target=0.05):
    try:
        pm = PortfolioManager(client=client)
    except:
        return
    
    try:
        equity = pm.equity_VaR #type: ignore
        buyingpower_nm = pm.buyingpower_nm #type: ignore
        exposure_Current = buyingpower_nm / equity
        
        exposure_Ratio = exposure_Current / max(exposure_Target,pm.cash_allocation)

        threshold_sell = 0.75
        threshold_buy = 1.25
        if (threshold_sell < exposure_Ratio < threshold_buy): # check for imbalance
            print("cleared",exposure_Ratio)
            return

        pos_raw = client.get_all_positions()
        if not pos_raw:
            return
        pos = parse_positions(pos_raw)

        equities_pre = pos.loc[~pos['asset_class'].str.contains("us_option",case=False)]
        equities = equities_pre.loc[~((equities_pre['side'].str.contains("short",case=False)) & (equities_pre['qty_available'].abs() < 2))].copy()
        equities['abs_market_value'] = equities['market_value'].abs()
        if exposure_Ratio > 1:
            threshold = equities['abs_market_value'].quantile(0.75)
            filtered_equities = equities.loc[equities['abs_market_value'] <= threshold]
        else:
            threshold = equities['abs_market_value'].quantile(0.75)
            filtered_equities = equities.loc[equities['abs_market_value'] >= threshold]


        damper = 1
        adjustment_factor = abs((1 / exposure_Ratio)-1)*damper if exposure_Ratio > 1 else abs(exposure_Ratio-1)*damper
        for index, position in filtered_equities.iterrows():

            symbol = position['symbol']
            current_quantity = abs(position['qty_available'])
            side = position['side']
            
            new_quantity = current_quantity * adjustment_factor
            quantity_diff = new_quantity
            
            # Place an order to adjust the position
            if quantity_diff != 0:
                qty = int(math.ceil(quantity_diff)) if "short" in side else round(quantity_diff,9)
                side_order = 'buy' if ((exposure_Ratio > 1 and "long" in side) or (exposure_Ratio < 1 and "sell" in side)) else 'sell'
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_order,
                    time_in_force='day',
                )
                print(symbol,round(exposure_Ratio,3),round(adjustment_factor,3),round(quantity_diff,3),side,side_order)
                try:
                    client.submit_order(orderData)
                except Exception as e:
                    try:
                        if "minimal" in str(e):
                            client.submit_order(MarketOrderRequest(symbol=symbol,notional=1.0,side=side_order,time_in_force='day'))
                    except Exception as e:
                        logging.exception(f"{reversalDCA.__name__} Error 1: {e}")
        print(f"Exposure Ratios: [{exposure_Ratio:.3%} {((float(client.get_account().non_marginable_buying_power)/float(client.get_account().equity))/exposure_Target):.3%}]") #type: ignore
    except Exception as e:
        logging.exception(f"{reversalDCA.__name__} Error 2: {e}")

class PortfolioManager():
    def __init__(self,client = api.client['DEV']):
        self.riskfreerate = 0.05161
        self.short_interest_rate = 0.085
        self.cash_allocation = 0.05
        self.stock_allocation = 0.7
        self.options_allocation = 1-(self.cash_allocation+self.stock_allocation)
        self.long_bias = 0.2
        self.short_allocation = self.riskfreerate+self.short_interest_rate+self.long_bias+1
        self.base_risk = config.RISK_EXPOSURE
        # self.portfolio_delta = float(redis_client.get('portfolio_delta')) if client is api.client['DEV'] else float(redis_client.get('portfolio_delta_live'))
        self.client = client
        self.update_values(client)
        self.update_instruments(client)



    def update_values(self,client = api.client['DEV']):
        key = 'portfolio_delta_live' if client is api.client['LIVE'] else 'portfolio_delta'
        portfolio_delta = redis_client.get(key)
        self.portfolio_delta = float(portfolio_delta) if portfolio_delta is not None else 0.0

        # self.portfolio_delta = float(redis_client.get('portfolio_delta')) if client is api.client['DEV'] else float(redis_client.get('portfolio_delta_live'))
        

        acct_info = client.get_account()
        if not acct_info:
            return False
        
        self.buyingpower = float(acct_info.regt_buying_power)
        self.buyingpower_nm = float(acct_info.non_marginable_buying_power) #type: ignore
        self.long_value = float(acct_info.long_market_value)
        self.short_value = float(acct_info.short_market_value)
        if self.short_value != 0.0:
            self.ls_ratio = abs(self.long_value/self.short_value)
        else: 
            self.ls_ratio = 1.0

        self.equity = float(acct_info.equity) #type: ignore
        self.cash_allocation = max(0.05,200/self.equity)
        self.exposure_Current = self.buyingpower_nm / self.equity
        self.exposure_Ratio =  self.exposure_Current / self.cash_allocation
        return True

    def update_holdings(self,client = api.client['DEV']):
        pos_raw = client.get_all_positions()    
        if not pos_raw:
            self.positions = pd.DataFrame()
            return False
        
        self.positions = parse_positions(pos_raw) #TODO: handle error when positions is empty but class variable now exists
        if self.positions.empty:
            return False
        
        posdf_json = self.positions.to_json(orient='records')
        if client is api.client['DEV']:
            redis_client.set('current_positions_DEV', posdf_json)
        else:
            redis_client.set('current_positions_LIVE', posdf_json)

        return True
    
    def update_instruments(self,client = api.client['DEV']):
        if not self.update_holdings(client=client):
            return False
        
        try:
            equities = self.positions.loc[~self.positions['asset_class'].str.contains("us_option",case=False)].copy()
            cost_EQ = equities.cost_basis.abs().to_numpy()
            options = self.positions.loc[self.positions['asset_class'].str.contains("us_option",case=False)]
            cost_OP = options.cost_basis.abs().to_numpy()

            # hotfix for alpaca options rounding error
            hotfix = options.unrealized_plpc.to_numpy()
            if hotfix.any() > 10:
                cost_OP *= 100

            op_ratio = cost_OP.sum()/cost_EQ.sum()
            correctionFactor = self.options_allocation/op_ratio
            smoothingFactor = 0.5
            self.options_CF = correctionFactor*smoothingFactor
            self.op_ratio = op_ratio
            self.options_VaR = cost_OP.sum()
            self.equity_VaR = cost_EQ.sum()
            print(f'Options_VaR: {self.options_VaR:.2f} Equity_VaR: {self.equity_VaR:.2f} Op_Ratio: {op_ratio:.2%} Portfolio_Delta {self.portfolio_delta:.2f}')
            return True
        except Exception as e:
            logging.exception(f"{self.update_instruments.__name__} Error: {e}")
            return False

    def rebalance(self,client=api.client['DEV']):
        if not (self.update_holdings(client=client) and self.update_values(client=client)):
            return

        threshold_sell = 0.75
        threshold_buy = 1.25
        if (threshold_sell < self.exposure_Ratio < threshold_buy): # check for imbalance
            return

        damper = 1
        adjustment_factor = abs((1 / self.exposure_Ratio)-1)*damper if self.exposure_Ratio > 1 else abs(self.exposure_Ratio-1)*damper

        equities_pre = self.positions.loc[~self.positions['asset_class'].str.contains("us_option",case=False)]
        equities = equities_pre.loc[~((equities_pre['side'].str.contains("short",case=False)) & (equities_pre['qty_available'].abs() < 2))].copy()
        equities['abs_market_value'] = equities['market_value'].abs()

        if self.exposure_Ratio > 1:
            threshold = equities['abs_market_value'].quantile(0.50)
            filtered_equities = equities.loc[equities['abs_market_value'] <= threshold]
        else:
            threshold = equities['abs_market_value'].quantile(0.75)
            filtered_equities = equities.loc[equities['abs_market_value'] >= threshold]

        for i, position in filtered_equities.iterrows():
            symbol = position['symbol']
            mv = position['market_value']
            current_quantity = abs(position['qty_available'])
            side = position['side']
            
            new_quantity = current_quantity * adjustment_factor
            quantity_diff = new_quantity

            if quantity_diff != 0: # and position['unrealized_plpc'] < 0:
                qty = int(math.ceil(quantity_diff)) if "short" in side else round(quantity_diff,9)
                side_order = 'buy' if ((self.exposure_Ratio > 1 and "long" in side) or (self.exposure_Ratio < 1 and "sell" in side)) else 'sell'
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side_order,
                    time_in_force='day',
                )
                logging.info(symbol,round(mv,3),round(self.exposure_Ratio,3),round(self.exposure_Current,3),round(adjustment_factor,3),round(quantity_diff,3),side,side_order)
                try:
                    client.submit_order(orderData)
                except Exception as e:
                    try:
                        if 'minimal' in str(e):
                            client.submit_order(MarketOrderRequest(symbol=symbol,notional=1.0,side=side_order,time_in_force='day'))  
                    except Exception as e:
                        logging.exception(f"{self.rebalance.__name__} Error: {e}")
        self.update_values()
        print(round(self.exposure_Ratio,3)) #type: ignore

