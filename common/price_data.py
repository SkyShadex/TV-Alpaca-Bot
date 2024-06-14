from common.api_alpaca import api
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
from io import StringIO
import time
import redis
import logging
import json
from io import StringIO

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
    
def get_ohlc_alpaca(symbols: str|list[str], lookback: int, timeframe: TimeFrame=TimeFrame(1, TimeFrameUnit('Day')),adjust: str="split",date_err: bool=True,useCache: bool=True) -> pd.DataFrame:
    """
        Wrapper for getting price data. Currently just for Stocks and Crypto, not Options.

        Args:
            symbol (str): The symbol for the asset.
            lookback (int): Number of days to look back from Current Date (Currently Localized to EST).
            timeframe: TimeFrame object from Alpaca. See Alpaca Docs.
            adjust (str): The type of corporate action data normalization.
            date_err (bool): Reject symbols that don't return nearly complete data set. Default set to True.
            useCache (bool): Use RedisDB to cache price data to reduce API calls. Default set to True.
        """
    NY_TIMEZONE = pytz.timezone('America/New_York')
    UTC_TIMEZONE = pytz.timezone('UTC')
    current_date = pd.Timestamp.now(tz=UTC_TIMEZONE)
    oldFound = False
    loopSymbols = False
    sleep_duration = 0
    tf = str(timeframe)

    if isinstance(symbols, (pd.Series,list)):
        loopSymbols = True
        useCache = False
        symCount = len(symbols)
        print(get_ohlc_alpaca.__name__,82303579834986) # TODO: Check if this is being used as a pd/list anywhere????
        if symCount >= 200:
            sleep_duration = 200 // 60
            print(f'Est. Time: {(sleep_duration*symCount)//60}mins')
    else:
        symbols = [symbols] # Ensure symbols is always treated as a list
        symCount = len(symbols)
        if useCache:
            old_price_data = retrieve_ohlcv_db(symbols[0],timeframe)
            if not old_price_data.empty:
                daterange = (old_price_data['date'].max() - old_price_data['date'].min()).days
                if daterange >= 100:
                    logging.debug(f'OHLCV:{symbols[0]}:{str(timeframe)} [CACHED]',daterange)
                    lookback = min(10,lookback)
                    oldFound = True
                    date_err = False
                else:
                    print(f'OHLCV:{symbols[0]}:{str(timeframe)} [NEW]',daterange)
                    lookback = max(365*3,lookback) if tf.endswith("Day") else max(365*1.5,lookback)
                    lookback = int(lookback)
                    date_err = False
    
    all_ohlcv = []
    all_value_at_risk = {}
    skipped_symbols = []

    start_date = current_date - dt.timedelta(days=lookback)           
    for i, symbol in enumerate(symbols):
        if symCount > 1 and loopSymbols:
            percent_complete = (i + 1) / symCount * 100
            print(f"Progress: {percent_complete:.2f}% complete {symbol}", flush=True)
            time.sleep(sleep_duration)

        asset = api.get_asset(symbol)
        isCrypto = asset.asset_class == AssetClass.CRYPTO
        if isCrypto:
            params = CryptoBarsRequest(symbol_or_symbols=symbol, start=start_date, timeframe=timeframe)
            price_data = apCrypto.get_crypto_bars(params)
        else:    
            params = StockBarsRequest(symbol_or_symbols=symbol, start=start_date, timeframe=timeframe, adjustment=adjust)
            price_data = apHist.get_stock_bars(params)

        ohlcv = price_data.df

        if not isinstance(ohlcv,pd.DataFrame):
            raise Exception(f"Expected Dataframe from Alpaca: {symbol}")    
        if len(ohlcv) <= 1:
            raise Exception(f"Insufficient Bar Data: [{symbol},{len(ohlcv)}]")    

        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'trade_count', 'vwap']
        ohlcv[numeric_columns] = ohlcv[numeric_columns].apply(pd.to_numeric, errors='raise')

        ohlcv = ohlcv.reset_index()
        ohlcv = ohlcv.drop_duplicates(keep='first')

        # add metrics
        ohlcv['symbol'] = symbol
        ohlcv['log_returns'] = np.log(ohlcv['close']).diff()
        ohlcv['freq'] = tf
        ohlcv['log_returns'] = ohlcv['log_returns'].fillna(0)
        value_at_risk = ohlcv['log_returns'].quantile(0.05)
        losses_below_var = ohlcv[ohlcv['log_returns'] < value_at_risk]['log_returns']
        ohlcv['CVaR'] = losses_below_var.mean()
        ohlcv['CVaR'] = ohlcv['CVaR'].fillna(0)
        ohlcv['isGap'] = ~(ohlcv['close'].shift(1).between(ohlcv['low'], ohlcv['high']))
        # gap_count = ohlcv['isGap'].sum()
        # print(f"\n\n Gap % for symbol {symbol} {tf}: {gap_count/len(ohlcv):.2%}")
        all_value_at_risk[symbol] = value_at_risk

        try:
            ohlcv['date'] = pd.to_datetime(ohlcv['timestamp'],utc=True)
            ohlcv.set_index(pd.DatetimeIndex(ohlcv['date'],tz=UTC_TIMEZONE),inplace=True)
            ohlcv.sort_index(inplace=True)
        except Exception as e:
            raise

        if ohlcv.isin([np.inf, -np.inf, np.nan]).any().any() and not isCrypto:
            skipped_symbols.append(symbol)
            logging.warning("Exogenous variable contains 'inf' or 'NaN' values.")
            for column in ohlcv.columns:
                if ohlcv[column].isin([np.inf, -np.inf, np.nan]).any():
                    logging.warning(f"Error values in column: {column}")

        days_collected = (ohlcv['date'].max() - ohlcv['date'].min()).days
        if days_collected <= lookback*0.95 and symCount > 1 and date_err:         # Filter Out Incomplete Data
            skipped_symbols.append(symbol)
            logging.warning(f"Expected {lookback*0.95:.0f} days of data, received {days_collected}")
            continue 
        
        all_ohlcv.append(ohlcv)
     
    if len(skipped_symbols) != 0:
        logging.warning(f'symbols skipped: {skipped_symbols}')

    if len(all_ohlcv) == 1:  # Single symbol request
        if not useCache:
            return all_ohlcv[0]
        if oldFound:
            new_df = pd.concat([old_price_data,all_ohlcv[0]])
            new_df.set_index(pd.DatetimeIndex(new_df['date'],tz=UTC_TIMEZONE),inplace=True)
            new_df.drop_duplicates(keep='last',inplace=True)
            new_df.sort_index(inplace=True)
            return store_ohlcv_db(new_df,new_df.iloc[0].symbol,timeframe)
        return store_ohlcv_db(all_ohlcv[0],all_ohlcv[0].iloc[0].symbol,timeframe)
    elif len(all_ohlcv) == 0:
        return pd.DataFrame()
        raise RuntimeError("No valid data returned")

    return pd.concat(all_ohlcv)




