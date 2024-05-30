import os, main
from dotenv import find_dotenv, load_dotenv

# # # Dev Env Variables
# dotenv_path = find_dotenv()
# if dotenv_path:
#     load_dotenv(dotenv_path)
# else:
#     raise RuntimeError("No .env file found")
try:
    # Security
    API_KEY = os.getenv("API_KEY")
    API_SECRET = os.getenv("API_SECRET")
    API_KEY_PROD = os.getenv("API_KEY_0")
    API_SECRET_PROD = os.getenv("API_SECRET_0")
    WEBHOOK_PASSPHRASE = os.getenv("WEBHOOK_PASSPHRASE")

    # Social Hooks
    DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
    DISCORD_WEBBHOOK_ENABLED = True

    # Strategy Settings
    REWARD = 10 # Units made for every unit risked
    RISK = 1 # Unit risked
    SLIPPAGE = 1.5
    RISK_EXPOSURE = 0.05 #equal weights divided by the number of actively traded symbols
    TAKEPROFIT_POSITION = 0.5
    DAYTRADE_ALLOW = True 
    FRACTIONAL_ALLOW = True
    MARGIN_ALLOW = True
    EXTENDTRADE_ALLOW = False

    # Portfolio Level Strategy
    PORTFOLIO_REBAL = 0.55

    # Network Settings
    LOCAL_HOST = os.getenv("LOCAL_HOST")
    LOCAL_PORT = int(os.getenv("LOCAL_PORT"))
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = int(os.getenv("DB_PORT","6379"))
except:
    raise RuntimeError("No .env file found")

# # Security
# API_KEY = os.environ["API_KEY"]
# API_SECRET = os.environ["API_SECRET"]
# API_KEY_PROD = os.environ["API_KEY_0"]
# API_SECRET_PROD = os.environ["API_SECRET_0"]
# WEBHOOK_PASSPHRASE = os.environ["WEBHOOK_PASSPHRASE"]
# print(WEBHOOK_PASSPHRASE)
# # Social Hooks
# DISCORD_WEBHOOK_URL = os.environ("DISCORD_WEBHOOK_URL")
# DISCORD_WEBBHOOK_ENABLED = True
# print(DISCORD_WEBHOOK_URL)
# # Strategy Settings
# REWARD = 10 # Units made for every unit risked
# RISK = 1 # Unit risked
# SLIPPAGE = 1.5
# RISK_EXPOSURE = 0.05 #equal weights divided by the number of actively traded symbols
# TAKEPROFIT_POSITION = 0.5
# DAYTRADE_ALLOW = True 
# FRACTIONAL_ALLOW = True
# MARGIN_ALLOW = True
# EXTENDTRADE_ALLOW = False

# # Portfolio Level Strategy
# PORTFOLIO_REBAL = 0.55

# # Network Settings
# LOCAL_HOST = os.environ["LOCAL_HOST"]
# LOCAL_PORT = os.environ["LOCAL_PORT"]
# DB_HOST = os.environ["DB_HOST"]
# DB_PORT = int(os.environ["DB_PORT","6379"])
# DB_HOST = os.getenv('REDIS_HOST', 'localhost')
# DB_PORT = os.getenv('REDIS_PORT', os.getenv("DB_PORT"))
