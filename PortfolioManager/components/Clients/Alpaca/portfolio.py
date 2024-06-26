import requests, config, os
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import pandas as pd
from alpaca.trading.models import Position, Order
import logging

# Set Alpaca Trading API
base_url = 'https://paper-api.alpaca.markets'
base_url2 = 'https://api.alpaca.markets'
endpoint = '/v2/account/portfolio/history'
headers = {
    'APCA-API-KEY-ID': config.API_KEY,
    'APCA-API-SECRET-KEY': config.API_SECRET
}
headers2 = {
    'APCA-API-KEY-ID': config.API_KEY_PROD,
    'APCA-API-SECRET-KEY': config.API_SECRET_PROD
}

# Date range for the portfolio request
start_date = datetime(2024, 4, 1)

def parse_positions(positions,commissions=0.5*2*3):
    formatted_data = []
    try:
        for position in positions:
            data = {
                'asset_id': str(position.asset_id),
                'asset_class' : str(position.asset_class),
                'symbol': str(position.symbol),
                'qty': float(position.qty),
                'side': str(position.side),
                'avg_entry_price': float(position.avg_entry_price),
                'market_value': float(position.market_value) if position.market_value is not None else 0.0,
                'cost_basis': float(position.cost_basis),
                'unrealized_pl': float(position.unrealized_pl) if position.unrealized_pl is not None else 0.0,
                'unrealized_plpc': float(position.unrealized_plpc) if position.unrealized_plpc is not None else 0.0,
                'unrealized_intraday_pl': float(position.unrealized_intraday_pl) if position.unrealized_intraday_pl is not None else 0.0,
                'unrealized_intraday_plpc': float(position.unrealized_intraday_plpc) if position.unrealized_intraday_plpc is not None else 0.0,
                'current_price': float(position.current_price) if position.current_price is not None else 0.0,
                'lastday_price': float(position.lastday_price) if position.lastday_price is not None else 0.0,
                'change_today': float(position.change_today) if position.change_today is not None else 0.0,
                'swap_rate': float(position.swap_rate) if position.swap_rate is not None else 0.0,
                'avg_entry_swap_rate': float(position.avg_entry_swap_rate) if position.avg_entry_swap_rate is not None else 0.0,
                'usd': float(position.usd) if position.usd is not None else 0.0,
                'qty_available': float(position.qty_available)
            }
            formatted_data.append(data)
    except Exception as e:
        logging.exception(f"{data}: {e}")

    posdf = pd.DataFrame(formatted_data)
    numeric_cols = ['qty', 'market_value', 'cost_basis','avg_entry_price', 'unrealized_pl', 
                    'unrealized_plpc', 'unrealized_intraday_pl', 
                    'unrealized_intraday_plpc', 'current_price', 
                    'lastday_price', 'change_today', 'qty_available']
    posdf[numeric_cols] = posdf[numeric_cols].apply(pd.to_numeric, errors='coerce')
    posdf['symbol'] = posdf['symbol'].astype(str)
    posdf['side'] = posdf['side'].astype(str)
    posdf['breakeven'] = ((posdf['cost_basis']/posdf['qty'])+commissions)*posdf['qty']
    posdf['breakeven_per_unit'] = (posdf.breakeven/(100*posdf.qty))
    posdf['cost_per_unit'] = (posdf['cost_basis']/posdf['qty'])/100
    posdf.sort_values('unrealized_plpc',ascending=False,inplace=True)
    return posdf

