import json
import logging
# import queue
# import threading
import redis
from threading import Lock, Thread
import datetime as dt
import tracemalloc
from alpaca.trading.requests import GetOrdersRequest

from flask import (Flask, jsonify, render_template,
                   render_template_string, request)
from flask_caching import Cache
import requests
import sys
import config
from common import discord
from common import start, vars, price_data
from common.api_alpaca import api
import pandas as pd
# from components.Clients.Alpaca.api_alpaca import api
# import components.Clients.MetaTrader.mt5_server as mt5
from components.techanalysis import screener
import os
import glob
import random


app = Flask(__name__)
logging.basicConfig(level=logging.INFO,stream=sys.stdout,filemode="a",format='%(asctime)s %(levelname)s:%(name)s:%(message)s') #filename="logs/py_log.log"
redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})


# tracemalloc.start()
# s = None
# Declaring some variables
accountInfo = api.get_account()
order_lock = Lock()

@app.route('/portfolio/<path:path>', methods=['GET'])
def proxy_portfolio(path):
    url = f"http://portfolio-manager:5000/{path}"
    # if request.method == 'POST':
    #     response = requests.post(url, json=request.get_json())
    # else:
    response = requests.get(url, params=request.args)
    # return jsonify(response.json())

    graph_directory = 'static/data/graphs/options'

    list_of_files = glob.glob(os.path.join(graph_directory, '*.png'))

    # Check if there are any .png files
    if list_of_files:
        # Find the latest file by modification time
        latest_file = max(list_of_files, key=os.path.getmtime)
        latest_filename = os.path.basename(latest_file)
        latest_full_path = os.path.join(graph_directory, latest_filename)
        random_file = random.choice(list_of_files)   
        random_file_filename = os.path.basename(random_file)
        random_full_path = os.path.join(graph_directory, random_file_filename) 
    else:
        random_full_path = 'static/data/graphs'
        latest_full_path = 'static/data/graphs'
        print("No File Found")

    return render_template('portfolio.html', portfolio_plot=latest_full_path, asset_plot=random_full_path)

@app.route('/')
def dashboard():
    orders = api.get_orders(filter=GetOrdersRequest(status='all', limit=100, nested=True))
    accountInfo = api.get_account()
    return render_template('dashboard.html', alpaca_orders=orders, account_info=accountInfo)

@app.route('/account', methods=['GET'])
def account():
    pretty_json = json.dumps(str(accountInfo), indent=4)
    html = f"<pre>{pretty_json}</pre>"
    accountInfo = api.get_account()  
    return render_template_string(html)

@app.route('/stats', methods=['GET'])
def stats():
    metric_modules = {}
    PriceGapPc_df = price_data.randomStats(redis_client)
    print(f"\n=======================\n=======================") 
    print(PriceGapPc_df.describe())
    PriceGapPc_dict = PriceGapPc_df.to_dict(orient="dict")
    metric_modules['Price Gap Percent'] = PriceGapPc_dict
    metric_modules['Price Gap Percent Anomlies'] = PriceGapPc_df.loc[PriceGapPc_df.priceGaps_to_totalBars>PriceGapPc_df.priceGaps_to_totalBars.quantile(0.75)].copy().to_dict(orient="dict") 
    # return render_template('stats.html', metric_modules=metric_modules)
    return jsonify(metric_modules)

@app.route('/screen', methods=['GET'])
def screen():
    response = screener.test()
    return jsonify(response)

@app.route('/portfolio', methods=['GET'])
def portDisplay():
    static = 'static'
    portfolio_plot = 'portfolioperformance.png'
    asset_plot = 'assetperformance.png'
    media_1 = os.path.join(static, portfolio_plot)
    media_2 = os.path.join(static, asset_plot)
    # portfolio.graph(plot_filename=portfolio_plot)
    # da.dataCrunch(plot_filename=asset_plot)
    return render_template('portfolio.html', portfolio_plot=media_1, asset_plot=media_2)

@app.route('/strategy', methods=['GET'])
def strategyDisplay():
    graph_directory = 'static/data/graphs'

    list_of_files = glob.glob(os.path.join(graph_directory, '*.png'))

    # Check if there are any .png files
    if list_of_files:
        # Find the latest file by modification time
        latest_file = max(list_of_files, key=os.path.getmtime)
        latest_filename = os.path.basename(latest_file)
        latest_full_path = os.path.join(graph_directory, latest_filename)
        random_file = random.choice(list_of_files)   
        random_file_filename = os.path.basename(random_file)
        random_full_path = os.path.join(graph_directory, random_file_filename) 
    else:
        random_full_path = None
        latest_full_path = None
        print("No File Found")

    return render_template('portfolio.html', portfolio_plot=latest_full_path, asset_plot=random_full_path)


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

# file_path = 'logs/data.txt'
# lock_file_path = 'logs/lock.txt'
# post_buffer = queue.Queue()
# buffer_lock = threading.Lock()
# mt5_lock = Lock()
# mt5_queue = queue.Queue()

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

# def get_file_content():
#     with open(file_path, 'r') as file:
#         return file.read()

