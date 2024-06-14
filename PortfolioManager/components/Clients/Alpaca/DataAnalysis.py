import pandas as pd
import os, time
import matplotlib.pyplot as plt
from alpaca.trading.requests import GetOrdersRequest
from alpaca.broker.requests import GetAccountActivitiesRequest
import time
from common import vars
from common.api_alpaca import api
from alpaca.broker.client import BrokerClient
import pandas as pd
import numpy as np
import datetime as dt
import pytz
import config
import requests
import seaborn as sns


def collectActivity():
    url_base = "https://paper-api.alpaca.markets/v2/account/activities/FILL"

    headers = {
        "accept": "application/json",
        "APCA-API-KEY-ID": config.API_KEY,
        "APCA-API-SECRET-KEY": config.API_SECRET
    }

    activities = []
    page_token = None

    while True:
        # Construct the URL with a page_token if it exists
        url = f"{url_base}?direction=asc"
        if page_token:
            url += f"&page_token={page_token}"

        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            activities.extend(data)

            # Check if data is empty (no more pages)
            if not data:
                break

            # Extract last id from the last item in the response for the next page_token
            last_activity = data[-1]
            page_token = last_activity['id']
        else:
            print("Failed to fetch data:", response.status_code)
            return None

    df = pd.DataFrame(activities)
    if not df.empty:
        df['transaction_time'] = pd.to_datetime(df['transaction_time'],utc=True)
        df.set_index('transaction_time', inplace=True)
        return df
    else:
        return pd.DataFrame()

def calcPerformance():
    current_time = dt.datetime.now(pytz.utc)
    activity_df = collectActivity()
    if activity_df is not None:
        # Convert price to numeric and ensure 'qty' is an integer
        activity_df = activity_df.loc[(activity_df['type']=='fill')]
        activity_df['price'] = pd.to_numeric(activity_df['price'], errors='coerce')
        activity_df['qty'] = activity_df['qty'].astype(float)
        activity_df.sort_values(by=['symbol', 'transaction_time'],ascending=False, inplace=True)    

        activity_df = activity_df.loc[(activity_df.symbol.str.len()>6)]
        # Calculate the balance based on the side of the transaction
        activity_df['balance'] = np.where(activity_df['side'] == 'sell',
                                          abs(activity_df['price'] * activity_df['qty'] * 100),
                                          -(activity_df['price'] * activity_df['qty'] * 100))
        
        # print(activity_df[['symbol', 'price', 'side', 'balance']].head(30))
        price_filtered = activity_df.loc[(activity_df['price'] < 1.0) & (activity_df['side'] == 'buy')]
        cull_symbols = price_filtered.symbol.unique()

        symbols = activity_df.symbol.unique()

        remaining_symbols = list(set(symbols) - set(cull_symbols))
        remaining_symbols = np.array(remaining_symbols)

        pnl_data = []
        current_holdings = []
        for symbol in symbols:
            activity_current = activity_df.loc[(activity_df.symbol==symbol)]
            sells = activity_current.loc[activity_df['side'] == 'sell']
            if sells.shape[0] == 0:
                continue

            # latest_sell_time = sells.index.max()
            # if latest_sell_time < (current_time - dt.timedelta(days=7)):
            #     continue 

            buys = activity_current.loc[activity_df['side'] == 'buy']
            if buys.shape[0] != sells.shape[0]:
                buys = buys.sort_index(ascending=False)
                current_holdings.append(buys.iloc[0])
                buys = buys.iloc[1:]

            contract_symbol = symbol
            base_symbol = api.parseOptSym(contract_symbol)[0]
            buy_sum = abs(buys.balance.sum())
            if buy_sum == 0.0:
                continue
            sell_sum = abs(sells.balance.sum())
            avg_contract = buys.price.mean()

            pnl_data.append({
                'symbol': symbol,
                'base_symbol': base_symbol,
                'buy_sum': buy_sum,
                'sell_sum': sell_sum,
                'Returns': (sell_sum / buy_sum) - 1,
                'Avg_Price': avg_contract
                })

        try:
            current_holdings_df = pd.concat(current_holdings, axis=1).T

            pnl_df = pd.DataFrame(pnl_data)
            pnl_df['net_PnL'] = pnl_df['sell_sum'] - pnl_df['buy_sum']

            grouped_data = pnl_df.groupby('base_symbol').agg({
                'buy_sum': 'sum',
                'sell_sum': 'sum',
                'Avg_Price': 'mean'
                }).reset_index()
            grouped_data['Returns'] = (grouped_data['sell_sum'] / grouped_data['buy_sum']) - 1
            grouped_data['net_PnL'] = grouped_data['sell_sum'] - grouped_data['buy_sum']

            pnl_description = pnl_df[["base_symbol"]].describe()
            grouped_stats = grouped_data[["Returns", "net_PnL", "Avg_Price"]].describe().round(2)
            estimated_pl = grouped_data.net_PnL.sum()
            estimated_holdings = current_holdings_df.balance.abs().sum()

            print(f"""
            //================//
            Base Symbol Description:
            {pnl_description.to_string()}

            //================//
            Options Returns Stats:
            {grouped_stats.to_string()}

            //================//
            Estimated P/L: {estimated_pl:.2f} 
            Estimated Current Holdings: {estimated_holdings:.2f}
            //================//
            """)
            plotOptionsMetrics(grouped_data)
            
        except Exception as e:
            print(e)


