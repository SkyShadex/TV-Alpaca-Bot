from alpaca.trading.client import TradingClient
import config
import time
import threading
import datetime as dt
from pytz import timezone
import re
import pandas as pd
import redis

class CustomTradingClient(TradingClient):

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'initialized'):
            super().__init__(config.API_KEY, config.API_SECRET, paper=True)
            # self.dev = TradingClient(config.API_KEY, config.API_SECRET, paper=True)
            self.prod = TradingClient(config.API_KEY_PROD, config.API_SECRET_PROD, paper=False)
            self.client = {
                'DEV': self,  # Reference to the default 'dev' account
                'LIVE': self.prod
                }
            self.initialized = True
            self.redis_client = redis.Redis(host=config.DB_HOST, port=config.DB_PORT, decode_responses=True)
            # self.clientDF = pd.DataFrame()
            # self.clientDF['DEV'] = self
            

    def check_alpaca_status(self):
        try:
            # with self.rate_limit_lock:
            # Make the API request within the lock to ensure only one thread can access it at a time
            account_info = self.get_account()
            return True
        except Exception as e:
            print(f"Error occurred while checking Alpaca API status: {e}")
            return False

    def rate_limiter(self, key, limit, window):
        current_time = int(time.time())
        pipeline = self.redis_client.pipeline()
        pipeline.zadd(key, {current_time: current_time})
        pipeline.zremrangebyscore(key, 0, current_time - window)
        pipeline.zcard(key)
        pipeline.expire(key, window + 1)
        _, _, count, _ = pipeline.execute()

        if count > limit:
            return False
        return True

    def call_with_rate_limit(self, func, *args, **kwargs):
        key = "api_call_limit"
        limit = 200  # Set the desired limit (e.g., 200 calls)
        window = 60  # Time window in seconds (e.g., 60 seconds)

        while True:
            if self.rate_limiter(key, limit, window):
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    print(f"Error occurred: {e}")
                    time.sleep(5)
            else:
                print("Rate limit exceeded. Retrying in 5 seconds...")
                time.sleep(5)

    def trading_hours(self,resume_time=3,pause_time=16):
        current_time = dt.datetime.now(timezone('US/Eastern'))
        if dt.time(pause_time, 0) <= current_time.time():
            return False
        if current_time.time() <= dt.time(resume_time, 0):
            return False
        if current_time.weekday() >= 5:
            return False
        return True
    
    def parseOptSym(self,symbol):
        try:
            match = re.match(r'^([A-Za-z]+)(\d{6})([PC])(\d+)$', symbol)
            base_symbol, expiry, option_type, strike_price = match.groups()
            strike_price = int(strike_price) / 1000.0
            expiry = f"20{expiry[:2]}-{expiry[2:4]}-{expiry[4:6]}"
            expiry_date = dt.datetime.strptime(expiry, "%Y-%m-%d")
            today_date = dt.datetime.today()
            days_to_expiry = (expiry_date - today_date).days+1 #TODO: Handle Zero error with contracts expiring day of
            option_type = "put" if option_type == 'P' else "call"
            return base_symbol,strike_price,days_to_expiry,option_type
        except Exception as e:
            pass

    def adjustmentTimed(self,startValue=0.3,finalValue=1.0,startDate=dt.datetime(2024, 4, 26),period=60):
        days_passed = min(max((dt.datetime.now() - startDate).days,1),period)
        conversion = 365/252
        increment_per_day = (finalValue - startValue) / (period * conversion)
        intermediateValue = startValue + increment_per_day * days_passed
        return intermediateValue
    
api = CustomTradingClient()