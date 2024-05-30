import json
import logging
from logging.handlers import TimedRotatingFileHandler
import redis
import numpy as np

from alpaca.trading.requests import GetOrdersRequest
from flask import (Flask, render_template)
from components.Clients.Alpaca import executionManager, portfolio

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

manager_scheduler = APScheduler()
scheduler = APScheduler()

def manageSchedules(TradingHours,OrderReset,equities,options,portfolio,onInit):
    if TradingHours:
        manager_scheduler.add_job(id='bod', func=scheduler.resume, trigger='cron', day_of_week='mon-fri', hour=8, minute=0, misfire_grace_time = None)
        manager_scheduler.add_job(id='eod', func=scheduler.pause, trigger='cron', day_of_week='mon-fri', hour=20, minute=5,misfire_grace_time = None)

    scheduler.add_job(id='options_metrics', func=da.calcPerformance, trigger='cron', day_of_week='mon-fri', hour=20, misfire_grace_time = None)

    manager_scheduler.init_app(app)
    manager_scheduler.start()
    scheduler.init_app(app)
    scheduler.start()

    if not api.trading_hours() and TradingHours:
        print(f"Pause Operations... {scheduler.state}")
        scheduler.pause()    

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


''''
Risk manager gathers risk metrics

Portfolio risk and Strategy risk

Post metrics back to DB for entry and exit logic

Push weights for smaller balanced portfolio's

HERC, but Cluster Universe to add another layer of diverisifcation
'''