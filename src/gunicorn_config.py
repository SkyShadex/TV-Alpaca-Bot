# gunicorn_config.py

bind = '0.0.0.0:5000'  # Bind to all available network interfaces to port
workers = 3  # Number of Gunicorn worker processes