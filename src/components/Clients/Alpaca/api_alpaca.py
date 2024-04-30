from alpaca.trading.client import TradingClient
import config
import time
import threading

class CustomTradingClient(TradingClient):
    def __init__(self):
        super().__init__(config.API_KEY, config.API_SECRET, paper=True)
        self.rate_limit_lock = threading.Lock()
        # self.dev = TradingClient(config.API_KEY, config.API_SECRET, paper=True)
        self.prod = TradingClient(config.API_KEY_PROD, config.API_SECRET_PROD, paper=False)
        self.client = {
            'DEV': self,  # Reference to the default 'dev' account
            'LIVE': self.prod
        }

    def check_alpaca_status(self):
        try:
            with self.rate_limit_lock:
                # Make the API request within the lock to ensure only one thread can access it at a time
                account_info = self.get_account()
                return True
        except Exception as e:
            print(f"Error occurred while checking Alpaca API status: {e}")
            return False

    def call_with_rate_limit(self, func, *args, **kwargs):
        while True:
            try:
                with self.rate_limit_lock:
                    result = func(*args, **kwargs)
                return result
            except Exception as e:
                # Retry after waiting for a while
                print(f"Rate limit exceeded. Retrying in 5 seconds...")
                time.sleep(5)

api = CustomTradingClient()