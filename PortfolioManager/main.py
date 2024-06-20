import json
import logging
from logging.handlers import TimedRotatingFileHandler
import redis
import numpy as np

from alpaca.trading.requests import GetOrdersRequest
from flask import Flask, jsonify, render_template
from components.Clients.Alpaca import executionManager, portfolio
from components.Clients.Alpaca.portfolioManager import (
    managePNL,
    reversalDCA,
    PortfolioManager,
)

import sys
import config
from common import start
from common.api_alpaca import api
from components.Clients.Alpaca import DataAnalysis as da
from flask_apscheduler import APScheduler


app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    filemode="a",
    format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
)  # filename="logs/py_log.log"
redis_client = redis.Redis(
    host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True
)
pm = {
    "DEV": PortfolioManager(client=api.client["DEV"]),
    "LIVE": PortfolioManager(client=api.client["LIVE"]),
}
master_scheduler = APScheduler()
scheduler = APScheduler()


def manageSchedules(TradingHours, OrderReset, portfolio, onInit):
    if TradingHours:
        master_scheduler.add_job(
            id="bod",
            func=scheduler.resume,
            trigger="cron",
            day_of_week="mon-fri",
            hour=8,
            minute=0,
            misfire_grace_time=None,
        )
        master_scheduler.add_job(
            id="eod",
            func=scheduler.pause,
            trigger="cron",
            day_of_week="mon-fri",
            hour=20,
            minute=5,
            misfire_grace_time=None,
        )

    if OrderReset:
        if onInit:
            api.prod.cancel_orders()
            api.cancel_orders()
        # master_scheduler.add_job(id='reset_orders_1', func=api.prod.cancel_orders, trigger='cron', day_of_week='mon-fri', hour=8, minute=0, misfire_grace_time = None)
        # master_scheduler.add_job(id='reset_orders', func=api.cancel_orders, trigger='cron', day_of_week='mon-fri', hour=8, minute=0, misfire_grace_time = None)

    if portfolio[0]:
        if portfolio[1]:
            scheduler.add_job(id="managePNL_init", func=managePNL)
            scheduler.add_job(id="testtest", func=pm["DEV"].parseSignals)
            # scheduler.add_job(id='testtest2', func=pm['LIVE'].parseSignals)
            # scheduler.add_job(id='options_metrics_init', func=da.calcPerformance)
            # scheduler.add_job(id='rebalance_devtest', func=reversalDCA, args=[api.client['DEV']])
        scheduler.add_job(
            id="parse_signals",
            func=pm["DEV"].parseSignals,
            trigger="cron",
            day_of_week="mon-fri",
            minute="*/10",
            start_date="2024-03-25 13:15:00",
            max_instances=2,
            misfire_grace_time=None,
        )
        scheduler.add_job(
            id="parse_signals_live",
            func=pm["LIVE"].parseSignals,
            trigger="cron",
            day_of_week="mon-fri",
            minute="*/10",
            start_date="2024-03-25 13:20:00",
            max_instances=2,
            misfire_grace_time=None,
        )
        scheduler.add_job(
            id="managePNL_loop",
            func=managePNL,
            trigger="cron",
            day_of_week="mon-fri",
            minute="*/7",
            start_date="2024-03-25 13:15:00",
            max_instances=2,
            misfire_grace_time=None,
        )
        scheduler.add_job(
            id="options_metrics",
            func=da.calcPerformance,
            trigger="cron",
            day_of_week="mon-fri",
            hour=20,
            misfire_grace_time=None,
        )
        scheduler.add_job(
            id="rebalance_Dev",
            func=reversalDCA,
            trigger="cron",
            day_of_week="mon-fri",
            hour=13,
            minute=31,
            misfire_grace_time=None,
        )
        scheduler.add_job(
            id="rebalance_Prod",
            func=reversalDCA,
            args=[api.client["LIVE"]],
            trigger="cron",
            day_of_week="mon-fri",
            hour=19,
            misfire_grace_time=None,
        )
        # scheduler.add_job(id='rebalance_job_1', func=alpaca_rebalance, trigger='interval', minutes=1, start_date='2024-03-25 08:05:00')

    master_scheduler.init_app(app)
    master_scheduler.start()
    scheduler.init_app(app)
    scheduler.start()

    if not api.trading_hours() and TradingHours:
        print(f"Pause Operations... {scheduler.state}")
        scheduler.pause()


start.startMessage(api.client["LIVE"].get_account().buying_power, api.client["LIVE"].get_account().non_marginable_buying_power, api.client["LIVE"].get_account().daytrade_count)  # type: ignore
start.startMessage(api.client["DEV"].get_account().buying_power, api.client["DEV"].get_account().non_marginable_buying_power, api.client["DEV"].get_account().daytrade_count)  # type: ignore
manageSchedules(
    TradingHours=True,
    OrderReset=False,
    portfolio=[True, True],
    onInit=True,
)


@app.route("/options_metrics", methods=["GET"])
def options_metrics():
    print("Fetching Options Metrics...")
    master_scheduler.add_job(id="options_metrics_init", func=da.calcPerformance)
    return jsonify({"output": "Fetching Options Metrics"})
