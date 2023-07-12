import pandas as pd
import os, time
import matplotlib.pyplot as plt


def dataCrunch(plot_filename):
    time.sleep(2)
    df = pd.read_csv('/workspaces/TV-Alpaca-Bot/src/logs/orders.csv')

    # Calculate total amount for each row and add it to the dataframe
    df['amount'] = df['filled_qty'] * df['filled_avg_price']

    symbols = df['symbol'].unique()
    closed_positions = []

    for symbol in symbols:
        symbol_df = df[df['symbol'] == symbol]
        sell_qty = symbol_df[symbol_df['side'] == 'sell']['filled_qty'].sum()
        buy_qty = symbol_df[symbol_df['side'] == 'buy']['filled_qty'].sum()

        net_qty = sell_qty - buy_qty

        if net_qty != 0:
            # Open position
            symbol_df = symbol_df.sort_values('filled_at', ascending=False)
            #latest_order = symbol_df.iloc[-1]  # Get the latest order
            #open_position = latest_order[['symbol', 'side', 'filled_avg_price', 'filled_qty']]
            #open_position['pnl'] = 0.0  # Set the P/L for the open position

            closed_orders = symbol_df[:-1]  # Exclude the latest order for closed positions

            total_sell_amount = closed_orders[closed_orders['side'] == 'sell']['amount'].sum()
            total_buy_amount = closed_orders[closed_orders['side'] == 'buy']['amount'].sum()

            total_sell_qty = sell_qty
            total_buy_qty = buy_qty

            pnl = total_sell_amount - total_buy_amount
            if total_sell_amount != 0:
                closed_positions.append(
                    (symbol, net_qty, total_sell_qty, total_buy_qty, pnl, total_sell_amount, total_buy_amount)
                )

        else:
            # No open position, calculate P/L for all orders
            total_sell_amount = symbol_df[symbol_df['side'] == 'sell']['amount'].sum()
            total_buy_amount = symbol_df[symbol_df['side'] == 'buy']['amount'].sum()

            total_sell_qty = sell_qty
            total_buy_qty = buy_qty

            pnl = total_sell_amount - total_buy_amount
            if pnl != 0:
                closed_positions.append(
                    (symbol, net_qty, total_sell_qty, total_buy_qty, pnl, total_sell_amount, total_buy_amount)
                )

    # Create a DataFrame for closed positions
    closed_positions_df = pd.DataFrame(
        closed_positions,
        columns=['symbol', 'pnl', 'net_qty', 'total_sell_qty', 'total_buy_qty', 'total_sell_amount', 'total_buy_amount']
    )
    df_sorted = closed_positions_df.sort_values('pnl', ascending=False)


    
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