def store_ohlcv_db(ohlcv,symbol,timeframe,cached=True):
    redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
    ts = redis_client.ts()
    def store_ohlcv_TS(row):
        labels = {col: str(row[col]) for col in row.index}
        ts.add(f'TS-OHLCV:{row.symbol}:{str(timeframe)}',int(row.name.timestamp() * 1000),float(row.close),labels=labels,duplicate_policy='last')
        ...    


    KEY = f'OHLCV:{symbol}:{str(timeframe)}'
    UTC_TIMEZONE = pytz.timezone('UTC')
    try:
        price_data_old_json = redis_client.get(KEY)
        if price_data_old_json is not None:
            price_data_old = pd.read_json(StringIO(price_data_old_json), orient='records')

            # price_data_old['timestamp'] = pd.to_datetime(price_data_old['timestamp'], utc=True)
            # ohlcv['timestamp'] = pd.to_datetime(ohlcv['timestamp'], utc=True)
            price_data_complete = pd.concat([price_data_old, ohlcv])
            price_data_complete['date'] = pd.to_datetime(price_data_complete['timestamp'],utc=True)
            price_data_complete.set_index(pd.DatetimeIndex(price_data_complete['date'],tz=UTC_TIMEZONE),inplace=True)
            price_data_complete.drop_duplicates(subset=['timestamp'], keep='last',inplace=True)
            price_data_complete.sort_index(inplace=True)
            
            if not ("Hour" in str(timeframe) or "Min" in str(timeframe)):
                price_data_complete.apply(store_ohlcv_TS,axis=1)
            price_data_complete['isGap'] = ~(price_data_complete['close'].shift(1).between(price_data_complete['low'], price_data_complete['high']))
            gappc = round(price_data_complete['isGap'].sum()/len(price_data_complete['isGap']),2)
            redis_client.hset(f'asset:metrics:gappc',key=symbol,value=gappc)
            price_data_complete_json = price_data_complete.to_json(orient='records')
            redis_client.set(KEY,price_data_complete_json,ex=12*3600)
            ohlcv_new = price_data_complete.copy()
        else:
            price_data_complete_json = ohlcv.to_json(orient='records')
            redis_client.set(KEY,price_data_complete_json,ex=12*3600)
            ohlcv_new = ohlcv.copy()
        redis_client.close()
        return ohlcv_new.sort_index()
    except (KeyError,ValueError,TypeError,Exception) as e:
        error_message = f'[{store_ohlcv_db.__name__}] Error for {KEY}: {e}'
        logging.warning(error_message)
        redis_client.delete(KEY)
        raise Exception(error_message) 

def retrieve_ohlcv_db(symbol,timeframe):
    redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
    KEY = f'OHLCV:{symbol}:{str(timeframe)}'
    UTC_TIMEZONE = pytz.timezone('UTC')
    try:
        price_data_old_json = redis_client.get(KEY)
        if price_data_old_json is not None:
            price_data_old = pd.read_json(StringIO(price_data_old_json), orient='records')
            price_data_old['date'] = pd.to_datetime(price_data_old['timestamp'],utc=True)
            price_data_old.drop_duplicates(keep='last',inplace=True)
            price_data_old.set_index(pd.DatetimeIndex(price_data_old['date'],tz=UTC_TIMEZONE),inplace=True)
            return price_data_old
        return pd.DataFrame()
    except (KeyError,ValueError,TypeError,Exception) as e:
        error_message = f'[{retrieve_ohlcv_db.__name__}] Error for {KEY}: {e}'
        logging.warning(error_message)
        redis_client.delete(KEY)
        raise Exception(error_message)
    
def randomStats(db_client: redis.Redis = None):
    # db_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
    metrics = db_client.hgetall("asset:metrics:gappc")
    metrics = {str(symbol): float(data) for symbol, data in metrics.items()}
    metrics_df = pd.DataFrame(metrics.items(), columns=['symbol', 'priceGaps_to_totalBars'])
    metrics_df.set_index('symbol', inplace=True)
    metrics_df['priceGaps_to_totalBars'] = metrics_df['priceGaps_to_totalBars'].astype(float)
    return metrics_df