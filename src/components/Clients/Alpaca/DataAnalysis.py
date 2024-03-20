import pandas as pd
import os, time
import matplotlib.pyplot as plt
from alpaca.trading.requests import GetOrdersRequest
import time
from commons import vars
from components.Clients.Alpaca.api_alpaca import api
import pandas as pd
import numpy as np
import datetime as dt
import pytz


def collectOrders():
    end_date = dt.datetime.combine(dt.date.today(), dt.datetime.min.time())
    order_params = GetOrdersRequest(status='closed', until=end_date, limit=500, nested=False) # TODO: Clean later
    all_orders = []

    try:
        while True:
            orders = api.get_orders(filter=order_params)
            if not orders:
                break
            
            df_data = [vars.extract_order_response(order) for order in orders if order.status.value == 'filled'] # TODO: Clean later
            all_orders.extend(df_data)
            
            # Update the until_date for the next iteration
            if df_data:
                created_at_values = pd.to_datetime([order['created_at'] for order in df_data])
                until_date = min(created_at_values)
            else:
                # If there are no orders in the current batch, break the loop
                break

            order_params.until = until_date
            time.sleep(1) # sleep to avoid API rate limits
        
        df = pd.DataFrame(all_orders)
        print(df.head())
        df.to_csv('logs/orders.csv', index=False)
        return df
    
    except Exception as e:
        print(f"Error fetching orders: {e}")


def dataCrunch(plot_filename):
    collectOrders()
    csv_path = '/workspaces/TV-Alpaca-Bot/src/logs/orders.csv'

    # Wait until the CSV file is done writing
    while not os.path.exists(csv_path):
        time.sleep(1)  # Adjust the sleep duration as needed
    
    df = pd.read_csv(csv_path)

    # Step 1: Calculate total amount for each row and add it to the dataframe
    # df['position_value'] = df['filled_qty'] * df['filled_avg_price']
    df['position_value'] = np.where(df['side'] == 'sell', -1, 1) * df['filled_qty'] * df['filled_avg_price']

    symbols = df['symbol'].unique()
    closed_positions = []

    for symbol in symbols:
        symbol_df = df[df['symbol'] == symbol]

        # # Check if there is an open position
        # if symbol_df['side'].nunique() == 1:
        #     continue  # Skip this symbol if it has an open position

        # Step 2: Calculate total amounts for sell and buy orders
        # sell_amount = symbol_df[symbol_df['side'] == 'sell']['position_value'].sum()
        total_value = symbol_df['position_value'].sum()
        sell_qty = symbol_df[symbol_df['side'] == 'sell']['filled_qty'].sum()
        buy_qty = symbol_df[symbol_df['side'] == 'buy']['filled_qty'].sum()
        # Step 3: Calculate cumulative profit/loss for the symbol
        pnl = total_value
        net_qty = sell_qty - buy_qty

        if net_qty == 0:
            closed_positions.append((symbol, pnl, net_qty, sell_qty, buy_qty))
        else:
            print(total_value,sell_qty,buy_qty)
 
    # Create a DataFrame for closed positions
    closed_positions_df = pd.DataFrame(
        closed_positions,
        columns=['symbol', 'pnl', 'net_qty', 'total_sell_qty', 'total_buy_qty'])
    df_sorted = closed_positions_df.sort_values('pnl')

    # Step 5: Sort the DataFrame by pnl in descending order
    closed_positions_df_sorted = closed_positions_df.sort_values('pnl', ascending=False)

    # Step 6: Calculate the total pnl of all symbols
    total_pl = closed_positions_df_sorted['pnl'].sum()

    # Calculate the total P/L of all symbols
    total_pl = df_sorted['pnl'].sum()

    # Plot the dataframe as a bar graph
    plt.figure(figsize=(15, 15))
    cmap = 'RdYlGn'
    bars = plt.barh(df_sorted['symbol'], df_sorted['pnl'], color=plt.cm.get_cmap(cmap)(0.5 + df_sorted['pnl'] / df_sorted['pnl'].max() / 2)) # TODO: Clean later

    max_abs_pnl = max(abs(df_sorted['pnl']))*1.2
    plt.xlim([-max_abs_pnl, max_abs_pnl])
    plt.axvline(0, color='black', linestyle='--', linewidth=1)
    plt.xlabel('P/L')
    plt.ylabel('Symbol')
    plt.title('Closed Positions P/L')
    plt.grid(axis='x', linestyle='--', alpha=0.7)
    plt.tight_layout()

    # # Add P/L values to the bars
    # for bar in bars:
    #     width = bar.get_width()
    #     if width >= 0:
    #         plt.text(width, bar.get_y() + bar.get_height() / 2, f'{width:.2f}', ha='left', va='center')
    #     else:
    #         plt.text(width, bar.get_y() + bar.get_height() / 2, f'{width:.2f}', ha='right', va='center')

    # Print the total P/L in the top right corner
    plt.text(0.95, 0.15, f'Total P/L: {total_pl:.2f}', ha='right', va='top', transform=plt.gca().transAxes)

    static_path = 'static'
    file_path = os.path.join(static_path, plot_filename)
    plt.savefig(file_path)