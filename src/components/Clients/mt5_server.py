import datetime
from components import vars


def main(webhook_message):
    # Extract variables from webhook_message
    symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, orderID_WH = vars.webhook(webhook_message)

    # Store the extracted variables in a local file
    store_data(symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, orderID_WH)


def store_data(symbol, side, price, quantity, comment, orderID):
    
    current_datetime = datetime.datetime.utcnow()
    timestamp = current_datetime.timestamp()

    # Open the file in write mode
    with open('logs/data.txt', 'w+') as file:
        # Write the data to the file
        file.write(f"Timestamp: {timestamp}, Symbol: {symbol}, Side: {side}, Price: {price}, Quantity: {quantity}, Comment: {comment}, Order ID: {orderID}")


def read_data():
    return