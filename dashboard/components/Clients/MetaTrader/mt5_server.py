import datetime
from commons import vars

orderHold = []
def main(webhook_message):
    # Extract variables from webhook_message
    symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, stratID_WH = vars.webhook(webhook_message)
    # Store the extracted variables in a local file
    store_data(symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, stratID_WH)
    return orderHold.pop(0)

def store_data(symbol, side, price, quantity, comment, stratID):  
    # current_datetime = datetime.datetime.utcnow()
    # timestamp = current_datetime.timestamp()

    current_datetime = datetime.datetime.utcnow()
    
    # Round the timestamp to the nearest 30 seconds
    rounded_seconds = round(current_datetime.second / 30) * 30
    rounded_timedelta = datetime.timedelta(seconds=rounded_seconds)
    rounded_datetime = current_datetime - datetime.timedelta(seconds=current_datetime.second, microseconds=current_datetime.microsecond) + rounded_timedelta
    
    timestamp = rounded_datetime.timestamp()

    order = f"Timestamp: {timestamp}, Symbol: {symbol}, Side: {side}, Price: {price}, Quantity: {quantity}, Comment: {comment}, Order ID: {stratID}"
    orderHold.append(order)  # Append the order dictionary to the array
    #print("2")
    print(order)
    # You can also write the order to a file here if needed
    with open('logs/data.txt', 'w+') as file:
        # Write the data to the file
        file.write(order)
    #    file.write("\n")



def read_data():
    return
