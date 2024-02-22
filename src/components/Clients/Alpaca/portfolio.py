import requests, config, os
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Set Alpaca Trading API
base_url = 'https://paper-api.alpaca.markets'
endpoint = '/v2/account/portfolio/history'
headers = {
    'APCA-API-KEY-ID': config.API_KEY,
    'APCA-API-SECRET-KEY': config.API_SECRET
}

# Date range for the portfolio request
start_date = datetime(2023, 12, 1)


def get_params(start_date, end_date=datetime.today()):
    # Calculate the duration of the date range in days
    duration = (end_date - start_date).days
    print(duration)

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
    print(params)
    return params

def request_portfolio_history():
    params=get_params(start_date)
    response = requests.get(
        base_url + endpoint,
        params,
        headers=headers #type: ignore
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


