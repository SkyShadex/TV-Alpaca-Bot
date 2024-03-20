from components.Clients.Alpaca.api_alpaca import api
from datetime import date
import math
import config
from flask import Flask
from flask_caching import Cache
import redis


redis_client = redis.Redis(host='redis-stack-server', port=6379, decode_responses=True)

def initialize_globals():
    # Set initial highest_equity in Redis
    redis_client.set('highest_equity_date', str(date.today()))
    redis_client.set('highest_equity', float(api.get_account().last_equity))

# Initialize global variables for the first request in each thread
initialize_globals()

def alpaca_rebalance():
    currentDate = str(date.today())
    current_equity = float(api.get_account().equity)
    goal = config.PORTFOLIO_REBAL / 100

    # Retrieve highest_equity from Redis
    highest_equity = float(redis_client.get('highest_equity'))
    portfolio_pnl = math.log(current_equity / highest_equity)

    print(f"Daily P/L || Current: {portfolio_pnl:.4f}% Goal: {goal:.4f}%")

    if (portfolio_pnl > goal):
        print("Rebalancing Portfolio...")
        api.close_all_positions(True)
        
        # Update highest_equity in Redis
        if redis_client.set('highest_equity', current_equity):
            print(f"Updated highest_equity: {current_equity}")

    
    if redis_client.get('highest_equity_date') != currentDate:
        if redis_client.set('highest_equity_date', currentDate) and redis_client.set('highest_equity', current_equity):
            print(f"Updating: {currentDate} {current_equity}")

    # The Redis client automatically handles atomic operations

# In your Flask route or application setup, call initialize_globals() to set up the initial highest_equity in Redis.