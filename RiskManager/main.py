import json
import logging
from logging.handlers import TimedRotatingFileHandler
import redis
from alpaca.trading.requests import GetOrdersRequest
from flask import Flask,render_template
import sys
from common import config
from common.api_alpaca import api
from components.Clients.Alpaca.Strategy.RiskManager import RiskManager
from flask_apscheduler import APScheduler


app = Flask(__name__)
logging.basicConfig(level=logging.INFO,stream=sys.stdout,filemode="a",format='%(asctime)s %(levelname)s:%(name)s:%(message)s') #filename="logs/py_log.log"
redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)

master_scheduler = APScheduler()
scheduler = APScheduler()

def run_strat():
    universe = RiskManager('weights')

def run_strat2():
    universe = RiskManager('metadata')

def manageSchedules(TradingHours,OrderReset,equities,options,portfolio,onInit):
    if TradingHours:
        master_scheduler.add_job(id='bod', func=scheduler.resume, trigger='cron', day_of_week='mon-fri', hour=8, minute=0, misfire_grace_time = None)
        master_scheduler.add_job(id='eod', func=scheduler.pause, trigger='cron', day_of_week='mon-fri', hour=20, minute=5,misfire_grace_time = None)

    if equities:
        if onInit:
            # scheduler.add_job(id='risk_manager_init', func=run_strat2)
            ...
        scheduler.add_job(id='risk_manager_loop', func=run_strat, trigger='cron', day_of_week='mon-fri', hour='*/2', start_date='2024-03-25 08:00:00', max_instances=1)
        scheduler.add_job(id='risk_manager_loop2', func=run_strat2, trigger='cron', day_of_week='mon-fri', day='*/1', start_date='2024-03-25 08:00:00', max_instances=1)

    master_scheduler.init_app(app)
    master_scheduler.start()
    scheduler.init_app(app)
    scheduler.start()

    if not api.trading_hours() and TradingHours:
        print(f"Pause Operations... {scheduler.state}")
        scheduler.pause()    

manageSchedules(TradingHours=True,OrderReset=False,equities=True,options=[True,True],portfolio=[True,True],onInit=True)  

# # Making the dashboard dynamic
# def fetch_orders():
#     orderParams = GetOrdersRequest(status='all', limit=100, nested=True) # type: ignore
#     orders = api.get_orders(filter=orderParams)
#     return orders

# def fetch_account_info():
#     return api.get_account()

# # Flask Routes
# @app.route('/')
# def dashboard():
#     orders = fetch_orders()
#     account_info = fetch_account_info()
#     return render_template('dashboard.html', alpaca_orders=orders, account_info=account_info)
