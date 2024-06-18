import random
import datetime
import pytz
import math
from alpaca.trading.enums import AssetClass, OrderStatus
from alpaca.trading.requests import (
    ClosePositionRequest,
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
)

import config
from common import vars
from common.api_alpaca import api
from components.Clients.Alpaca.portfolio import parse_positions
import logging
import redis
import uuid
import json
import threading
import pandas as pd
import time

from apscheduler.schedulers.background import BackgroundScheduler

# Ensure your scheduler is globally accessible or passed to where needed
scheduler = BackgroundScheduler()
scheduler.start()


# Declaring some variables
accountInfo = api.get_account()
slippage = 1 - (config.SLIPPAGE / 100)


# Check if our account is restricted from trading.
def tradingValid():
    if accountInfo.trading_blocked:  # type: ignore
        return "Error: Account is currently restricted from trading."
    elif int(accountInfo.daytrade_count) > 3 and not config.DAYTRADE_ALLOW:  # type: ignore
        return "Error: Approaching Day Trade Limit"
    else:
        return True


def checkOpenOrder(ticker, side):
    orderParams = GetOrdersRequest(status="open", limit=20, nested=False, symbols=[ticker])  # type: ignore
    orders = api.get_orders(filter=orderParams)
    canceled_orders = []
    if orders:  # Check if there are any orders
        for order in orders:
            if side == "buy" or order.status in [
                OrderStatus.CANCELED,
                OrderStatus.FILLED,
            ]:  # order.side == side and side == 'buy':  # type: ignore
                continue
            else:
                try:
                    api.cancel_order_by_id(order_id=order.id)  # type: ignore
                    canceled_orders.append(order.id)  # type: ignore
                except Exception as e:
                    print(f"Error canceling order {order.id}: {e}")  # type: ignore

        # counter = len(canceled_orders)
    return canceled_orders


def checkAssetClass(ticker):
    asset = api.get_asset(ticker)
    if asset.tradable:  # type: ignore
        return asset.asset_class  # type: ignore
    else:
        return None


def calcQuantity(ticker, price, weight=1.0):
    accountInfo = api.get_account()
    if config.MARGIN_ALLOW == True:
        buyingPower = float(accountInfo.regt_buying_power)  # type: ignore
    else:
        buyingPower = float(accountInfo.non_marginable_buying_power)  # type: ignore

    quantity = (
        max((buyingPower * config.RISK_EXPOSURE * weight), 1) / price
    )  # Position Size Based on Risk Exposure

    if quantity == 0.0:
        return 1.0

    return quantity


def calcRR(price):
    stopLoss = round((((0.1 * config.RISK) * price) - price) * -1, 2)
    takeProfit = round((((0.1 * config.RISK) * config.REWARD) * price) + price, 2)
    return stopLoss, takeProfit


def extendedHoursCheck():
    current_time = datetime.datetime.now().astimezone(pytz.timezone("US/Eastern"))
    trading_hours_start = current_time.replace(
        hour=9, minute=30, second=0, microsecond=0
    )
    trading_hours_end = current_time.replace(hour=16, minute=0, second=0, microsecond=0)

    if current_time < trading_hours_start or current_time >= trading_hours_end:
        return True
    else:
        return False


# ============================== Execution Logic =================================
def executeOrder(webhook_message):
    symbol_WH, side_WH, price_WH, quantity_WH, comment_WH, orderID_WH = vars.webhook(
        webhook_message
    )

    checkOpenOrder(symbol_WH, side_WH)

    if side_WH == "buy":
        result = entryOrder(symbol_WH, price_WH, orderID_WH)
    elif side_WH == "sell":
        result = exitOrder(symbol_WH, orderID=orderID_WH)
    else:
        result = "Invalid order side"
    return result


