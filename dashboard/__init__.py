from os import system
from time import sleep

system("gunicorn -c gunicorn_config.py main:app")
