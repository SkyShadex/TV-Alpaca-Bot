import json
import logging
from logging.handlers import TimedRotatingFileHandler
import redis
import numpy as np

from alpaca.trading.requests import GetOrdersRequest
from flask import (Flask, render_template)
from components.Clients.Alpaca import executionManager, portfolio
from components.Clients.Alpaca.portfolioManager import managePNL,reversalDCA,PortfolioManager

import sys
import config
from commons import start
from components.Clients.Alpaca.api_alpaca import api
from components.Clients.Alpaca import DataAnalysis as da
from flask_apscheduler import APScheduler


app = Flask(__name__)
logging.basicConfig(level=logging.INFO,stream=sys.stdout,filemode="a",format='%(asctime)s %(levelname)s:%(name)s:%(message)s') #filename="logs/py_log.log"
redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
accountInfo = api.get_account()

s = None

manager_scheduler = APScheduler()
scheduler = APScheduler()

def manageSchedules(TradingHours,OrderReset,equities,options,portfolio,onInit):
    if TradingHours:
        manager_scheduler.add_job(id='bod', func=scheduler.resume, trigger='cron', day_of_week='mon-fri', hour=8, minute=0, misfire_grace_time = None)
        manager_scheduler.add_job(id='eod', func=scheduler.pause, trigger='cron', day_of_week='mon-fri', hour=20, minute=5,misfire_grace_time = None)

    if OrderReset:
        if onInit:
            api.prod.cancel_orders()
            api.cancel_orders()
        manager_scheduler.add_job(id='reset_orders_1', func=api.prod.cancel_orders, trigger='cron', day_of_week='mon-fri', hour=8, minute=0, misfire_grace_time = None)
        manager_scheduler.add_job(id='reset_orders', func=api.cancel_orders, trigger='cron', day_of_week='mon-fri', hour=8, minute=0, misfire_grace_time = None)

    if portfolio[0]:
        if portfolio[1]:
            scheduler.add_job(id='managePNL_init', func=managePNL)
            # scheduler.add_job(id='options_metrics_init', func=da.calcPerformance)
            # scheduler.add_job(id='rebalance_devtest', func=reversalDCA, args=[api.client['DEV']])
        scheduler.add_job(id='managePNL_loop', func=managePNL, trigger='cron', day_of_week='mon-fri', minute='*/10', start_date='2024-03-25 13:15:00')
        scheduler.add_job(id='options_metrics', func=da.calcPerformance, trigger='cron', day_of_week='mon-fri', hour=20, misfire_grace_time = None)
        scheduler.add_job(id='rebalance_Dev', func=reversalDCA, trigger='cron', day_of_week='mon-fri', hour=13, minute=31, misfire_grace_time = None)  
        scheduler.add_job(id='rebalance_Prod', func=reversalDCA, args=[api.client['LIVE']], trigger='cron', day_of_week='mon-fri', hour=19, misfire_grace_time = None)
        # scheduler.add_job(id='rebalance_job_1', func=alpaca_rebalance, trigger='interval', minutes=1, start_date='2024-03-25 08:05:00')

    manager_scheduler.init_app(app)
    manager_scheduler.start()
    scheduler.init_app(app)
    scheduler.start()

    if not api.trading_hours() and TradingHours:
        print(f"Pause Operations... {scheduler.state}")
        scheduler.pause()    

start.startMessage(api.prod.get_account().buying_power, api.prod.get_account().non_marginable_buying_power, api.prod.get_account().daytrade_count) # type: ignore
start.startMessage(accountInfo.buying_power, accountInfo.non_marginable_buying_power, accountInfo.daytrade_count) # type: ignore
manageSchedules(TradingHours=False,OrderReset=False,equities=True,options=[True,True],portfolio=[True,True],onInit=True)  

# Making the dashboard dynamic
def fetch_orders():
    orderParams = GetOrdersRequest(status='all', limit=100, nested=True) # type: ignore
    orders = api.get_orders(filter=orderParams)
    return orders

def fetch_account_info():
    return api.get_account()

# Flask Routes
@app.route('/')
def dashboard():
    orders = fetch_orders()
    account_info = fetch_account_info()
    return render_template('dashboard.html', alpaca_orders=orders, account_info=account_info)
