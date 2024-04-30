# gunicorn_config.py
import multiprocessing

bind = '0.0.0.0:5000'  # Bind to all available network interfaces to port
workers = 1#min(multiprocessing.cpu_count() * 2 + 1,10)
print(f'initializing {workers} workers')

#gunicorn -c gunicorn_config.py main:app