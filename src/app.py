import json
import logging
import os
import time
import queue
import threading
from flask_redis import FlaskRedis
import redis
import gc
from threading import Lock, Thread
import tracemalloc
import requests
import random
from alpaca.common import exceptions
# import alpaca_trade_api as tradeapi
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Order
from alpaca.trading.requests import GetOrdersRequest
from flask import (Flask, abort, jsonify, render_template,
                   render_template_string, request)
from flask_caching import Cache


import config
from commons import start
from components import discord, orderlogic, portfolio, vars
from components.api_alpaca import api
from components.RiskManager import backtest, port_rebal
import components.Clients.mt5_server as mt5
from components.techanalysis import screener
from components.RiskManager import DataAnalysis as da

app = Flask(__name__)
redis_client = redis.Redis(host='redis-stack-server', port=6379, decode_responses=True)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

# Declaring some variables
accountInfo = api.get_account()
order_lock = Lock()

tracemalloc.start()
s = None

# Start Up Message.
start.startMessage(accountInfo.buying_power, accountInfo.non_marginable_buying_power, accountInfo.daytrade_count) # type: ignore
port_rebal.alpaca_rebalance()

def check_alpaca_status():
    if not api.check_alpaca_status():
        return jsonify({"error": "Alpaca API is currently unavailable"}), 503

######## This spam's the API and causes rate limiting...
#@app.before_request
#def before_request():
#    # List of routes to exclude from alpaca_status check
#    excluded_routes = ['/mt5client']

#    if request.endpoint not in excluded_routes:
#        check_alpaca_status()


# Making the dashboard dynamic
def fetch_orders():
    orderParams = GetOrdersRequest(status='all', limit=100, nested=True) # type: ignore
    orders = api.get_orders(filter=orderParams)
    port_rebal.alpaca_rebalance()
    return orders


def fetch_account_info():
    return accountInfo



# Flask Routes
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
    backtest.collectOrders()
    da.dataCrunch(plot_filename=asset_plot)
    return render_template('portfolio.html', portfolio_plot=portfolio_plot, asset_plot=asset_plot)

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

# Start the background process for processing POST requests
post_thread = Thread(target=process_post_requests)
post_thread.start()

def get_file_content():
    with open(file_path, 'r') as file:
        return file.read()

@app.route('/mt5client', methods=['GET'])
def mt5client():
    # Check if there are orders available
    data = redis_client.lpop('orderHold')
    if data is None:
        #olddata = get_file_content()
        olddata = "No Order Found"
        response = {'message': olddata}
        return jsonify(response), 404
    else:
        response = {'file_content': data}
        return jsonify(response), 200

@app.route('/webhook', methods=['POST']) # type: ignore
def webhook():
    payload = request.data.decode("utf-8")
    start_index = payload.find('{')
    end_index = payload.rfind('}')

    if start_index == -1 or end_index == -1 or end_index <= start_index:
        return {'code': 'error', 'message': 'Invalid payload'}
    extrainfo = payload[:start_index].strip()
    cleaned_payload = payload[start_index:end_index+1]

    webhook_message = json.loads(cleaned_payload)

    #logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
    #logging.info('Webhook message received: %s', webhook_message)

    if webhook_message['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return {'code': 'error', 'message': 'nice try buddy'}
    
    if "mt5" in extrainfo:
        with buffer_lock:
            post_buffer.put(webhook_message)
            response = "Request Buffered."
            return jsonify(response), 200
    else:
        port_rebal.alpaca_rebalance()

    symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, stratID_WH = vars.webhook(
        webhook_message)
    content = f"Strategy Alert: {side_WH}({comment_WH}) -|- {symbol_WH}: {quantity_WH} units @ {round(price_WH,3)} -|- Strategy ID: {stratID_WH}"
    discord.message(content)

    with order_lock:
        try:
            response = orderlogic.executeOrder(webhook_message)

            if isinstance(response, Order):
                orderInfo = vars.extract_order_response(response)
                content = f"Alpaca: Order executed successfully -|- {orderInfo['qty']} units of {orderInfo['symbol']} -|- Timestamp: {orderInfo['submitted_at']}"
                discord.message(content)
                print(content)
                return jsonify(message='Order executed successfully!', orderInfo=orderInfo)

        # Error Handling
        except exceptions.APIError as e: 
            error_message = f"Alpaca Error: {str(e)} for {side_WH} order"
            discord.message(error_message)

            good_errors = ["position not found", "order not found", "is not active", "asset not found", "not tradable", "insufficient balance for USD"]
            if any(error in str(e) for error in good_errors):
                return jsonify(error=error_message), 200
            else:
                return jsonify(error=error_message), 500

if __name__ == '__app__':
    app.run(host='0.0.0.0', port=5000,debug=False)