def entryOrder(
    symbol,
    price,
    orderID,
    side="buy",
    isMarketOrder=False,
    weight=1.0,
    quantity=0.0,
    client=api.client["DEV"],
):
    if price == 0:
        print(f"price error: {symbol},{price},{side},{orderID}")
        return
    checkCrypto = checkAssetClass(symbol)
    slippage_price = price * slippage
    if quantity == 0.0:
        quantity = calcQuantity(symbol, slippage_price, weight)
    client_order_id = f"skybot1_{orderID}{random.randrange(100000000)}"
    tif = "day"
    if checkCrypto == AssetClass.CRYPTO:
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=round(quantity, 2),
            side=side,
            time_in_force=tif,
            client_order_id=client_order_id,
        )
        # else:
        #     orderData = LimitOrderRequest(
        #             symbol=symbol,
        #             qty=quantity,
        #             side=side,
        #             type='limit',
        #             time_in_force='day',
        #             limit_price=round(slippage_price,2),
        #             client_order_id=client_order_id
        #         )
        response = f"Market Order, {side}: {symbol}. {quantity:.2f} shares, {tif}."
    else:
        if quantity == 0.0:
            if side == "sell":
                quantity = max(int(quantity), 1)
            else:
                quantity = round(quantity, 9)
        extCheck = extendedHoursCheck()
        stopLoss, takeProfit = calcRR(price)
        take_profit = {"limit_price": takeProfit}
        stop_loss = {"stop_price": stopLoss}
        tif = "day"
        if config.EXTENDTRADE_ALLOW and extCheck:
            if not isMarketOrder:
                orderData = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    type="limit",
                    time_in_force=tif,
                    limit_price=round(slippage_price, 2),
                    extended_hours=str(extCheck),
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                    client_order_id=client_order_id,
                )
            else:
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=tif,
                    extended_hours=str(extCheck),
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id,
                )
        else:
            if not isMarketOrder:
                orderData = LimitOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    type="limit",
                    time_in_force=tif,
                    limit_price=round(slippage_price, 2),
                    # order_class='bracket',
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id,
                )
            else:
                orderData = MarketOrderRequest(
                    symbol=symbol,
                    qty=quantity,
                    side=side,
                    time_in_force=tif,
                    # order_class='bracket',
                    # take_profit=take_profit,
                    # stop_loss=stop_loss,
                    client_order_id=client_order_id,
                )
        response = f"Order {side}: {symbol} @ {slippage_price:.2f}. {quantity:.2f} shares, {tif}."

    logging.info(f"{entryOrder.__name__} {response}")
    res = client.submit_order(orderData)
    return res


def exitOrder(symbol, client=api.client["DEV"], orderID="", live=False):
    # if 'tp' in orderID and False:
    #     close_options = ClosePositionRequest(percentage=config.TAKEPROFIT_POSITION*100)
    #     return api.close_position(symbol, close_options=close_options)
    # else:
    res = client.close_position(symbol)
    return res


def optionsOrder(
    symbol,
    price,
    client=api.client["DEV"],
    orderID="",
    side="buy",
    quantity=1,
    isMarketOrder=False,
    weight=1.0,
    tif="day",
    bet=100.0,
    vol_limit=5,
):
    if isMarketOrder:
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=quantity,
            side=side,
            time_in_force=tif,
        )
    else:
        qty = quantity
        if side != "sell":
            portfolio_Corrected = bet * weight
            qty = (
                min(max(math.floor(portfolio_Corrected / (100 * price)), 1), vol_limit)
                if price != 0
                else 1
            )

        orderData = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            type="limit",
            time_in_force=tif,
            limit_price=round(price, 2),
        )
    response = f"Order {side}: {orderID} @ {price:.3f}. {qty:.2f} contracts, '{tif}'."
    logging.info(f"{optionsOrder.__name__} {response}")
    return client.submit_order(orderData)


# //--------------------- PROD ENV ---------------------------------//


