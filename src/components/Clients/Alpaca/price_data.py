from components.Clients.Alpaca.api_alpaca import api
from alpaca.trading.enums import AssetClass
from alpaca.data.requests import StockBarsRequest, StockLatestQuoteRequest,CryptoBarsRequest,CryptoLatestQuoteRequest,OptionLatestQuoteRequest
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.crypto import CryptoHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import pandas as pd
import pytz
import datetime as dt
import numpy as np
import config
import time
import redis
import logging


apHist = StockHistoricalDataClient(config.API_KEY,config.API_SECRET)
apCrypto = CryptoHistoricalDataClient(config.API_KEY,config.API_SECRET)
apOpt = OptionHistoricalDataClient(config.API_KEY,config.API_SECRET)

def get_latest_quote(symbol,mode='equity'):
    match mode:
        case 'crypto':
            quoteParams = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
            q = apCrypto.get_crypto_latest_quote(quoteParams,feed="us")
        case 'equity':
            quoteParams = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            q = apHist.get_stock_latest_quote(quoteParams)
        case 'options':
            quoteParams = OptionLatestQuoteRequest(symbol_or_symbols=symbol)
            q = apOpt.get_option_latest_quote(quoteParams)
            
    data = []

    if isinstance(q, dict):
        for symbol, quote in q.items():
            ask_price = quote.ask_price
            ask_size = quote.ask_size
            bid_price = max(quote.bid_price,2.2250738585072014e-308) # reduce errors from bid_price being zero in live environments
            bid_size = quote.bid_size
            spread = ask_price - bid_price
            mid_price = (ask_price+bid_price)/2 
            total_volume = ask_size + bid_size
            if total_volume != 0.0:
                weighted_mid_price = ((ask_price * ask_size) + (bid_price * bid_size)) / total_volume
                mid_price = weighted_mid_price
            logging.debug({'symbol': symbol,
                         'ask_price': ask_price,
                         'ask_size': ask_size,
                         'bid_price': bid_price,
                         'bid_size': bid_size,
                         'mid_price': mid_price,
                         'mid_price_raw': (ask_price+bid_price)/2,
                         'mid_v': total_volume,
                         'spread': spread})    
            data.append({'symbol': symbol,
                         'ask_price': ask_price,
                         'ask_size': ask_size,
                         'bid_price': bid_price,
                         'bid_size': bid_size,
                         'mid_price': mid_price,
                         'mid_price_vw': (ask_price+bid_price)/2,
                         'mid_v': total_volume,
                         'spread': spread})
        quote = pd.DataFrame(data)
        quote['spread_pc'] = 1-np.log(quote['bid_price']/quote['ask_price'])
        return quote
    
