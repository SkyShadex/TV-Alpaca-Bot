import requests, config, os, datetime
import matplotlib.pyplot as plt

# Set the base URL for the Alpaca Trading API
base_url = 'https://paper-api.alpaca.markets'

# Set the endpoint for getting portfolio history
endpoint = '/v2/account/portfolio/history'

# Set the parameters for the request
params = {
    'period': '30D',  # Specify the desired time period (e.g., '1D', '1W', '1M')
    'timeframe': '1H'  # Specify the time interval of each data element (e.g., '1D', '1H', '15Min')
}

# Set the headers for the request
headers = {
    'APCA-API-KEY-ID': config.API_KEY,
    'APCA-API-SECRET-KEY': config.API_SECRET
}



def request_portfolio_history():
    # Send the GET request to the Alpaca Trading API
    response = requests.get(
        base_url + endpoint,
        params=params,
        headers=headers
    )

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the response JSON
        portfolio_history = response.json()

        # Reformat the timestamps
        timestamps = portfolio_history['timestamp']
        formatted_timestamps = []

        for timestamp in timestamps:
            formatted_timestamp = datetime.datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
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
    timestamps = portfolio_history['timestamp']
    equity = portfolio_history['equity']
    profit_loss = portfolio_history['profit_loss']
    profit_loss_pct = portfolio_history['profit_loss_pct']
    
    # Plot the equity
    plt.figure(figsize=(10, 6))
    plt.plot(timestamps, equity, label='Equity')
    plt.xlabel('Timestamp')
    plt.ylabel('Equity')
    plt.title('Portfolio Equity')
    plt.legend()

    # Alternatively, skip every other label
    plt.xticks(range(len(timestamps)), timestamps, rotation=45, fontsize=8)
    for i, label in enumerate(plt.gca().xaxis.get_ticklabels()):
        if i % 10 == 1:
            label.set_visible(True)
        else:
            label.set_visible(False)

    static_path = 'static'
    # Combine the strings to create the file path
    file_path = os.path.join(static_path, plot_filename)

    # Save the plot using the file path
    plt.savefig(file_path)