def entryOrderProd(symbol, price, orderID, side="buy", isMarketOrder=False, weight=1.0):
    client = api.client["LIVE"]
    if price == 0:
        print(f"[PROD]: price error: {symbol},{price},{side},{orderID}")
        return

    asset = client.get_asset(symbol)

    if not asset:
        print(f"[PROD]: DNE: {symbol},{price},{side},{orderID}")
        return

    if not asset.tradable:
        return

    acct_info_prod = client.get_account()
    buyingpower = max(
        float(acct_info_prod.regt_buying_power) - 500, 1
    )  # In order to keep a cash balance
    quantity = max((buyingpower * config.RISK_EXPOSURE * weight), 1.1) / price

    if quantity == 0.0:
        quantity = 1.0

    client_order_id = f"skybot1_prod{orderID}{random.randrange(100000000)}"
    if asset.asset_class == AssetClass.CRYPTO:
        orderData = MarketOrderRequest(
            symbol=symbol,
            qty=round(quantity, 2),
            side=side,
            time_in_force="day",
            client_order_id=client_order_id,
        )
        response = f"Market Order, {side}: {symbol}. {quantity} shares."
    else:
        if side == "sell":
            quantity = max(int(quantity), 1)
        else:
            quantity = round(quantity, 9)

        extCheck = extendedHoursCheck()
        tif = "day"
        if config.EXTENDTRADE_ALLOW and extCheck:
            orderData = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=tif,
                extended_hours=str(extCheck),
                client_order_id=client_order_id,
            )
        else:
            orderData = MarketOrderRequest(
                symbol=symbol,
                qty=quantity,
                side=side,
                time_in_force=tif,
                client_order_id=client_order_id,
            )
        response = (
            f"[PROD]: Order {side}: {symbol} @ {price}. {quantity:.2f} shares, {tif}."
        )
    logging.info(f"{entryOrderProd.__name__} {response}")
    res = client.submit_order(orderData)
    return res


class SkyOrder:
    def __init__(self, client, symbol: str, order_type: str, **kwargs):
        """
        Initialize a SkyOrder object.

        Args:
            client (str): The client placing the order.
            symbol (str): The symbol for the asset.
            order_type (str): The type of the order (e.g., 'limit', 'market').
            **kwargs: Additional optional parameters.

        Keyword Args:
            asset_class (str): The asset class (e.g., 'equity').
            side (str): The side of the order ('buy' or 'sell').
            quantity (int): The quantity of the order.
            price (float): The price of the order.
            volume_limit (float): The max volume for order.
            bet_size (float): The max cash allotted to order.
            weight (float): The final weight modified for order.
            order_memo (str): A memo or note for the order.
            start_time (str): The start time of the order.
            last_time (str): The last update time of the order.
            end_time (str): The end time of the order.

        """
        self.order_id = str(f"ORDER-{uuid.uuid4()}")
        self.client = (
            "LIVE"
            if client is api.client["LIVE"]
            else "DEV" if client is api.client["DEV"] else "Err"
        )
        # logging.info(f'{client} {self.client} {self.order_id}')
        self.symbol = symbol
        self.order_type = order_type
        self.asset_class = kwargs.get("asset_class", "None")
        if "None" in self.asset_class:
            self.asset_class = (
                "us_option" if len(symbol) > 8 else "us_equity"
            )  # be aware that api offers crypto, but it's not available for me
        self.side = kwargs.get("side", "None")
        self.quantity = kwargs.get("quantity", 0.0)
        self.price = kwargs.get("price", 0.0)
        self.volume_limit = kwargs.get("volume_limit", 1)
        self.bet_size = kwargs.get("bet_size", 1.0)
        self.weight = kwargs.get("weight", 1.0)
        self.order_memo = kwargs.get("order_memo", "None")
        self.start_time = kwargs.get("start_time", 0)
        self.next_time = kwargs.get("next_time", 0)
        self.end_time = kwargs.get("end_time", 0)
        self.payload = self.to_dict()

    def to_dict(self):
        """
        Convert the SkyOrder object to a dictionary.

        Returns:
            dict: The order details as a dictionary.
        """
        return {
            "order_id": self.order_id,
            "client": self.client,
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "order_type": self.order_type,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "volume_limit": self.volume_limit,
            "bet_size": self.bet_size,
            "weight": self.weight,
            "order_memo": self.order_memo,
            "start_time": self.start_time,
            "next_time": self.next_time,
            "end_time": self.end_time,
        }

    def to_json(self):
        """
        Convert the SkyOrder object to a JSON string.

        Returns:
            str: The order details as a JSON string.
        """
        return json.dumps(self.to_dict())