def get_ohlc_alpaca(symbols, lookback, timeframe=TimeFrame(1, TimeFrameUnit('Day')),adjust="split",date_err=True):
    NY_TIMEZONE = pytz.timezone('America/New_York')
    current_date = pd.Timestamp.now(tz=NY_TIMEZONE)
    oldFound = False
    sleep_duration = 0
    # Ensure symbols is always treated as a list
    if isinstance(symbols, pd.Series):
        symCount = len(symbols)
        if symCount >= 200:
            sleep_duration = 200 // 60
            print(f'Est. Time: {(sleep_duration*symCount)//60}mins')
    else:
        symbols = [symbols]
        symCount = len(symbols)
        old_price_data = retrieve_ohlcv_db(symbols[0],timeframe)
        if len(old_price_data) > 1500:
            lookback = 30
            oldFound = True
            date_err = False
        else:
            lookback = 365*10
            date_err = False
    
    all_ohlcv = []
    all_value_at_risk = {}
    skipped = 0

    start_date = current_date - dt.timedelta(days=lookback)           
    for i, symbol in enumerate(symbols):
        percent_complete = (i + 1) / symCount * 100
        if symCount > 1:
            print(f"Progress: {percent_complete:.2f}% complete {symbol}", flush=True)
            time.sleep(sleep_duration)

        asset = api.get_asset(symbol)
        isCrypto = asset.asset_class == AssetClass.CRYPTO
        if isCrypto:
            params = CryptoBarsRequest(symbol_or_symbols=symbol, start=start_date, timeframe=timeframe)
            price_data = apCrypto.get_crypto_bars(params)
            # print(asset.asset_class,symbol)
        else:    
            params = StockBarsRequest(symbol_or_symbols=symbol, start=start_date, timeframe=timeframe, adjustment=adjust)
            price_data = apHist.get_stock_bars(params)
            
        ohlcv = price_data.df

        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'trade_count', 'vwap']
        ohlcv[numeric_columns] = ohlcv[numeric_columns].apply(pd.to_numeric, errors='raise')

        ohlcv = ohlcv.reset_index()
        ohlcv = ohlcv.drop_duplicates(keep='first')
        ohlcv['symbol'] = symbol
        ohlcv['log_returns'] = np.log(ohlcv['close']).diff()
        ohlcv['log_returns'] = ohlcv['log_returns'].fillna(0)
        ohlcv['vol_tc'] = ohlcv['volume'] / ohlcv['trade_count'] # divide by zero???

        value_at_risk = ohlcv['log_returns'].quantile(0.05)
        losses_below_var = ohlcv[ohlcv['log_returns'] < value_at_risk]['log_returns']
        ohlcv['CVaR'] = losses_below_var.mean()
        all_value_at_risk[symbol] = value_at_risk

        try:
            ohlcv['date'] = pd.to_datetime(ohlcv['timestamp'])
            ohlcv = ohlcv.set_index(pd.DatetimeIndex(ohlcv['date']))
        except Exception as e:
            logging.warning(e)
            raise e

        if ohlcv.isin([np.inf, -np.inf, np.nan]).any().any() and not isCrypto:
            skipped += 1
            # print("Exogenous variable contains 'inf' or 'NaN' values.")
            continue 
            # raise ValueError("Exogenous variable contains 'inf' or 'NaN' values.")

        days_collected = (ohlcv['date'].max() - ohlcv['date'].min()).days
        if days_collected <= lookback*0.95 and symCount > 1 and date_err:         # Filter Out Incomplete Data
            skipped += 1
            # print("Incomplete data")
            continue 
        
        all_ohlcv.append(ohlcv)
        # print(f'append: {symbol} {len(all_ohlcv)}')
        
        
    # if skipped != 0:
    #     print(f'symbols skipped: {skipped}')
    if len(all_ohlcv) == 1:  # Single symbol request
        if oldFound:
            all_ohlcv = pd.concat([old_price_data,all_ohlcv[0]])
            all_ohlcv.drop_duplicates(keep='last',inplace=True)
            store_ohlcv_db(all_ohlcv,all_ohlcv.iloc[0].symbol,timeframe)
            return all_ohlcv
        store_ohlcv_db(all_ohlcv[0],all_ohlcv[0].iloc[0].symbol,timeframe)
        return all_ohlcv[0]
    elif len(all_ohlcv) == 0:
        raise RuntimeError("No valid data returned")
    else:
        return pd.concat(all_ohlcv)
    

def store_ohlcv_db(ohlcv,symbol,timeframe):
    redis_client = redis.Redis(host=str(config.DB_HOST), port=int(str(config.DB_PORT)), decode_responses=True)
    try:
        key = f'OHLCV_{symbol}_{str(timeframe)}'
        price_data_old_json = redis_client.get(key)
        if price_data_old_json is not None:
            price_data_old = pd.read_json(price_data_old_json, orient='records')

            price_data_old['timestamp'] = pd.to_datetime(price_data_old['timestamp'], utc=True)
            ohlcv['timestamp'] = pd.to_datetime(ohlcv['timestamp'], utc=True)
            # print(key,len(ohlcv),len(price_data_old),len(ohlcv)+len(price_data_old))
            price_data_merge = pd.concat([price_data_old, ohlcv]).sort_values(by='timestamp')
            # print(key,price_data_merge['timestamp'].iloc[-1],price_data_merge.shape)
            price_data_merge['date'] = pd.to_datetime(price_data_merge['timestamp'],utc=True)
            price_data_complete = price_data_merge.drop_duplicates(subset=['timestamp'], keep='last')
            price_data_complete = price_data_complete.set_index(pd.DatetimeIndex(price_data_complete['date']))

            # print(key,price_data_complete.shape)
            price_data_complete_json = price_data_complete.to_json(orient='records')
            redis_client.set(key,price_data_complete_json)
        else:
            price_data_complete_json = ohlcv.to_json(orient='records')
            print(key,"new",ohlcv.shape)
            redis_client.set(key,price_data_complete_json)
        redis_client.close()
    except Exception as e:
        print(3573483,e)

def retrieve_ohlcv_db(symbol,timeframe):
    redis_client = redis.Redis(host=str(config.DB_HOST), port=int(str(config.DB_PORT)), decode_responses=True)
    try:
        key = f'OHLCV_{symbol}_{str(timeframe)}'
        price_data_old_json = redis_client.get(key)
        redis_client.close()
        if price_data_old_json is not None:
            price_data_old = pd.read_json(price_data_old_json, orient='records')
            price_data_old.drop_duplicates(keep='last',inplace=True)
            return price_data_old
        return pd.DataFrame()
    except Exception as e:
        print(e)
