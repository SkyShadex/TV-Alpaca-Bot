import random
import datetime as dt
import pytz

from alpaca.trading.enums import (AssetClass, OrderStatus)
from alpaca.trading.requests import (ClosePositionRequest, GetOrdersRequest,
                                     LimitOrderRequest, MarketOrderRequest)


import config
from common import vars
from common.api_alpaca import api
from common.price_data import get_ohlc_alpaca
from sklearn.preprocessing import MinMaxScaler
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.requests import OptionChainRequest
import logging
import requests
import json
import pandas as pd
import numpy as np

# Declaring some variables
accountInfo = api.get_account()
apOpt = OptionHistoricalDataClient(config.API_KEY,config.API_SECRET)

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

    def parse_chain(self, underlying_symbol: str,
                    strike_price_gte: float | None = None, 
                    strike_price_lte: float | None = None,
                    expiration_date: dt.date | str | None = None,
                    expiration_date_gte: dt.date | str | None = None,
                    expiration_date_lte: dt.date | str | None = None,
                    root_symbol: str | None = None):
        
            params = OptionChainRequest(underlying_symbol=underlying_symbol,expiration_date_gte=expiration_date_gte,expiration_date_lte=expiration_date_lte)
            option_chain = apOpt.get_option_chain(request_params=params)
            return option_chain
    
    # def to_Dataframe(self,option_chain):
    #     try:
    #         chainDF = pd.DataFrame(option_chain).T
    #         chainDF.columns=['symbol','latest_trade','latest_quote','implied_volatility','greeks']
    #         chainDF.sort_index(inplace=True)
    #         print(chainDF.shape)

    #         def expand_column(df, col_name):
    #             col_expanded = df[col_name].apply(lambda x: pd.Series(x, dtype=object))
    #             if len(col_expanded.columns) > 1:
    #                 for subcol in col_expanded.columns:
    #                     nested_expanded = col_expanded[subcol].apply(lambda x: pd.Series(x, dtype=object))
    #                     nested_expanded.columns = [f"{subcol}_{subcol2}" for subcol2 in nested_expanded.columns]
    #                     col_expanded = col_expanded.drop(columns=[subcol]).join(nested_expanded)
    #             col_expanded.columns = [f"{col_name}_{subcol}" for subcol in col_expanded.columns]
    #             df = df.drop(columns=[col_name]).join(col_expanded)
    #             return df

    #         chainDF = expand_column(chainDF, 'symbol')
    #         chainDF = expand_column(chainDF, 'latest_trade')
    #         chainDF = expand_column(chainDF, 'latest_quote')
    #         chainDF = expand_column(chainDF, 'implied_volatility')
    #         chainDF = expand_column(chainDF, 'greeks')

    #         for col in chainDF.columns:
    #             if chainDF[col].apply(lambda x: isinstance(x, tuple)).any():
    #                 nested_expanded = chainDF[col].apply(pd.Series)
    #                 nested_expanded.columns = [f"{col}_{subcol}" for subcol in nested_expanded.columns]
    #                 chainDF = chainDF.drop(columns=[col]).join(nested_expanded)

    #         columns_to_drop = [col for col in chainDF.columns if str(chainDF[col][1]) in col]
    #         chainDF = chainDF.drop(columns=columns_to_drop)

    #         keywords = ['symbol', 'timestamp', 'exchange', 'price', 'size', 'id', 'conditions','tape']  # List of keywords to search for
    #         for col in chainDF.columns:
    #             if any(keyword in str(cell) for keyword in keywords for cell in chainDF[col]):
    #                 chainDF.drop(columns=[col], inplace=True)

    #         chainDF.columns = ['symbol','implied_volatility',0,'latest_trade_ts','exchange','price','size','id',1,2,3,'latest_quote_ts','ask_exchange','ask_price','ask_size','bid_exchange','bid_price','bid_size','conditions','tape',4,'delta',5,'gamma',6,'rho',7,'theta',8,'vega']
            
    #         columns_to_drop = [col for col in chainDF.columns if any(char.isdigit() for char in str(col))]
    #         chainDF.drop(columns=columns_to_drop, inplace=True)
    #         return chainDF        
        # except Exception as e:
        #     raise

    def to_Dataframe(self,option_chain):
        try:
            chainDF = pd.DataFrame(option_chain).T
            chainDF.columns=['symbol','latest_trade','latest_quote','implied_volatility','greeks']
            chainDF.sort_index(inplace=True)

            def expand_column(input_df, col_name):
                df = input_df.copy()
                columns_to_drop = [col for col in df.columns if col_name not in col]
                df.drop(columns=columns_to_drop,inplace=True)
                col_expanded = df[col_name].apply(lambda x: pd.Series(x, dtype=object))
                if len(col_expanded.columns) > 1:
                    for subcol in col_expanded.columns:
                        nested_expanded = col_expanded[subcol].apply(lambda x: pd.Series(x, dtype=object))
                        nested_expanded.columns = [f"{subcol}_{subcol2}" for subcol2 in nested_expanded.columns]
                        col_expanded = col_expanded.drop(columns=[subcol]).join(nested_expanded)
                col_expanded.columns = [f"{col_name}_{subcol}" for subcol in col_expanded.columns]
                df = df.drop(columns=[col_name]).join(col_expanded)

                for col in df.columns:
                    if df[col].apply(lambda x: isinstance(x, tuple)).any():
                        df2 = df[col].apply(pd.Series)
                        df2.columns = [f"{col}_{subcol}" for subcol in df2.columns]
                        df = df.drop(columns=[col]).join(df2)

                if len(df.columns) > 2:
                    df.drop(df.columns[[0]],axis=1,inplace=True)

                column_labels = df.iloc[1,::2].copy()
                output_df = df.iloc[:,1::2].copy() 
                output_df.columns = column_labels.values

                return output_df.copy()

            symbol = expand_column(chainDF, 'symbol')
            latest_trade = expand_column(chainDF, 'latest_trade')
            latest_quote = expand_column(chainDF, 'latest_quote')
            implied_volatility = expand_column(chainDF, 'implied_volatility')
            greeks = expand_column(chainDF, 'greeks')

            output_chain_df = symbol.join(latest_trade,rsuffix="_latest_trade").join(latest_quote,rsuffix="_latest_quote").join(implied_volatility,rsuffix="_implied_volatility").join(greeks,rsuffix="_greeks")
            return output_chain_df.copy()
        except Exception as e:
            raise

    def get_option_contracts(self, underlying_symbols=None, status="active", expiration_date=None,
                             expiration_date_gte=None, expiration_date_lte=None, root_symbol=None,
                             option_type=None, style='american', strike_price_gte=None, strike_price_lte=None,
                             page_token=None, limit=1000,override=False):
        
        # try:
        #     data=self.parse_chain(underlying_symbol=underlying_symbols,expiration_date_gte=expiration_date_gte,expiration_date_lte=expiration_date_lte)
        #     data_df = self.to_Dataframe(data)
        #     print(data_df.iloc[len(data_df)//2,:])
        # except Exception as e:
        #     print(e)

        try:
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
        
        except (KeyError,ValueError,TypeError,Exception) as e:
            raise   
        
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
        else:
            raise TypeError("invalid symbol input")
                    
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
            underlying = get_ohlc_alpaca(symbols=df['underlying_symbol'].iloc[-1],lookback=365,adjust="all",date_err=False)
        except Exception as e:
            raise Exception(f"[{AlpacaOptionContracts.__name__}] Error: Missing Underlying Price Data for {df['underlying_symbol'].iloc[-1]} : {e}")
        df['underlying_price'] = underlying['close'].iloc[-1]
        df['underlying_price_2'] = underlying['close'].iloc[-7]
        df['ul_vol'] = underlying['close'].pct_change().std()*np.sqrt(365)
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




