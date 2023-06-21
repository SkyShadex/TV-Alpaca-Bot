from flask import Flask, render_template, request, abort, jsonify, render_template_string
#import alpaca_trade_api as tradeapi
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.models import Order
from alpaca.common import exceptions
import config, json, requests, subprocess, logging
from components import orderlogic, vars, discord
from components.techanalysis import screener
from commons import start
from threading import Lock

app = Flask(__name__)

# Declaring some variables
api = TradingClient(config.API_KEY, config.API_SECRET, paper=True)
accountInfo = api.get_account()
orderParams = GetOrdersRequest(status='all',limit=100,nested=True)
order_lock = Lock()

# Start Up Message.
start.startMessage(accountInfo.buying_power,accountInfo.daytrade_count)

# Making the dashboard dynamic
def fetch_orders():
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
    #return render_template_string(str(response))


@app.route('/webhook', methods=['POST'])
def webhook():
    webhook_message = json.loads(request.data)
    # Log the webhook_message
    logging.basicConfig(filename='logs/webhook.log', level=logging.INFO)
    logging.info('Webhook message received: %s', webhook_message)

    if webhook_message['passphrase'] != config.WEBHOOK_PASSPHRASE:
        return {
            'code': 'error',
            'message': 'nice try buddy'
        }
    else:
        # Declare some variable
        symbol_WH, side_WH, price_WH, qty_WH, comment_WH, orderID_WH = vars.webhook(webhook_message)

        # Trigger Received Confirmation
        content = f"Strategy Alert Triggered: {side_WH}({comment_WH}) {qty_WH} shares of {symbol_WH} @ {price_WH}."
        print(content)
        discord.message(content)
        order_lock.acquire()
        try:
            response = orderlogic.executeOrder(webhook_message)  # Execute Order with the Webhook

            if isinstance(response, Order):
                orderInfo = vars.extract_order_response(response)
                content = f"Alpaca Response: Order executed successfully. {orderInfo['qty']} of {orderInfo['symbol']} submitted at {orderInfo['submitted_at']}"
                discord.message(content)

                # Return alpaca response
                print(content)
                return jsonify(message='Order executed successfully!', orderInfo=orderInfo)            
        except exceptions.APIError as e:
            error_message = f"Alpaca Error: {str(e)} for {side_WH} order"
            discord.message(error_message)
            return jsonify(error=error_message), 500
        finally:
            order_lock.release()



#if __name__ == '__app__':
#    app.run(debug=True)