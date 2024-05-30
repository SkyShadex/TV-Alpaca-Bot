import json
import logging
from logging.handlers import TimedRotatingFileHandler
import queue
import threading
import redis
from threading import Lock, Thread
from pytz import timezone
import tracemalloc
import warnings
import numpy as np

from alpaca.trading.requests import GetOrdersRequest
from flask import (Flask, abort, jsonify, render_template,
                   render_template_string, request)
from flask_caching import Cache
from components.Clients.Alpaca import executionManager, portfolio
from components.Clients.Alpaca.portfolioManager import managePNL,reversalDCA,PortfolioManager

import sys
import config
from commons import start, vars
from components import discord
from components.Clients.Alpaca.api_alpaca import api
import components.Clients.MetaTrader.mt5_server as mt5
from components.techanalysis import screener
from components.Clients.Alpaca import DataAnalysis as da
from components.Clients.Alpaca.Strategy.StrategyManager import StrategyManager
from flask_apscheduler import APScheduler


app = Flask(__name__)
# cache = Cache(app, config={'CACHE_TYPE': 'simple'})
logging.basicConfig(level=logging.INFO,stream=sys.stdout,filemode="a",format='%(asctime)s %(levelname)s:%(name)s:%(message)s') #filename="logs/py_log.log"
redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
# redis_client.bgsave()

accountInfo = api.get_account()
order_lock = Lock()

tracemalloc.start()
s = None

manager_scheduler = APScheduler()
scheduler = APScheduler()
warnings.simplefilter('ignore', np.RankWarning)

def run_strat():
    universe = StrategyManager("TSMOM",1)
    l_etf = StrategyManager("TSMOM",2)
    weeklies = StrategyManager("TSMOM",3)

def run_opt():
    opt = StrategyManager("TSMOM_O")

def run_hedge():
    opt = StrategyManager("HEDGE")

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

    if options[0]:
        if onInit:
            scheduler.add_job(id='optionsStrat_init', func=run_opt)
        scheduler.add_job(id='hedgeStrat_loop', func=run_hedge, trigger='cron', day_of_week='mon-fri', hour='*/4', start_date='2024-03-25 13:40:00', misfire_grace_time = None)
        scheduler.add_job(id='optionsStrat_loop', func=run_opt, trigger='cron', day_of_week='mon-fri', minute='*/10', start_date='2024-03-25 08:05:00', max_instances=2)

    if equities:
        if onInit:
            scheduler.add_job(id='init_stocks_1', func=run_strat)
        scheduler.add_job(id='run_strategy_job_1', func=run_strat, trigger='cron', day_of_week='mon-fri', minute='*/25', start_date='2024-03-25 08:00:00', max_instances=2)
        scheduler.add_job(id='run_stocks_job_close', func=run_strat, trigger='cron', day_of_week='mon-fri', hour=19, minute=50, misfire_grace_time = None)

    manager_scheduler.init_app(app)
    manager_scheduler.start()
    scheduler.init_app(app)
    scheduler.start()

    if not api.trading_hours() and TradingHours:
        print(f"Pause Operations... {scheduler.state}")
        scheduler.pause()    

start.startMessage(api.prod.get_account().buying_power, api.prod.get_account().non_marginable_buying_power, api.prod.get_account().daytrade_count) # type: ignore
start.startMessage(accountInfo.buying_power, accountInfo.non_marginable_buying_power, accountInfo.daytrade_count) # type: ignore
manageSchedules(TradingHours=True,OrderReset=False,equities=True,options=[True,True],portfolio=[True,True],onInit=True)  

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

# @app.route('/account', methods=['GET'])
# def account():    
#     payload = f'{accountInfo}'
#     pretty_json = json.dumps(payload, indent=4)
#     html = f"<pre>{pretty_json}</pre>"
#     return render_template_string(html)

# @app.route('/screen', methods=['GET'])
# def screen():
#     response = screener.test()
#     return jsonify(response)

# @app.route('/portfolio', methods=['GET'])
# def portDisplay():
#     portfolio_plot = 'portfolioperformance.png'
#     asset_plot = 'assetperformance.png'
#     portfolio.graph(plot_filename=portfolio_plot)
#     # da.dataCrunch(plot_filename=asset_plot)
#     return render_template('portfolio.html', portfolio_plot=portfolio_plot, asset_plot=portfolio_plot)

# file_path = 'logs/data.txt'
# lock_file_path = 'logs/lock.txt'
# post_buffer = queue.Queue()
# buffer_lock = threading.Lock()
# mt5_lock = Lock()
# mt5_queue = queue.Queue()

