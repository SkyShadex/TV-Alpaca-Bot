from components.api_alpaca import api as alpaca
from components.api_alpaca import api
from alpaca.trading.client import TradingClient
from datetime import date
import math
import config

# Declaring some variables
accountInfo = api.get_account()
highest_equity_date = date.today()  # Initialize with the current date
highest_equity = float(accountInfo.last_equity)  # Initialize with current equity


def alpaca_rebalance():
    global highest_equity_date  # Declare the variable as global
    global highest_equity  # Declare the variable as global
    current_equity = float(accountInfo.equity)
    portfolio_pnl = math.log(current_equity / highest_equity)
    goal = config.PORTFOLIO_REBAL / 100

    print( f"Daily P/L || Current: {portfolio_pnl:.4f}% Goal: {goal:.4f}%") # \n{current_equity} / {highest_equity}

    if highest_equity_date != date.today():
        highest_equity_date = date.today()
        highest_equity = current_equity
        
    if portfolio_pnl > goal:
        print("Rebalancing Portfolio...")
        api.close_all_positions(True)
        highest_equity = current_equity