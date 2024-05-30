import json
import logging
import queue
import threading
import redis
from threading import Lock, Thread
import datetime as dt
import tracemalloc
from alpaca.trading.requests import GetOrdersRequest

from flask import (Flask, jsonify, render_template,
                   render_template_string, request)
from flask_caching import Cache
from components.Clients.Alpaca import portfolio

import sys
import config
from commons import start, vars
from components import discord
from components.Clients.Alpaca.api_alpaca import api
import components.Clients.MetaTrader.mt5_server as mt5
from components.techanalysis import screener


app = Flask(__name__)
logging.basicConfig(level=logging.INFO,stream=sys.stdout,filemode="a",format='%(asctime)s %(levelname)s:%(name)s:%(message)s') #filename="logs/py_log.log"
redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Declaring some variables
accountInfo = api.get_account()
order_lock = Lock()

tracemalloc.start()
s = None

print("party time")

start.startMessage(api.prod.get_account().buying_power, api.prod.get_account().non_marginable_buying_power, api.prod.get_account().daytrade_count) # type: ignore
start.startMessage(accountInfo.buying_power, accountInfo.non_marginable_buying_power, accountInfo.daytrade_count) # type: ignore   

def check_alpaca_status():
    if not api.check_alpaca_status():
        logging.warning(jsonify({"error": "Alpaca API is currently unavailable"}), 503)
        return jsonify({"error": "Alpaca API is currently unavailable"}), 503

def fetch_orders():
    orderParams = GetOrdersRequest(status='all', limit=100, nested=True) # type: ignore
    orders = api.get_orders(filter=orderParams)
    return orders

def fetch_account_info():
    return api.get_account()

@app.route('/')
def dashboard():
    orders = fetch_orders()
    account_info = fetch_account_info()
    return render_template('dashboard.html', alpaca_orders=orders, account_info=account_info)

@app.route('/account', methods=['GET'])
def account():    
    payload = f'{accountInfo}'
    pretty_json = json.dumps(payload, indent=4)
    html = f"<pre>{pretty_json}</pre>"
    return render_template_string(html)

@app.route('/screen', methods=['GET'])
def screen():
    response = screener.test()
    return jsonify(response)

@app.route('/portfolio', methods=['GET'])
def portDisplay():
    portfolio_plot = 'portfolioperformance.png'
    asset_plot = 'assetperformance.png'
    portfolio.graph(plot_filename=portfolio_plot)
    # da.dataCrunch(plot_filename=asset_plot)
    return render_template('portfolio.html', portfolio_plot=portfolio_plot, asset_plot=portfolio_plot)

file_path = 'logs/data.txt'
lock_file_path = 'logs/lock.txt'
post_buffer = queue.Queue()
buffer_lock = threading.Lock()
mt5_lock = Lock()
mt5_queue = queue.Queue()

@app.route("/snapshot")
def snap():
    global s
    if not s:
        s = tracemalloc.take_snapshot()
        return "taken snapshot\n"
    else:
        lines = []
        top_stats = tracemalloc.take_snapshot().compare_to(s, 'lineno')
        for stat in top_stats[:5]:
            lines.append(str(stat))
        return "\n".join(lines)

def process_post_requests():
    while True:
        try:
            webhook_message = post_buffer.get(timeout=1)  # Wait for 1 second to get a message from the queue 
        except queue.Empty:
            continue  # If the queue is empty, continue waiting for messages
        # Remove the lock file
        #if os.path.isfile(lock_file_path):
        #    os.remove(lock_file_path)
        #logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
        #logging.info('Webhook message received: %s', webhook_message)

        # Process and Store Value
        #mt5_queue.put(mt5.main(webhook_message))
        data = mt5.main(webhook_message)
        for x in range(5):
            redis_client.lpush('orderHold',data)


        # Check if the lock file exists
        #if os.path.isfile(lock_file_path):
        #   continue

        # Create the lock file
        #with open(lock_file_path, 'w') as lock_file:
        #    lock_file.write('locked')
        if False:
            symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, stratID_WH = vars.webhook(webhook_message)
            content = f"Strategy Alert [MT5]: {side_WH}({comment_WH}) -|- {symbol_WH}: {quantity_WH} units @ {round(price_WH,3)} -|- Strategy ID: {stratID_WH}"
            discord.message(content)

def get_file_content():
    with open(file_path, 'r') as file:
        return file.read()