def parse_orders(orders):
    formatted_order = []
    for order in orders:
        data = {
            'id': order.id,
            # 'client_order_id': order.client_order_id,
            # 'created_at': order.created_at,
            # 'updated_at': order.updated_at,
            'submitted_at': order.submitted_at,
            'filled_at': order.filled_at,
            'expired_at': order.expired_at,
            'canceled_at': order.canceled_at,
            'failed_at': order.failed_at,
            # 'replaced_at': order.replaced_at,
            # 'replaced_by': order.replaced_by,
            # 'replaces': order.replaces,
            # 'asset_id': order.asset_id,
            'symbol': order.symbol,
            'qty': order.qty,
            'filled_qty': order.filled_qty,
            'filled_avg_price': order.filled_avg_price,
            'order_class': order.order_class,
            'order_type': order.order_type,
            'side': order.side,
            'time_in_force': order.time_in_force,
            'limit_price': order.limit_price,
            # 'stop_price': order.stop_price,
            'status': order.status,
            'extended_hours': order.extended_hours,
            # 'legs': order.legs,
            # 'trail_percent': order.trail_percent,
            # 'trail_price': order.trail_price,
            # 'hwm': order.hwm
            # Add other attributes as needed
        }
        formatted_order.append(data)
    if orders:
        order_df = pd.DataFrame(formatted_order)
        order_df.id = order_df.id.astype(str)
        order_df.symbol = order_df.symbol.astype(str)
        order_df.status = order_df.status.astype(str)
        order_df.submitted_at = pd.to_datetime(order_df['submitted_at'], utc=True)
        order_df.filled_at = pd.to_datetime(order_df['filled_at'], utc=True)
        order_df.expired_at = pd.to_datetime(order_df['expired_at'], utc=True)
        order_df.canceled_at = pd.to_datetime(order_df['canceled_at'], utc=True)
        order_df.failed_at = pd.to_datetime(order_df['failed_at'], utc=True)
        return order_df

def get_params(start_date, end_date=datetime.today()):
    # Calculate the duration of the date range in days
    duration = (end_date - start_date).days
    # print(duration)

    if duration <= 30:
        periodPD = '{}D'.format(duration)
    elif duration <= 90:
        periodPD = '{}W'.format(round(duration/7))
    else:
        periodPD = '{}M'.format(round(duration/30))

    if periodPD.endswith('D'):
        unitPD = '15Min'
    else:
        unitPD = '1D'

    # Set the parameters for the request
    params = {
        'period': periodPD,
        'timeframe': unitPD
    }
    # print(params)
    return params

def request_portfolio_history():
    params=get_params(start_date)
    response = requests.get(
        base_url2 + endpoint,
        params,
        headers=headers2 #type: ignore
    )

    if response.status_code == 200:
        portfolio_history = response.json()
        # Reformat the timestamps
        timestamps = portfolio_history['timestamp']
        formatted_timestamps = []

        for timestamp in timestamps:
            if params['period'].endswith('D'):
                formatted_timestamp = datetime.fromtimestamp(timestamp).strftime('%m-%d-%Y %H:%M:%S')
            else:
                formatted_timestamp = datetime.fromtimestamp(timestamp).strftime('%m-%d-%Y')
            formatted_timestamps.append(formatted_timestamp)

        portfolio_history['timestamp'] = formatted_timestamps

        # Return the portfolio history data
        return portfolio_history
    else:
        # Handle the case when the request was not successful
        return {'error': response.text}
    
def graph(plot_filename):
    portfolio_history = request_portfolio_history()
    # Extract the necessary data for plotting
    
    # Filter out zero equity values
    non_zero_indices = [i for i, value in enumerate(portfolio_history['equity']) if value != 0]
    
    # Extract the necessary data for plotting based on non-zero indices
    timestamps = [portfolio_history['timestamp'][i] for i in non_zero_indices]
    equity = [portfolio_history['equity'][i] for i in non_zero_indices]
    profit_loss = [portfolio_history['profit_loss'][i] for i in non_zero_indices]
    profit_loss_pct = [portfolio_history['profit_loss_pct'][i] for i in non_zero_indices]

    # Plot the equity
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, equity, label='Equity')
    plt.xlabel('Timestamp')
    plt.ylabel('Equity')
    plt.title('Portfolio Equity')
    plt.legend()


    # Alternatively, skip every other label
    num_ticks = len(timestamps)
    display_ticks = 10
    plt.xticks(range(len(timestamps)), timestamps, rotation=60, fontsize=6)
    for i, label in enumerate(plt.gca().xaxis.get_ticklabels()):
        if i % (num_ticks // display_ticks) == 0:
            label.set_visible(True)
        else:
            label.set_visible(False)

    static_path = 'static'
    # Combine the strings to create the file path
    file_path = os.path.join(static_path, plot_filename)

    # Save the plot using the file path
    plt.savefig(file_path)