class ExecutionManager(threading.Thread):
    def __init__(self):
        super().__init__()
        self.redis_client = redis.Redis(
            host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True
        )

    def push_order_db(self, order: SkyOrder):
        order_id = order.order_id
        order_data = order.to_dict()

        self.redis_client.rpush("order:queue", order_id)
        self.redis_client.hset(f"order:{order_id}", mapping=order_data)

    def update_holdings(self, client):
        pos_raw = client.get_all_positions()
        if not pos_raw:
            return

        self.positions = parse_positions(pos_raw)
        if self.positions.empty:
            return

        posdf_json = self.positions.to_json(orient="records")
        self.redis_client.set(
            (
                "current:positions:LIVE"
                if client is api.client["LIVE"]
                else "current:positions:DEV"
            ),
            posdf_json,
        )
        self.redis_client.hset(
            "portfolio:positions",
            "LIVE" if client is api.client["LIVE"] else "DEV",
            posdf_json,
        )
        return self.positions

    def process_orders(self):
        while True:
            try:
                time.sleep(1)
                # Pop an order ID from the front of the list
                order_id = self.redis_client.lpop("order:queue")
                if order_id:
                    # Retrieve the order details from the hash
                    order_data = self.redis_client.hgetall(f"order:{order_id}")
                    self.redis_client.expire(f"order:{order_id}", 1200)
                    if order_data:
                        order_data["client_label"] = order_data["client"]
                        order_data["client"] = (
                            api.client["LIVE"]
                            if order_data["client"] == "LIVE"
                            else (
                                api.client["DEV"]
                                if order_data["client"] == "DEV"
                                else "Err"
                            )
                        )
                        self.execute_order(order_data)
            except Exception as e:
                logging.warning(f" process_orders {e}")

    def execute_order(self, order_data):
        # pos_all = self.update_holdings(order_data['client'])
        match order_data["order_type"]:
            case "exit":
                self.exitOrder(order_data)
                pass
            case "market":
                self.entryOrder(order_data)
                pass
            case "limit":
                print(f"{order_data['order_type']}")
                # print(f"Executing order: {order_data}")
                pass
            case "dca":
                print(f"{order_data['order_type']}")
                # print(f"Executing order: {order_data}")
                # self.entryOrder(order_data)
                pass
            case _:
                print(f"unknown source: {order_data['order_type']}")
                # print(f"Executing order: {order_data}")
                pass

        # if toDelete:

    def exitOrder(self, order_data):
        symbol = order_data["symbol"]
        side = order_data["side"]
        price = float(order_data["price"])
        quantity = float(order_data["quantity"])
        order_type = order_data["order_type"]
        client_order_id = order_data["order_id"]

        try:
            pos_all = self.update_holdings(order_data["client"])
            if symbol in pos_all["symbol"].values:
                match = (
                    pos_all.loc[pos_all.symbol == order_data["symbol"]].copy().iloc[0]
                )
                if abs(match.unrealized_plpc) > 0.05:  # to reduce turnover
                    res = order_data["client"].close_position(symbol)
            print(
                f"[{order_data['client_label']}]: {order_data['order_type']} : {order_data['symbol']} {order_data['order_memo']}"
            )
            time.sleep(2)
        except (KeyError, ValueError, TypeError, Exception) as e:
            logging.warning(f" exitOrder {e}")

    def entryOrder(self, order_data):
        tif = "day"
        symbol = order_data["symbol"]
        side = order_data["side"]
        price = float(order_data["price"])
        quantity = (
            float(order_data["quantity"])
            if "sell" not in side
            else min(int(order_data["quantity"]), 1)
        )
        order_type = order_data["order_type"]
        client_order_id = order_data["order_id"]

        try:
            entryOrder(
                symbol,
                price,
                client_order_id,
                side=side,
                isMarketOrder=True,
                weight=1.0,
                quantity=quantity,
                client=order_data["client"],
            )
            print(
                f"[{order_data['client_label']}]: {order_data['order_type']} : {order_data['symbol']} {order_data['order_memo']}"
            )
        except (KeyError, ValueError, TypeError, Exception) as e:
            if "cannot be sold short" in str(e):
                logging.debug(e)
            else:
                logging.warning(f" entryOrder {e}")

    def childOrders(self, order_data):
        toChildOrders = False
        current_time = datetime.datetime.now().astimezone(pytz.timezone("US/Eastern"))
        market_end = datetime.datetime.combine(
            current_time, datetime.time(16, 0)
        ).astimezone(pytz.timezone("US/Eastern"))
        minutes_remaining = (market_end - current_time).total_seconds() / 60
        interval = 45  # e.g., minutes
        intervals_remaining = minutes_remaining / interval
        percentage_per_interval = min(50, 100 // intervals_remaining)

        tif = "day"
        symbol = order_data["symbol"]
        side = order_data["side"]
        price = float(order_data["price"])
        quantity = float(order_data["quantity"])
        order_type = order_data["order_type"]
        client_order_id = order_data["order_id"]

        try:
            if order_data["symbol"] in self.positions.symbol.any():
                pos = (
                    self.positions.loc[self.positions.symbol == order_data["symbol"]]
                    .copy()
                    .iloc[0]
                )
                toChildOrders = pos.market_value > 1000 and pos.qty_available > 1

            # this only handles market entries, not exits
            # res = order_data['client'].close_position(order_data['symbol'],close_options=ClosePositionRequest(percentage=str(percentage_per_interval)))
            if toChildOrders:
                total_quantity = quantity
                child_orders = []

                for i in range(int(intervals_remaining)):
                    # Calculate quantity for each child order
                    child_quantity = (
                        int(math.ceil(total_quantity * percentage_per_interval / 100))
                        if "short" in str(pos["side"]).lower()
                        else round(total_quantity * percentage_per_interval / 100, 9)
                    )
                    total_quantity -= child_quantity

                    orderData = MarketOrderRequest(
                        symbol=symbol,
                        qty=child_quantity,
                        side=side,
                        time_in_force=tif,
                        client_order_id=f"{client_order_id}_child_{i+1}",
                    )

                    # TODO: consider using the existing function for entries
                    # entryOrder [symbol,price,client_order_id,side=side,isMarketOrder=True,weight=1.0,quantity=quantity,client=order_data['client']]
                    run_date = current_time + datetime.timedelta(
                        minutes=interval * (i + 1)
                    )
                    scheduler.add_job(
                        order_data["client"].submit_order,
                        "date",
                        run_date=run_date,
                        args=[orderData],
                        misfire_grace_time=None,
                    )

                    child_orders.append(orderData)

                # If there's any remaining quantity, schedule it as the last order
                if total_quantity > 0:
                    orderData = MarketOrderRequest(
                        symbol=symbol,
                        qty=total_quantity,
                        side=side,
                        time_in_force=tif,
                        client_order_id=f"{client_order_id}_child_final",
                    )

                    run_date = current_time + datetime.timedelta(
                        minutes=interval * int(intervals_remaining)
                    )
                    scheduler.add_job(
                        order_data["client"].submit_order,
                        "date",
                        run_date=run_date,
                        args=[orderData],
                        misfire_grace_time=None,
                    )

                    child_orders.append(orderData)

            return toChildOrders

        except Exception as e:
            logging.exception(e)

    # def calcQuantity(self,client,price,weight=1.0):
    #     accountInfo = client.get_account()
    #     if config.MARGIN_ALLOW == True:
    #         buyingPower = float(accountInfo.regt_buying_power)  # type: ignore
    #     else:
    #         buyingPower = float(accountInfo.non_marginable_buying_power)  # type: ignore

    #     quantity = max((buyingPower * config.RISK_EXPOSURE * weight),1) / price  # Position Size Based on Risk Exposure

    #     if quantity == 0.0:
    #         return 1.0

    #     return quantity


execution_manager = ExecutionManager()
order_thread = threading.Thread(target=execution_manager.process_orders)
order_thread.start()
