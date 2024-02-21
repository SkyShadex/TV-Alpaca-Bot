import os, app
from dotenv import find_dotenv, load_dotenv

# Dev Env Variables
dotenv_path = find_dotenv()
load_dotenv(dotenv_path)


# Security
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
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
PORTFOLIO_REBAL = 0.6

# Network Settings
LOCAL_HOST = '0.0.0.0'
PORT = '5000'