# @app.route("/snapshot")
# def snap():
#     global s
#     if not s:
#         s = tracemalloc.take_snapshot()
#         return "taken snapshot\n"
#     else:
#         lines = []
#         top_stats = tracemalloc.take_snapshot().compare_to(s, 'lineno')
#         for stat in top_stats[:5]:
#             lines.append(str(stat))
#         return "\n".join(lines)

# def process_post_requests():
#     while True:
#         try:
#             webhook_message = post_buffer.get(timeout=1)  # Wait for 1 second to get a message from the queue 
#         except queue.Empty:
#             continue  # If the queue is empty, continue waiting for messages
#         # Remove the lock file
#         #if os.path.isfile(lock_file_path):
#         #    os.remove(lock_file_path)
#         #logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
#         #logging.info('Webhook message received: %s', webhook_message)

#         # Process and Store Value
#         #mt5_queue.put(mt5.main(webhook_message))
#         data = mt5.main(webhook_message)
#         for x in range(5):
#             redis_client.lpush('orderHold',data)


#         # Check if the lock file exists
#         #if os.path.isfile(lock_file_path):
#         #   continue

#         # Create the lock file
#         #with open(lock_file_path, 'w') as lock_file:
#         #    lock_file.write('locked')
#         if False:
#             symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, stratID_WH = vars.webhook(webhook_message)
#             content = f"Strategy Alert [MT5]: {side_WH}({comment_WH}) -|- {symbol_WH}: {quantity_WH} units @ {round(price_WH,3)} -|- Strategy ID: {stratID_WH}"
#             discord.message(content)

# # Start the background process for processing POST requests
# post_thread = Thread(target=process_post_requests)

# def get_file_content():
#     with open(file_path, 'r') as file:
#         return file.read()

# # @app.route('/mt5client', methods=['GET'])
# # def mt5client():
# #     # Check if there are orders available
# #     data = redis_client.lpop('orderHold')
# #     if data is None or True:
# #         #olddata = get_file_content()
# #         olddata = "No Order Found"
# #         response = {'message': olddata}
# #         return jsonify(response), 404
# #     else:
# #         response = {'file_content': data}
# #         return jsonify(response), 200

# # def orderResults(webhook_message,side_WH):
# #     try:
# #         response = executionManager.executeOrder(webhook_message)

# #         if isinstance(response, Order):
# #             orderInfo = vars.extract_order_response(response)
# #             content = f"Alpaca: Order executed successfully -|- {orderInfo['qty']} units of {orderInfo['symbol']} -|- Timestamp: {orderInfo['submitted_at']}"
# #             discord.message(content)
# #             logging.info(content)
# #             return jsonify(message='Order executed successfully!', orderInfo=orderInfo)

# #     # Error Handling
# #     except exceptions.APIError as e: 
# #         error_message = f"Alpaca Error: {str(e)} for {side_WH} order"
# #         discord.message(error_message)

# #         good_errors = ["position not found", "order not found", "is not active", "asset not found", "not tradable", "insufficient balance for USD"]
# #         if any(error in str(e) for error in good_errors):
# #             return jsonify(error=error_message), 200
# #         else:
# #             return jsonify(error=error_message), 500

# # @app.route('/webhook', methods=['POST']) # type: ignore
# # def webhook():
# #     payload = request.data.decode("utf-8")
# #     start_index = payload.find('{')
# #     end_index = payload.rfind('}')

# #     if start_index == -1 or end_index == -1 or end_index <= start_index:
# #         return {'code': 'error', 'message': 'Invalid payload'}
# #     extrainfo = payload[:start_index].strip()
# #     cleaned_payload = payload[start_index:end_index+1]

# #     webhook_message = json.loads(cleaned_payload)

# #     #logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
# #     #logging.info('Webhook message received: %s', webhook_message)

# #     if webhook_message['passphrase'] != config.WEBHOOK_PASSPHRASE:
# #         return {'code': 'error', 'message': 'nice try buddy'}
    
# #     if "mt5" in extrainfo:
# #         with buffer_lock:
# #             post_buffer.put(webhook_message)
# #             response = "Request Buffered."
# #             return jsonify(response), 200

# #     symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, stratID_WH = vars.webhook(
# #         webhook_message)
# #     content = f"Strategy Alert: {side_WH}({comment_WH}) -|- {symbol_WH}: {quantity_WH} units @ {round(price_WH,3)} -|- Strategy ID: {stratID_WH}"
# #     discord.message(content)

# #     with order_lock:
# #         orderResults(webhook_message,side_WH)
    