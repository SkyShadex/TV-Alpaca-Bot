from alpaca.trading.client import TradingClient
import config
import time

class CustomTradingClient(TradingClient):
    def __init__(self):
        super().__init__(config.API_KEY, config.API_SECRET, paper=True)
        self.alpaca_status = True

    def check_alpaca_status(self):
        if not self.alpaca_status:
            return False

        max_retries = 3
        retry_delay = 5  # Number of seconds to wait before retrying

        for retry in range(max_retries):
            try:
                account_info = self.get_account()
                self.alpaca_status = True
                return True
            except Exception as e:
                # Handle the exception and log the error (You can customize the error handling)
                print(f"Error occurred while checking Alpaca API status: {e}")
                if '429' in str(e):  # Check if the error is related to rate limiting
                    print(f"Rate limit exceeded. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    self.alpaca_status = False
                    return False

        print("Max retry attempts reached. Alpaca API is currently unavailable.")
        self.alpaca_status = False
        return False

api = CustomTradingClient()
