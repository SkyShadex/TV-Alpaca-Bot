
def webhook_vars(webhook_message):
        symbol_WH = webhook_message['ticker']
        side_WH = webhook_message['strategy']['order_action']
        price_WH= webhook_message['strategy']['order_price']
        quantity_WH = webhook_message['strategy']['order_contracts']
        comment_WH = webhook_message['strategy']['comment']
        orderID_WH = webhook_message['strategy']['order_id']

        return symbol_WH,side_WH,price_WH,quantity_WH,comment_WH,orderID_WH