def plotOptionsMetrics(grouped_data):
    # Create a figure with two subplots
    current_time = dt.datetime.now(pytz.utc)
    fig = plt.figure(figsize=(20, 20))
    gs = fig.add_gridspec(2, 2)
    
    # Create quantile categories with range labels
    quantile_bins = pd.qcut(grouped_data['Avg_Price'], q=4)
    grouped_data['Avg_Price_Quantiles'] = quantile_bins

    # Create string labels for the quantile ranges
    quantile_labels = quantile_bins.cat.categories
    grouped_data['Avg_Price_Quantiles'] = grouped_data['Avg_Price_Quantiles'].apply(lambda x: f'{x.left:.2f}-{x.right:.2f}')

    ax1 = fig.add_subplot(gs[0, 0])
    sns.violinplot(data=grouped_data, x='Avg_Price_Quantiles', y='Returns', inner="box", linewidth=1.5, ax=ax1, color="skyblue")
    ax1.axhline(y=0, color='red', linestyle='--', linewidth=0.5, alpha=0.75)
    ax1.set_title("Options Returns (%)")
    ax1.set_ylabel("Returns (%)")

    ax2 = fig.add_subplot(gs[0, 1])
    sns.violinplot(data=grouped_data, x='Avg_Price_Quantiles', y='net_PnL', inner="box", linewidth=1.5, ax=ax2, color="orange")
    ax2.axhline(y=0, color='red', linestyle='--', linewidth=0.5, alpha=0.75)
    ax2.set_title("Options Returns ($)")
    ax2.set_ylabel("Returns ($)")

    ax3 = fig.add_subplot(gs[1, :])
    ax3.scatter(grouped_data['Avg_Price'], grouped_data['Returns'])
    sns.regplot(data=grouped_data, x='Avg_Price', y='Returns', ax=ax3, scatter=False, color='red', line_kws={'linewidth': 1})
    for i, txt in enumerate(grouped_data['base_symbol']):
        ax3.annotate(txt, (grouped_data['Avg_Price'][i], grouped_data['Returns'][i]))
    ax3.set_title("Returns vs. Avg_Price")
    ax3.set_ylabel("Returns (%)")
    ax3.set_xlabel("Avg_Price ($)")

    fig.suptitle(f"Options Performance Analysis. Estimated P/L: {grouped_data.net_PnL.sum():.2f}", fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    static_path = 'data/graphs'
    os.makedirs(static_path, exist_ok=True)
    filename = f'options_subplots_dviz_{current_time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
    file_path = os.path.join(static_path, filename)
    plt.savefig(file_path)

    plt.close()

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
                created_at_values = pd.to_datetime([order['created_at'] for order in df_data],utc=True)
                until_date = min(created_at_values)
            else:
                # If there are no orders in the current batch, break the loop
                break

            order_params.until = until_date
            time.sleep(1) # sleep to avoid API rate limits
        
        df = pd.DataFrame(all_orders)
        # print(df.head())
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
        # else:
            # print(total_value,sell_qty,buy_qty)
 
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