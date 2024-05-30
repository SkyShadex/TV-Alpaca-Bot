import os

os.system("gunicorn -c gunicorn_config.py main:app")
