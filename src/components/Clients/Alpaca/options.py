import random
import datetime as dt
import pytz

from alpaca.trading.enums import (AssetClass, OrderStatus)
from alpaca.trading.requests import (ClosePositionRequest, GetOrdersRequest,
                                     LimitOrderRequest, MarketOrderRequest)


import config
from commons import vars
from components.Clients.Alpaca.api_alpaca import api
from components.Clients.Alpaca.price_data import get_ohlc_alpaca
from sklearn.preprocessing import MinMaxScaler
import requests
import json
import pandas as pd
import numpy as np

# Declaring some variables
accountInfo = api.get_account()


class AlpacaOptionContracts:
    def __init__(self):
        self.isValid = False
        self.url = "https://paper-api.alpaca.markets/v2/options/contracts"
        self.key = config.API_KEY
        self.secret = config.API_SECRET
        self.headers = {
            "accept": "application/json",
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret
        }

    def get_option_contracts(self, underlying_symbols=None, status="active", expiration_date=None,
                             expiration_date_gte=None, expiration_date_lte=None, root_symbol=None,
                             option_type=None, style='american', strike_price_gte=None, strike_price_lte=None,
                             page_token=None, limit=1000,override=False):
        params = {
            "status": status,
            "expiration_date": expiration_date,
            "expiration_date_gte": expiration_date_gte,
            "expiration_date_lte": expiration_date_lte,
            "root_symbol": root_symbol,
            "type": option_type,
            "style": style,
            "strike_price_gte": strike_price_gte,
            "strike_price_lte": strike_price_lte,
            "page_token": page_token,
            "limit": limit
        }
        if underlying_symbols:
            params["underlying_symbols"] = underlying_symbols

        response = requests.get(self.url, headers=self.headers, params=params)
        response.raise_for_status()  # Raise an exception for 4XX or 5XX status codes
        return self.parse_response(response.json(),override)
    
    def get_option_bars(self,symbol_or_symbols, timeframe, start=None, end=None, limit=None, sort='asc'):
        url = "https://data.alpaca.markets/v1beta1/options/bars"

        headers = {
            "accept": "application/json",
            "APCA-API-KEY-ID": self.key,
            "APCA-API-SECRET-KEY": self.secret
        }
        
        if len(symbol_or_symbols) == 0:
            raise Exception("Missing Symbol")
        
        single = isinstance(symbol_or_symbols, str)
        multi = isinstance(symbol_or_symbols, list) and len(symbol_or_symbols) > 1
        need_fix = isinstance(symbol_or_symbols, list) and len(symbol_or_symbols) == 1 and len(symbol_or_symbols[-1]) > 1

        if need_fix:
            symbols = symbol_or_symbols[-1]
            single = True
        if multi:
            symbols = ','.join(symbol_or_symbols)
        elif single: 
            symbols = symbol_or_symbols   
                    
        params = {
            "symbols": symbols,
            "timeframe": timeframe,
            "limit": limit,
            "sort": sort
        }

        if start:
            params["start"] = start
        if end:
            params["end"] = end

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        if response.status_code == 200:
            data =  response.json()

            # Check if the response contains bars for multiple symbols
            if single:
                bars_data = data['bars'][symbols]
                df_bars = pd.DataFrame(bars_data)
            else:
                df_bars_list = []
                for symbol in symbol_or_symbols:
                    if symbol not in data['bars']:
                        continue
                    bars_data = data['bars'][symbol]
                    df_bars_symbol = pd.DataFrame(bars_data)
                    df_bars_symbol['symbol'] = symbol  # Add symbol column
                    df_bars_list.append(df_bars_symbol)
                df_bars = pd.concat(df_bars_list)
            
            df_bars = df_bars.astype({'c': float, 'h': float, 'l': float, 'n': int, 'o': float, 'v': int, 'vw': float})
            df_bars['t'] = pd.to_datetime(df_bars['t'])
            # df_bars['t'] = pd.to_datetime(df_bars['t']).dt.tz_localize(None)
            # decay_rate = 0.0075
            # current_date = dt.datetime.now().replace(tzinfo=None)
            # df_bars['days_ago'] = (current_date-df_bars['t']).dt.days
            # weights = np.exp(-decay_rate * df_bars['days_ago'])
            # df_bars['wc'] = df_bars['c'] * weights
            df_bars.set_index('t', inplace=True)
            df_bars['r']= df_bars['c'].pct_change()
            return df_bars
  

    def parse_response(self, response_json,override):
        option_contracts = response_json.get('option_contracts', [])
        df = pd.DataFrame(option_contracts)
        df['strike_price'] = df['strike_price'].astype(float)
        df['open_interest'] = df['open_interest'].astype(float)
        df['close_price'] = df['close_price'].astype(float)
        df['expiration_date'] = pd.to_datetime(df['expiration_date'])
        current_date = dt.datetime.now()
        df['days_to_expiry'] = ((df['expiration_date'] - current_date).dt.days).round()
        df['days_to_expiry'] = df['days_to_expiry'].astype(int)
        try:
            underlying = get_ohlc_alpaca(df['underlying_symbol'].iloc[-1],365,adjust="all",date_err=False)
        except Exception as e:
            raise RuntimeError(f"Missing Underlying Price Data for {df['underlying_symbol'].iloc[-1]}\n{e}")
        df['underlying_price'] = underlying['close'].iloc[-1]
        df['underlying_price_2'] = underlying['close'].iloc[-7]
        df['ul_vol'] = underlying['close'].pct_change().std()
        df.loc[df['type'] == 'put', 'moneyness'] = np.log((df['strike_price'])/df['underlying_price']) * 100
        df.loc[df['type'] == 'call', 'moneyness'] = np.log(df['underlying_price']/(df['strike_price'])) * 100
        
        df[['moneyness_normalized', 'strike_price_normalized']] = MinMaxScaler().fit_transform(df[['moneyness', 'strike_price']])
        df['contract_value'] = (df['moneyness_normalized']) / df['strike_price_normalized']
        df.drop(['moneyness_normalized', 'strike_price_normalized'], axis=1, inplace=True)
        
        df['open_interest'] = df['open_interest'].fillna(0)
        df['open_interest_strike_ratio'] = df['open_interest'] / df['strike_price']
        df['open_interest_strike_ratio'] = df['open_interest_strike_ratio'].fillna(0)
        df['strike_price_norm'] = df['strike_price']/df['strike_price'].sum()
        df = df[df['open_interest'].notna() & (df['open_interest'] != 0)]
        # df = df[(df['close_price']<= df['close_price'].quantile(0.95))] #Filter outlier pricing
        
        if not override:
            if len(df) < 10:
                raise RuntimeError('Too few contracts to compute')
            
            if df['open_interest'].quantile(0.5) == 0:
                # print(df.describe())
                raise RuntimeError('Not enough open interest to compute')
        
        # print(f"{len(df)} contracts found for {df['underlying_symbol'].iloc[-1]}")
        return df




