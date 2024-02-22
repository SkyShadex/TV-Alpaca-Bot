import pandas as pd
import os, time
import matplotlib.pyplot as plt
from alpaca.trading.requests import GetOrdersRequest
import time
from commons import vars
from components.Clients.Alpaca.api_alpaca import api
import pandas as pd



def collectOrders():
    orderParams = GetOrdersRequest(status='closed', limit=500, nested=False) # type: ignore
    orders = api.get_orders(filter=orderParams)
    
    df_data = [vars.extract_order_response(order) for order in orders if order.status.value == 'filled'] # type: ignore
    df = pd.DataFrame(df_data)
    print(df)
    df.to_csv('logs/orders.csv', index=False)
    return df

def dataCrunch(plot_filename):
    collectOrders()
    csv_path = '/workspaces/TV-Alpaca-Bot/src/logs/orders.csv'

        # Wait until the CSV file is done writing
    while not os.path.exists(csv_path):
        time.sleep(1)  # Adjust the sleep duration as needed
    
    df = pd.read_csv(csv_path)

    # Step 1: Calculate total amount for each row and add it to the dataframe
    df['amount'] = df['filled_qty'] * df['filled_avg_price']

    symbols = df['symbol'].unique()
    closed_positions = []

    for symbol in symbols:
        symbol_df = df[df['symbol'] == symbol]

        # Check if there is an open position
        if symbol_df['side'].nunique() == 1:
            continue  # Skip this symbol if it has an open position

        # Step 2: Calculate total amounts for sell and buy orders
        sell_amount = symbol_df[symbol_df['side'] == 'sell']['amount'].sum()
        buy_amount = symbol_df[symbol_df['side'] == 'buy']['amount'].sum()
        sell_qty = symbol_df[symbol_df['side'] == 'sell']['filled_qty'].sum()
        buy_qty = symbol_df[symbol_df['side'] == 'buy']['filled_qty'].sum()

        # Step 3: Calculate cumulative profit/loss for the symbol
        pnl = sell_amount - buy_amount
        net_qty = sell_qty - buy_qty

        closed_positions.append((symbol, pnl, net_qty, sell_qty, buy_qty, sell_amount, buy_amount))
 
    # Create a DataFrame for closed positions
    closed_positions_df = pd.DataFrame(
        closed_positions,
        columns=['symbol', 'pnl', 'net_qty', 'total_sell_qty', 'total_buy_qty', 'total_sell_amount', 'total_buy_amount'])
    df_sorted = closed_positions_df.sort_values('pnl', ascending=False)

    # Step 5: Sort the DataFrame by pnl in descending order
    closed_positions_df_sorted = closed_positions_df.sort_values('pnl', ascending=False)

    # Step 6: Calculate the total pnl of all symbols
    total_pl = closed_positions_df_sorted['pnl'].sum()


    # Calculate the total P/L of all symbols
    total_pl = df_sorted['pnl'].sum()

    # Plot the dataframe as a bar graph
    plt.figure(figsize=(10, 6))
    bars = plt.barh(df_sorted['symbol'], df_sorted['pnl'])
    plt.xlabel('P/L')
    plt.ylabel('Symbol')
    plt.title('Closed Positions P/L')
    plt.tight_layout()

    # Add P/L values to the bars
    for bar in bars:
        width = bar.get_width()
        if width >= 0:
            plt.text(width, bar.get_y() + bar.get_height() / 2, f'{width:.2f}', ha='left', va='center')
        else:
            plt.text(width, bar.get_y() + bar.get_height() / 2, f'{width:.2f}', ha='right', va='center')

    # Print the total P/L in the top right corner
    plt.text(0.95, 0.95, f'Total P/L: {total_pl:.2f}', ha='right', va='top', transform=plt.gca().transAxes)


    static_path = 'static'
    # Combine the strings to create the file path
    file_path = os.path.join(static_path, plot_filename)

    # Save the plot using the file path
    plt.savefig(file_path)