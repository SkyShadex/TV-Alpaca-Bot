import json
import logging
import os
from threading import Lock

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
from components import backtest, discord, orderlogic, portfolio, vars
from components.api_alpaca import api
from components.techanalysis import screener

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


@app.route('/mt5client', methods=['GET'])
def mt5client():
    return "Hello from Flask!"

@app.route('/mt5client', methods=['POST'])
def mt5client_post():
    # Code for handling the POST request goes here
    return 'This is the POST method response'


@app.route('/portfolio', methods=['GET'])
def portDisplay():
    plot_filename = 'portfolioperformance.png'
    portfolio.graph(plot_filename)
    backtest.collectOrders()
    return render_template('portfolio.html', plot_filename=plot_filename)


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

            good_errors = ["position not found", "order not found", "is not active", "asset not found"]
            if any(error in str(e) for error in good_errors):
                return jsonify(error=error_message), 200
            else:
                return jsonify(error=error_message), 500


# if __name__ == '__app__':
#    app.run(debug=True)
