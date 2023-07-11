import json
import logging
import os
import time
from threading import Lock, Thread

import requests
from alpaca.common import exceptions
# import alpaca_trade_api as tradeapi
from alpaca.trading.client import TradingClient
from alpaca.trading.models import Order
from alpaca.trading.requests import GetOrdersRequest
from flask import (Flask, abort, jsonify, render_template,
                   render_template_string, request)

import config
from commons import start
from components import discord, orderlogic, portfolio, vars, Clients
from components.api_alpaca import api
from components.RiskManager import backtest
import components.Clients.mt5_server as mt5
from components.techanalysis import screener
from components.RiskManager import DataAnalysis as da

app = Flask(__name__)

# Declaring some variables
accountInfo = api.get_account()
order_lock = Lock()

# Start Up Message.
start.startMessage(accountInfo.buying_power, accountInfo.non_marginable_buying_power, accountInfo.daytrade_count)

# Making the dashboard dynamic
def fetch_orders():
    orderParams = GetOrdersRequest(status='all', limit=100, nested=True)
    orders = api.get_orders(filter=orderParams)
    return orders


def fetch_account_info():
    account_info = api.get_account()
    return account_info



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


file_path = 'logs/data.txt'
lock_file_path = 'logs/lock.txt'
post_buffer = []

def process_post_requests():
    while True:
        if post_buffer:
            webhook_message = post_buffer.pop(0)
            logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
            logging.info('Webhook message received: %s', webhook_message)

            if webhook_message['passphrase'] != config.WEBHOOK_PASSPHRASE:
                continue

            # Check if the lock file exists
            if os.path.isfile(lock_file_path):
                continue

            # Create the lock file
            with open(lock_file_path, 'w') as lock_file:
                lock_file.write('locked')

            # Process and Store Value
            mt5.main(webhook_message)

            if webhook_message.get('strategyid'):
                strategyid_WH = webhook_message['strategyid']
            else:
                strategyid_WH = "Missing ID"

            symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, orderID_WH = vars.webhook(webhook_message)
            content = f"Strategy Alert [MT5]: {side_WH}({comment_WH}) -|- {symbol_WH}: {quantity_WH} units @ {round(price_WH,3)} -|- Strategy ID: {strategyid_WH}"
            discord.message(content)
            response = "Response Recorded."

            # Remove the lock file
            if os.path.isfile(lock_file_path):
                os.remove(lock_file_path)

        # Sleep for a while before checking the buffer again
        time.sleep(1)

# Start the background process for processing POST requests
post_thread = Thread(target=process_post_requests)
post_thread.start()

@app.route('/mt5client', methods=['GET'])
def mt5client():
    # Check if the lock file exists
    if os.path.isfile(lock_file_path):
        return jsonify({'message': 'File is being updated. Try again later.'}), 503

    # Check if the file exists
    if not os.path.isfile(file_path):
        response = {'error': 'File not found'}
        return json.dumps(response), 404

    # Read the content of the text file
    with open(file_path, 'r') as file:
        file_content = file.read()

    # Create a JSON response with the file content
    response = {'file_content': file_content}

    # Return the JSON response
    return json.dumps(response)

@app.route('/mt5client', methods=['POST'])
def mt5client_post():
    webhook_message = json.loads(request.data)
    logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
    logging.info('Webhook message received: %s', webhook_message)

    if webhook_message['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return {'code': 'error', 'message': 'nice try buddy'}

    # Add the request data to the post_buffer
    post_buffer.append(webhook_message)

    response = "Request Buffered."

    return jsonify(response), 200



@app.route('/portfolio', methods=['GET'])
def portDisplay():
    portfolio_plot = 'portfolioperformance.png'
    asset_plot = 'assetperformance.png'
    portfolio.graph(plot_filename=portfolio_plot)
    backtest.collectOrders()
    da.dataCrunch(plot_filename=asset_plot)
    return render_template('portfolio.html', portfolio_plot=portfolio_plot, asset_plot=asset_plot)


@app.route('/webhook', methods=['POST'])
def webhook():
    webhook_message = json.loads(request.data)
    logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
    logging.info('Webhook message received: %s', webhook_message)

    if webhook_message['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return {'code': 'error', 'message': 'nice try buddy'}

    if webhook_message.get('strategyid'):
        strategyid_WH = webhook_message['strategyid']
    else:
        strategyid_WH = "Missing ID"

    symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, orderID_WH = vars.webhook(
        webhook_message)
    content = f"Strategy Alert: {side_WH}({comment_WH}) -|- {symbol_WH}: {quantity_WH} units @ {round(price_WH,3)} -|- Strategy ID: {strategyid_WH}"
    #print(content)
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

        except exceptions.APIError as e:
            error_message = f"Alpaca Error: {str(e)} for {side_WH} order"
            discord.message(error_message)

            good_errors = ["position not found", "order not found", "is not active", "asset not found", "not tradable", "insufficient balance for USD"]
            if any(error in str(e) for error in good_errors):
                return jsonify(error=error_message), 200
            else:
                return jsonify(error=error_message), 500


# if __name__ == '__app__':
#    app.run(debug=True)
