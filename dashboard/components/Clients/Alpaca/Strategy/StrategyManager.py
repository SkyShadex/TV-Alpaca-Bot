from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from components.Clients.Alpaca.price_data import get_ohlc_alpaca, get_latest_quote
from components.Clients.Alpaca import executionManager as em
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.requests import GetAssetsRequest
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.models import Position

from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform, pdist
from scipy.stats import zscore, linregress,gaussian_kde,boxcox,median_abs_deviation
from sklearn.linear_model import LinearRegression
import statsmodels.tsa.stattools as ts
from arch import arch_model
import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt
import time
import pytz
from io import StringIO
import seaborn as sns
import datetime as dt
from components.Clients.Alpaca.api_alpaca import api
from components.Clients.Alpaca.options import AlpacaOptionContracts
from components.Clients.Alpaca.Strategy.OptionsOI import Strategy_OI,Strategy_PricingModel
from components.Clients.Alpaca.Strategy.TS_MOM import Strategy_TSMOM
from components.Clients.Alpaca.portfolio import parse_positions, parse_orders
from components.Clients.Alpaca.portfolioManager import PortfolioManager
import re
import threading
import random
import logging
import redis
import config

symbols_tocull = set()

class StrategyManager(threading.Thread):
    def __init__(self,strat="TSMOM",source=1,weight_factor=1.0):
        super().__init__()
        self.weight_factor = weight_factor
        self.live = False
        self.long_only = False
        self.isCrypto = False
        self.source = source
        self.strat = strat
        self.underperforming = []
        starttime = dt.datetime.now()
        self.name = f'{self.name}_{strat}_{source}'
        self.execManager = em.ExecutionManager()
        self.pm = {'DEV' : PortfolioManager(client=api.client['DEV'])}
        self.pm['LIVE'] = PortfolioManager(client=api.client['LIVE'])
        # self.execManager.push_order_db(order=em.SkyOrder(client=api.client['LIVE'],symbol="AAPL",order_type="market",price=20,side="sell",weight=1.5,order_memo="LOL this is a test"))
        logging.info(f"{self.name} Start: {starttime.strftime('%H:%M:%S')}")
        print(f"{self.name} Start: {starttime.strftime('%H:%M:%S')}")
        self.buildUniverse()
        match self.strat:
            case "TSMOM":
                self.run_TSMOM()
            case "TSMOM_O":
                self.run_TSMOM_Options()
            case "HEDGE":
                self.run_PortfolioHedge()
            case "OOI":
                self.run_OOI()
        elapsed_time = (dt.datetime.now() - starttime).total_seconds() // 60
        logging.info(f"{self.name} End. Duration: {elapsed_time} minutes")
        print(f"{self.name} End. Duration: {elapsed_time} minutes")    

    def buildUniverse(self):
        weeklies = ['NKE', 'USB', 'JMIA', 'AG', 'LI', 'TSLL', 'SNDL', 'JOBY', 'CI', 'SO', 'BILL', 'HL', 'CLOV', 'ROST', 'CART', 'GM', 'TZA', 'PYPL', 'EMB', 'CMA', 'ELF', 'EBAY', 'UBER', 'ANF', 'NUGT', 'FTNT', 'DIS', 'SPCE', 'LII', 'BOIL', 'NTES', 'XLC', 'GIS', 'APPS', 'CRM', 'YINN', 'AAP', 'PM', 'ACN', 'NNDM', 'SRPT', 'SLB', 'VOD', 'DAL', 'EMR', 'IVR', 'EXPE', 'STX', 'AIG', 'ULTA', 'BMY', 'CF', 'JDST', 'PCG', 'GSK', 'XBI', 'ET', 'KOLD', 'AMAT', 'CBOE', 'GOOS', 'CMG', 'XLV', 'CRWD', 'COHR', 'APP', 'NOK', 'MRK', 'FIS', 'TLT', 'SHAK', 'STNE', 'NVDA', 'GOLD', 'FL', 'SPXL', 'CNC', 'WMB', 'VIXY', 'BBAI', 'ALB', 'DKS', 'AVXL', 'JPM', 'DPZ', 'CVX', 'AA', 'URA', 'HUM', 'RCL', 'DFS', 'SPGI', 'MARA', 'SLV', 'BA', 'HAL', 'RACE', 'LNG', 'AFRM', 'TJX', 'CMCSA', 'PANW', 'BYND', 'NEP', 'XOP', 'WPM', 'PLUG', 'URBN', 'NU', 'JNJ', 'ORCL', 'QQQ', 'ALLY', 'APA', 'MMM', 'BX', 'EPD', 'UPS', 'ADBE', 'MDLZ', 'INTC', 'JBLU', 'AI', 'CLX', 'UPST', 'LRCX', 'OPEN', 'PNC', 'RUN', 'JETS', 'WAL', 'UEC', 'YPF', 'CVNA', 'GLD', 'IREN', 'USO', 'PG', 'HRL', 'MS', 'GDX', 'KR', 'CSIQ', 'IOVA', 'JD', 'NOC', 'BBWI', 'TFC', 'WDAY', 'VRT', 'TOST', 'WOLF', 'TAN', 'RDFN', 'HIVE', 'ZION', 'RILY', 'GS', 'LEN', 'TSLA', 'PSX', 'BEKE', 'MSTR', 'SAVA', 'RTX', 'PFE', 'BITF', 'ABNB', 'EOG', 'REGN', 'EOSE', 'DIA', 'MRNA', 'GSAT', 'PDD', 'NLY', 'V', 'LULU', 'AXP', 'ETSY', 'LUMN', 'TPR', 'FSLY', 'GRPN', 'MDT', 'JNUG', 'AMGN', 'LAZR', 'WBA', 'T', 'TDOC', 'DDOG', 'IWM', 'TOL', 'LMT', 'WEAT', 'BABA', 'SHOP', 'SMH', 'DOCU', 'HON', 'TEVA', 'FCX', 'FSLR', 'PCT', 'CC', 'UWMC', 'IRBT', 'ARDX', 'META', 'AFL', 'SE', 'AGNC', 'SWKS', 'MU', 'TMUS', 'CHTR', 'APO', 'ADI', 'SPXU', 'IEP', 'CCCC', 'HUT', 'RSP', 'NFLX', 'BTBT', 'FCEL', 'SCHW', 'RUM', 'SBUX', 'ABR', 'IOT', 'VKTX', 'QS', 'ADP', 'MDB', 'NVAX', 'DB', 'FOXA', 'DE', 'MT', 'KSS', 'INTU', 'CZR', 'NEE', 'TSN', 'GD', 'FXI', 'AMBA', 'CRSP', 'MNKD', 'MCD', 'XLP', 'BAX', 'IYR', 'CTRA', 'EFA', 'ARKG', 'LUV', 'MCK', 'DHR', 'PLTR', 'CLSK', 'BKNG', 'TXN', 'AKAM', 'HPQ', 'CHPT', 'XLY', 'BILI', 'BBIO', 'RH', 'KO', 'CIFR', 'TTD', 'STZ', 'DLR', 'CROX', 'NTAP', 'KKR', 'CPNG', 'GLW', 'FAS', 'ASHR', 'MSOS', 'UNP', 'TEAM', 'LQD', 'LCID', 'TECK', 'BAC', 'TQQQ', 'TSM', 'ON', 'AVTR', 'COTY', 'CAT', 'LABD', 'HSBC', 'ONON', 'DBX', 'TAL', 'TUP', 'DJT', 'FDX', 'JWN', 'JNK', 'SOXS', 'PARA', 'PHM', 'BLNK', 'DG', 'GNRC', 'LVS', 'MET', 'CLF', 'GOOG', 'MRVL', 'X', 'RKLB', 'GTLB', 'WBD', 'TRIP', 'CL', 'PXD', 'MGM', 'HOOD', 'SHEL', 'SHOT', 'GEO', 'UAL', 'CAVA', 'ENPH', 'PTON', 'XLF', 'TWLO', 'XLI', 'UPRO', 'DASH', 'BITO', 'SYM', 'CHWY', 'ARKK', 'GE', 'FANG', 'FUBO', 'SPR', 'BMBL', 'AAL', 'EQT', 'ASO', 'IMVT', 'CAR', 'HSY', 'HE', 'APT', 'ADM', 'CVS', 'NYCB', 'ARM', 'ASML', 'U', 'VFS', 'MELI', 'ALT', 'CAH', 'SVXY', 'SQQQ', 'HIMS', 'CSCO', 'ANET', 'CSX', 'VALE', 'Z', 'COF', 'TGT', 'ADSK', 'NEGG', 'VRTX', 'ZIM', 'GOOGL', 'ROKU', 'OKTA', 'SPY', 'LLY', 'BITI', 'OZK', 'ENVX', 'LMND', 'ITB', 'EEM', 'RNG', 'HES', 'NET', 'TMF', 'ISRG', 'ATMU', 'PEP', 'CAN', 'GILD', 'NCLH', 'PBR', 'QCOM', 'VLO', 'COST', 'SU', 'XHB', 'ACHR', 'EA', 'TELL', 'BITX', 'COIN', 'IBM', 'MRO', 'WULF', 'GDDY', 'ILMN', 'LABU', 'ABBV', 'XLE', 'AMC', 'KHC', 'FEZ', 'DVN', 'SDOW', 'MO', 'NXPI', 'ASTS', 'TLRY', 'XOM', 'DOW', 'PAA', 'WM', 'UVXY', 'AZN', 'BIIB', 'MSFT', 'PPG', 'HOG', 'TNA', 'BTU', 'APLD', 'CELH', 'CCJ', 'BURL', 'XLB', 'KWEB', 'UNG', 'MANU', 'MA', 'SMCI', 'SSO', 'NOW', 'PENN', 'BLK', 'URI', 'XPEV', 'SNV', 'SPOT', 'SNAP', 'RIG', 'ZS', 'STNG', 'TGTX', 'NVDL', 'CMI', 'BBY', 'F', 'IONQ', 'CAG', 'NEM', 'GDXJ', 'SQ', 'UNH', 'BIDU', 'KMX', 'KLAC', 'KRE', 'WMT', 'MPC', 'XRT', 'WDC', 'DLTR', 'SOFI', 'SIG', 'NIO', 'SWN', 'AMD', 'BP', 'C', 'RBLX', 'S', 'IEF', 'MTCH', 'KEY', 'W', 'HD', 'GEHC', 'OIH', 'GPS', 'KVUE', 'NKLA', 'WW', 'NTR', 'BUD', 'KMI', 'NVO', 'SOUN', 'XLU', 'AEO', 'WHR', 'BYON', 'GME', 'IVV', 'DKNG', 'OXY', 'EWU', 'CGC', 'AAPL', 'M', 'MVIS', 'VFC', 'AAOI', 'CYTK', 'KGC', 'TMV', 'SPWR', 'SOXL', 'AMZN', 'WYNN', 'FI', 'MAR', 'WFC', 'HYG', 'IQ', 'PINS', 'RKT', 'MPW', 'MOS', 'DHI', 'SEDG', 'URNM', 'SPXS', 'EWZ', 'DELL', 'ZM', 'LOW', 'RIVN', 'XLK', 'CPB', 'EDU', 'SNOW', 'LIN', 'VXX', 'KMB', 'AR', 'RDW', 'UAA', 'ABT', 'FUTU', 'SIRI', 'RIOT', 'XP', 'COP', 'BB', 'LYFT', 'ERX', 'UCO', 'CCL', 'VZ', 'TMO', 'UVIX', 'ALGN', 'AVGO', 'SAVE']
        universe_1 = ['SPY','XLK', 'WEC', 'VZ', 'UPS', 'TSM', 'TRMK', 'TGT', 'TD', 'T', 'SO', 'SNN', 'SNDR', 'BETH', 'SHG', 'SAFT', 'QSR', 'PAYX', 'ORCL', 'MO', 'LLY', 'LDOS', 'KO', 'KEYS', 'KB', 'JBHT', 'IRM', 'HWKN', 'HEDJ', 'GOOGL', 'GILD', 'GBDC', 'FDL', 'EXPO', 'DUK', 'DGRW', 'DBA', 'CSX', 'CHKP', 'CBU', 'CAT', 'BTI', 'BMY', 'APH', 'AMH', 'AEP', 'AEE', 'ABT', 'AAPL']
        etf_leveraged = ['USD', 'BITO', 'NOBL', 'WEBL', 'NUGT', 'SPTS', 'PSQ', 'YINN', 'TQQQ', 'GUSH', 'SOXL', 'JPST', 'ROM', 'MINT', 'QQQE', 'AGQ', 'VXX', 'BIB', 'SPXL', 'UWM', 'VGSH']
        more_etf = ['HYLB', 'VNQ', 'ICF', 'IDEV', 'IDV', 'IEF', 'IEFA', 'IEI', 'IEMG', 'IEUR', 'IEV', 'BLV', 'IGF', 'IGIB', 'IGLB', 'IGM', 'IGSB', 'INDA', 'IOO', 'IQLT', 'FAS', 'BSV', 'IUSB', 'IXUS', 'JAAA', 'KBWB', 'EWP', 'EWM', 'EWL', 'BKLN', 'EWJ', 'EWA', 'EFV', 'GREK', 'BIV', 'MBB', 'MINT', 'FUTY', 'MOAT', 'EZU', 'AIQ', 'FLJP', 'IHAK', 'EMXC', 'EMLC', 'PCEF', 'PHO', 'PJP', 'EIDO', 'POWA', 'EFZ', 'EFAV', 'EFA', 'PSI', 'EEMV', 'EFG', 'EEM', 'EDV', 'EBND', 'QTUM', 'QUS', 'RDVY', 'REET', 'RETL', 'DVY', 'RLY', 'ROBO', 'SCHZ', 'ANGL', 'GDXJ', 'QUAL', 'GDX', 'DIA', 'SHY', 'DGRO', 'SIL', 'SJB', 'DFIV', 'RWO', 'SPIB', 'SPLB', 'SPSB', 'SPTI', 'SPTL', 'SDIV', 'STIP', 'SHYG', 'BBJP', 'ARKX', 'SKYY', 'ARKF', 'BBEU', 'SPAB', 'TECL', 'SPDW', 'SPEM', 'SPTS', 'TFLO', 'FTSM', 'CQQQ', 'FTSL', 'SRLN', 'COWZ', 'TIP', 'TIPX', 'COM', 'TLH', 'FTEC', 'TLT', 'FSTA', 'URA', 'URTH', 'USD', 'USIG', 'USMV', 'VAW', 'VCR', 'VDC', 'VDE', 'VEA', 'VCSH', 'VEU', 'VFH', 'VGIT', 'VGK', 'VGLT', 'VGSH', 'VHT', 'VIG', 'VIGI', 'VLUE', 'VMBS', 'VOX', 'VPL', 'VPU', 'VT', 'VTI', 'VTIP', 'VTV', 'VUG', 'VWO', 'VXUS', 'VYM', 'VYMI', 'FNDE', 'BUG', 'ACWX', 'XT', 'FLRN', 'BOTZ', 'FLOT', 'AAXJ', 'ACWV', 'FIW', 'BNDX', 'BND', 'FEZ', 'HDV', 'HEFA', 'FENY', 'GVI']
        master_list = weeklies+universe_1+etf_leveraged+more_etf
        # crypto = ['XTZ/USD','AAVE/USD','AVAX/USD','BAT/USD','BCH/BTC', 'BCH/USD', 'BTC/USD', 'CRV/USD', 'DOGE/USD', 'DOT/USD', 'ETH/BTC', 'ETH/USD', 'GRT/USD', 'LINK/BTC', 'LINK/USD','LTC/BTC', 'LTC/USD','MKR/USD','SHIB/USD','SUSHI/USD','UNI/BTC','UNI/USD','YFI/USD']
        old = []
        match self.strat:
            case "TSMOM":
                smallest_port = min(len(weeklies),len(universe_1),len(etf_leveraged))
                match self.source:
                    case 1:
                        self.live = True
                        old = universe_1
                        random.shuffle(old)
                        self.validateSymbols(old)
                        samplesize = int(max(smallest_port,len(self.universe)*0.25))
                        self.universe = self.universe[:samplesize]

                    case 3:
                        self.live = True
                        old = weeklies
                        random.shuffle(old)
                        self.validateSymbols(old)
                        samplesize = int(max(smallest_port,len(self.universe)*0.25))
                        self.universe = self.universe[:samplesize]

                    case 4:
                        self.live = False
                        self.long_only = True
                        self.isCrypto = True
                        # random.shuffle(crypto)
                        search_params = GetAssetsRequest(status='active',asset_class='crypto')
                        data = api.get_all_assets(search_params)
                        keys = [list(zip(*row))[0] for row in data]
                        values = [list(zip(*row))[1] for row in data]
                        row_dicts = [dict(zip(keys[i], values[i])) for i in range(len(keys))]
                        crypto = pd.DataFrame(row_dicts)
                        crypto.reset_index(drop=True, inplace=True)
                        crypto_list = crypto['symbol'].to_list()
                        # cleancrypto = [item for item in crypto_list if 'USDC' not in item and 'USDT' not in item]
                        self.universe = crypto_list[:int(len(crypto_list)/3)]

                    case _:
                        self.live = True
                        old = list(set(more_etf+etf_leveraged))
                        self.validateSymbols(old)
                self.universe = list(set(self.universe))
            
            case "TSMOM_O":
                self.live = True
                old = list(set(master_list))
                random.shuffle(old)
                self.validateSymbols(old,False)
                if api.trading_hours(5,16):
                    self.universe = self.universe[:50]

            case "OOI":
                old = list(set(etf_leveraged+more_etf+universe_1+weeklies))
                random.shuffle(old)
                self.validateSymbols(old,False)
                # self.universe = self.universe[:30]
            
            case _:
                old = list(set(etf_leveraged+more_etf+universe_1+weeklies))
                random.shuffle(old)
                self.validateSymbols(old,False)

        print(f'{self.name}: {len(self.universe)} / {len(old)}')
        if not self.live:
            self.pm.pop('LIVE') 
                
    def getOpenPO(self,client=api):
        redis_client = redis.Redis(host=str(config.DB_HOST), port=config.DB_PORT, decode_responses=True)
        if client is api.client['DEV']:
            posdf_json = redis_client.get('current_positions_DEV')
        else:
            posdf_json =  redis_client.get('current_positions_LIVE')
        redis_client.close()

        if posdf_json is not None:
            positions = pd.read_json(StringIO(posdf_json), orient='records')
        else:
            if client is api.client['DEV']:
                self.pm['DEV'].update_holdings(client=client)
                positions = self.pm['DEV'].positions
            else:
                self.pm['LIVE'].update_holdings(client=client)
                positions = self.pm['LIVE'].positions 

        open_orders = client.get_orders(filter=GetOrdersRequest(status='open',limit=500,after=dt.datetime.now() - dt.timedelta(hours=36))) # type: ignore
        if open_orders:
            orders = parse_orders(open_orders)
        else:
            orders = pd.DataFrame()
        return positions,orders

    def killOldOrders(self,client=api.client['DEV'],cutoff=4):
        if not api.trading_hours(10,13):
            return

        orders = self.getOpenPO(client)[1]
        if not orders.empty:
            current_time = dt.datetime.now()
            orders['submission_time'] = pd.to_datetime(orders['submitted_at'],utc=True)
            orders['time_delta'] = current_time - orders['submission_time']
            old_orders = orders[orders['time_delta'] > dt.timedelta(hours=cutoff)]

            # Cancel each old order
            for order_id in old_orders['id']:
                client.cancel_order_by_id(order_id)

            if len(old_orders) > 0:
                print(f'{len(old_orders)} Stale Orders Culled...')

    def baseUniverse(self,*filters):
        search_params = GetAssetsRequest(status='active',attributes='options_enabled') #type: ignore
        data = api.get_all_assets(search_params)
        keys = [list(zip(*row))[0] for row in data]
        values = [list(zip(*row))[1] for row in data]
        row_dicts = [dict(zip(keys[i], values[i])) for i in range(len(keys))]
        assets = pd.DataFrame(row_dicts)

        filtered_assets = assets[
        (assets['tradable'] == True) &
        (assets['easy_to_borrow'] == True) &
        (assets['shortable'] == True) &
        (assets['fractionable'] == True)
        ]
        filtered_assets.reset_index(drop=True, inplace=True)

        if len(filters) > 0:
            pattern = '|'.join(map(re.escape, filters))
            filtered_assets = filtered_assets[filtered_assets['name'].str.contains(pattern, flags=re.IGNORECASE)]

        return filtered_assets

    def validateSymbols(self,input_list,toCull=True):
        validAssets = set(self.baseUniverse()['symbol'])
        self.universe = [ticker for ticker in input_list if ticker in validAssets]
        universe_toCull = [ticker for ticker in input_list if ticker not in validAssets]
        universe_toCull.append('SPXU') # Too correlated
        universe_toCull = list(set(universe_toCull))
        if toCull:
            self.validatePositions(api,universe_toCull)
            if self.live:
                self.validatePositions(api.client['LIVE'],universe_toCull)

    def validatePositions(self,client,culllist):
        pos1 = self.getOpenPO(client)[0]
        if pos1.empty:
            return
                
        rejected_and_held_symbols = pos1[pos1.symbol.isin(culllist)]
        if not rejected_and_held_symbols.empty:
            for index, row in rejected_and_held_symbols.iterrows():
                if (row['market_value'] > row['breakeven'] or abs(row['unrealized_plpc']) > 0.1) and row['qty_available'] != 0:
                    print(f"Closing position for invalid symbol {row['symbol']} due to profit level.")
                    try:
                        client.close_position(row['symbol'])
                    except Exception as e:
                        logging.debug(f"{self.validatePositions.__name__} Error: {e}")
        
    def run_OOI(self): 
        random.shuffle(self.universe)
        options = AlpacaOptionContracts()
        strat = Strategy_OI()
        opm = Strategy_PricingModel()
        positions,orders=self.getOpenPO(api)
        if not positions.empty:
            positions = positions.loc[positions.asset_class.str.contains("us_option",case=False)]

        steps = 0
        for i,symbol in enumerate(self.universe[:]):
            if symbol in symbols_tocull:
                symbols_tocull.remove(symbol)
                continue
            print(f'checking {symbol} for entry signals {i/len(self.universe):.2%} {steps}...')
            steps = 0
            success = False
            try:
                expiry = dt.datetime.today()+dt.timedelta(days=30)
                df_raw = options.get_option_contracts(symbol, expiration_date_lte=expiry.strftime('%Y-%m-%d'), limit=1000)
                success = strat.estimateFV(df_raw,dof=2,mad_lim=0.5)
                if not (strat.isValid and success):
                    symbols_tocull.add(symbol)
                    continue
            except Exception as e:
                continue

            steps += 1
            try:
                price_lim = 10
                # row = strat.rankContract(price_filter=price_lim,limit=30,days_filter=[9,200])
                opm.getData(symbol,maxTime=30,limit=100)
                opm.printStats = True
                opm.fitModel()
                print(opm.minimum)
                row = opm.filterResults(0,45,0.45,0.7,-1.0,0.0,0.25,price_lim,False)
                if row.empty or opm.minimum > 1:
                    continue
                if "BULLISH" in strat.sentiment:
                    side = "C00"
                    menu = row.loc[row['type'] == 'call']
                elif "BEARISH" in strat.sentiment:
                    side = "P00"
                    menu = row.loc[row['type'] == 'put']
                else:
                    side = ""
                    menu = row.sort_values('over/under',ascending=True)

                menu = menu.head(10)
                 
            except Exception as e:
                    continue   
            
            # steps += 1
            # largest_micro_value = -float('inf')
            # std_move = []
            # ohlc_contract = options.get_option_bars(menu.symbol.to_list(), '1Day', '2024-01-03T00:00:00Z')
            # ohlc_contract.set_index('symbol', append=True, inplace=True) 
            # for index, row in menu.iterrows():
            #     try:
            #         symbol_contract = row['symbol']
            #         if symbol_contract not in ohlc_contract.index.get_level_values('symbol'):
            #             continue
            #         try:
            #             symbol_data = ohlc_contract.loc[(slice(None), symbol_contract), :]
            #         except:
            #             symbol_data = ohlc_contract

            #         current_close = symbol_data['c'].iloc[-1]
            #         if row['close_price'] != current_close and current_close > price_lim and current_close > menu.modeled_price:
            #             continue
            #         try:
            #             linear_model_contract = LinearRegression()
            #             X_contract = np.arange(len(symbol_data)).reshape(-1, 1)
            #             linear_model_contract.fit(X_contract, symbol_data['c'])
            #             predictions_contract = linear_model_contract.predict(X_contract)
            #             if predictions_contract[-1] < 0:
            #                 continue
            #         except:
            #             continue

            #         micro_value = np.log(predictions_contract[-1] / current_close)
            #         menu.loc[index, 'micro_value'] = micro_value.round(4)
            #         menu.loc[index, 'close_price'] = current_close
            #         std_move.append(symbol_data['r'].std())

            #         if micro_value > largest_micro_value:
            #             largest_micro_value = micro_value
            #         # time.sleep(0.35)
            #     except Exception as e:
            #         # print(2,e)
            #         continue
            # steps += 1        
            # if 'micro_value' not in menu.columns:
            #     continue

            # if menu.micro_value.max() < np.mean(std_move)*1.5:
            #     continue

            # menu = menu.nlargest(1, 'micro_value')
            if menu.empty:
                continue
            menu = menu.iloc[0]
            
# ---------------------------------------------------------------
            try:
                if not positions.empty:
                    pos = positions.loc[(positions.symbol.str.contains(str(menu.underlying_symbol),case=False))] # & (positions.symbol.str.contains(side,case=False))
                    if not pos.empty:
                        continue

                if not orders.empty:
                    if orders['symbol'].str.contains(menu.symbol,case=False).any():
                        continue

            except Exception as e:
                print(f'{menu.symbol}: {e}')

            steps += 1
            try:
                xtm = "ITM" if menu.moneyness > 0 else "OTM"
                orderid = menu.symbol+"_"+xtm
                # print(ohlc_contract.v.mean()//1)
                entry_price = max(menu.close_price,menu.modeled_price)
                result = em.optionsOrder(menu.symbol,entry_price,client=api,orderID=orderid,side='buy',isMarketOrder=False,weight=1)
                continue
            except Exception as e:
                print(f'{menu.symbol}: {e}')

    def run_PortfolioHedge(self):
        try:
            opm = Strategy_PricingModel()
            # if self.live:
            #     self.live_port = PortfolioManager(client=api.client['LIVE'])
            #     bet_size_LIVE = self.live_port.buyingpower_nm*self.live_port.base_risk
            #     price_AdjustedForContract_LIVE = bet_size_LIVE/100
            #     pricelimit_LIVE = max(price_AdjustedForContract_LIVE,1)
            #     pos_LIVE,ord_LIVE=self.getOpenPO(client=api.client['LIVE'])
            #     if self.live_port.op_ratio>0.4:
            #         logging.warning(f"Low buying power for options on LIVE, {self.live_port.buyingpower_nm}")
            #         self.live = False

            client = api.client['DEV']
            self.pos_dev,self.ord_dev=self.getOpenPO(client)
            strong_signals = self.pos_dev.loc[~(self.pos_dev.unrealized_plpc.between(-0.05,0.05)) & ~(self.pos_dev['asset_class'].str.contains("us_option",case=False))].copy() 
            if strong_signals.empty:
                return
            
            def microstructureCheck(source,quote,adj_factor=1.025):
                        overvalued = source.modeled_price*adj_factor < quote.mid_price
                        spread_pc = quote.spread/source.modeled_price
                        spread_too_wide = spread_pc > 0.5
                        if overvalued or (not overvalued and spread_too_wide):
                            logging.info(f'[{self.name}][REJECTED] {[source.symbol,round(source.modeled_price,2),round(quote.mid_price,2),round(spread_pc,2)]}');return False                        
                        return True

            def checkDupeOrdersAndPositions(source,positions,orders):         
                if not positions.empty and 'symbol' in positions.columns:
                    pos = positions.loc[positions.symbol.str.contains(source.symbol,case=False)]
                    if not pos.empty:return False

                if not orders.empty and 'symbol' in orders.columns:
                    if orders['symbol'].str.contains(source.symbol,case=False).any():return False
                return True

            def placeOrder(client,source,quote,bet_amt_cash=1.0):
                limit_price = min(source.modeled_price,quote.mid_price) #TODO: Handle mid_price returning zero
                if limit_price == 0.0:
                    return False
                xtm = "ITM" if abs(source.delta) > 0.5 else "OTM"
                orderid = source.symbol+"_"+xtm
                volume_limit = max(quote.mid_v//10,1)
                self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=source.symbol,order_type="limit_order",asset_class="options",price=limit_price,order_memo=orderid,side='buy',bet_size=bet_amt_cash,weight=1,volume_limit=volume_limit))
                result = em.optionsOrder(source.symbol,price=limit_price,client=client,orderID=orderid,side='buy',isMarketOrder=False,bet=bet_amt_cash,weight=1,vol_limit=volume_limit)
                if "error" not in result:
                    trade_info = (f'[{self.name}]\n -- [{source.symbol}] \n -- Deltas: [{source.delta:.2f}]  O/U: {source["over/under"]:.2%} R2: {opm.minimum:.2f}\n -- Spread: {quote.spread/source.modeled_price:.2%} Mid: {quote.mid_price:.2f} Model: {source.modeled_price:.2f}')
                    print(trade_info)
                    logging.info(trade_info)
                    return True
                else:
                    logging.info(result)
                    return False
                return False

            def search_Target_Delta(row):
                target_delta = row.qty/100
                direction = "call" if target_delta < 0 else "put"
                res = opm.getData(row.symbol,startoffset=15,maxTime=15,limit=100)
                if res.empty:return False
                    
                opm.fitModel()
                filtered_contracts = opm.filterResults(3,90,0.2,0.6,-1.0,-0.2,0.1,5,False)
                if filtered_contracts.empty:return False

                hedge = filtered_contracts.loc[(filtered_contracts.type==direction)].copy()
                if hedge.empty:return False
                    
                hedge['abs_delta'] = hedge.delta.abs()
                hedge.sort_values('abs_delta', inplace=True, ascending=True)
                hedge = hedge.iloc[0]
                qty = (target_delta//hedge['abs_delta'])*hedge['modeled_price']*100
                if not checkDupeOrdersAndPositions(hedge,self.pos_dev,self.ord_dev):return False
                try:
                    quote = get_latest_quote(hedge.symbol,'options').iloc[0]
                except:
                    return False
                if not microstructureCheck(hedge,quote,adj_factor=1.025):return False
                if not placeOrder(api.client['DEV'],hedge,quote,qty):return False
                return True

            strong_signals.apply(search_Target_Delta,axis=1)

        except Exception as e:
            print(e)

    def run_TSMOM_Options(self):
        random.shuffle(self.universe)
        self.strategy_instances = {}
        opm = Strategy_PricingModel()
        contracts_to_get = 100 if api.trading_hours(5,16) else 300

        if self.live:
            bet_size_LIVE = self.pm['LIVE'].buyingpower_nm*self.pm['LIVE'].base_risk
            price_AdjustedForContract_LIVE = bet_size_LIVE/100
            pricelimit_LIVE = max(price_AdjustedForContract_LIVE,1)
            pos_LIVE,ord_LIVE=self.getOpenPO(client=api.client['LIVE'])
            # self.live_port.options_allocation = api.adjustmentTimed(0.8,0.25,dt.datetime(2024, 5, 20),60) # Raise capital allocation for the time being.
            if (self.pm['LIVE'].op_ratio>self.pm['LIVE'].options_allocation) or self.pm['LIVE'].buyingpower_nm < 150:
                logging.warning(f"Low buying power for options on LIVE, {self.pm['LIVE'].buyingpower_nm}")
                self.live = False


        client = api.client['DEV'] 
        # try:
        #     self.killOldOrders(client)
        # except Exception as e:
        #     print(e)
        self.pos_dev,self.ord_dev=self.getOpenPO(client)
        
        for i,symbol in enumerate(self.universe):
            if i % 25 == 0 and i != 0:
                print(f"o...")
            lookback = int(365*0.4)
            timeframe=TimeFrame(2, TimeFrameUnit('Hour'))
            try:
                assetData = get_ohlc_alpaca(symbol, lookback, timeframe=timeframe,adjust="all",date_err=True)
                strategy_inst = Strategy_TSMOM(assetData, test_size=0.5, initial_investment=100, betsize=0.05, trigger=75, lag=1)
                result = strategy_inst.backtest()
                if not isinstance(result,pd.DataFrame):
                    continue

                sr = strategy_inst.sharpe_ratio.iloc[1]
                time = strategy_inst.time_in_market
                trades = strategy_inst.trade_count
                cagr = strategy_inst.cagr
                trade_eff = abs(cagr)/time
                
                if trade_eff < 0.5:
                    continue

                signal = strategy_inst.tradeSignal()
                direction = "call" if signal > 0 else "put" if signal < 0 else "null"

                if direction == "null":
                    continue

                res = opm.getData(symbol,startoffset=20,maxTime=41,limit=contracts_to_get)                
                if res.empty:
                    continue

                opm.fitModel()
                
                # TODO: Consider moving this out of loop. the value is largely static and creates unnecessary calls
                if self.pm['DEV'].update_values(client=client): 
                    bet_size = self.pm['DEV'].buyingpower_nm*self.pm['DEV'].options_allocation*self.pm['DEV'].base_risk*self.pm['DEV'].options_CF
                    price_AdjustedForContract = bet_size
                    pricelimit = price_AdjustedForContract
                else:
                    continue

                # consider that nudging ITM you need you'll move the entire range, vol skew risk. making everything slightly more expensive.
                delta_range = [0.4,0.6]
                trade_eff_range = [0.5,3.0]
                conf_delta = max(delta_range[1] - (delta_range[1] - delta_range[0]) * ((trade_eff - trade_eff_range[0]) / (trade_eff_range[1] - trade_eff_range[0])),delta_range[0])
                filtered_contracts = opm.filterResults(0,90,conf_delta,delta_range[1],-1.0,1.0,0.25,pricelimit*10,False)
                if filtered_contracts.empty:
                    continue


                # TODO: Encapsulating core logic to clean up later

                def microstructureCheck(source,quote,adj_factor=1.025):
                    overvalued = source.modeled_price*adj_factor < quote.mid_price
                    spread_pc = quote.spread/source.modeled_price
                    spread_too_wide = spread_pc > 0.5
                    if overvalued or (not overvalued and spread_too_wide):
                        logging.info(f'[REJECTED] {[source.symbol,round(source.modeled_price,2),round(quote.mid_price,2),round(spread_pc,2)]}');return False                        
                    return True

                def checkDupeOrdersAndPositions(source,positions,orders):         
                    if not positions.empty and 'symbol' in positions.columns:
                        pos = positions.loc[positions.symbol.str.contains(source.symbol,case=False)]
                        if not pos.empty:print('[]');return False

                    if not orders.empty and 'symbol' in orders.columns:
                        if orders['symbol'].str.contains(source.symbol,case=False).any():print('[]');return False
                    return True

                def placeOrder(client,source,quote,bet_amt_cash=1.0):
                    limit_price = min(source.modeled_price,quote.mid_price)
                    if limit_price == 0.0:
                        return False
                    xtm = "ITM" if abs(source.delta) > 0.5 else "OTM"
                    orderid = source.symbol+"_"+xtm
                    volume_limit = max(quote.mid_v//10,1)
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=source.symbol,order_type="limit_order",asset_class="options",price=limit_price,order_memo=orderid,side='buy',bet_size=bet_amt_cash,weight=1,volume_limit=volume_limit))
                    result = em.optionsOrder(source.symbol,price=limit_price,client=client,orderID=orderid,side='buy',isMarketOrder=False,bet=bet_amt_cash,weight=1,vol_limit=volume_limit)
                    if "error" not in result:
                        trade_info = (f'[{self.name}]\n -- [{symbol}] CAGR: {cagr:.2%} TIM: {time:.1%} SR: {sr:.2f} TC: {trades} Eff: {trade_eff:.1%}\n -- Deltas: [{conf_delta:.2f} , {source.delta:.2f}]  O/U: {source["over/under"]:.2%} R2: {opm.minimum:.2f}\n -- Spread: {quote.spread/source.modeled_price:.2%} Mid: {quote.mid_price:.2f} Model: {source.modeled_price:.2f}')
                        print(trade_info)
                        logging.info(trade_info)
                        return True
                    else:
                        logging.info(result)
                        return False
                    return False

                def force2ndLeg(client,leg1,bet_amt_cash=1.0):
                    if 'C00' in leg1.symbol:
                        leg2_symbol = leg1.symbol.replace('C00', 'P00')

                    elif 'P00' in leg1.symbol:
                        leg2_symbol = leg1.symbol.replace('P00', 'C00')

                    quote = get_latest_quote(leg2_symbol,'options').iloc[0]
                    limit_price = np.nanmean([leg1.modeled_price*(abs(leg1['over/under'])+1),quote.mid_price])
                    volume_limit = max(quote.mid_v//10,1)
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=leg2_symbol,order_type="limit_order",asset_class="options",price=limit_price,order_memo=leg2_symbol,side='buy',bet_size=bet_amt_cash,weight=1,volume_limit=volume_limit))
                    result = em.optionsOrder(leg2_symbol,price=limit_price,client=client,orderID=leg2_symbol,side='buy',isMarketOrder=False,bet=bet_amt_cash,weight=1,vol_limit=volume_limit)
                    
                            
                # one looped loop to keep breaks simple
                for j in range(1):
                    # ========================== Primary leg  ==========================
                    if self.pm['DEV'].op_ratio>self.pm['DEV'].options_allocation:
                        logging.warning(f"Low buying power for options, {self.pm['DEV'].op_ratio}/{self.pm['DEV'].options_allocation}")
                        break

                    menu = filtered_contracts.loc[(filtered_contracts.type==direction) & (filtered_contracts['close_price'] <= pricelimit)].copy()
                    if menu.empty:break

                    # parametric assumption that the undervalued contracts are actually relatively undervalued.
                    menu = menu.loc[(filtered_contracts['over/under'] <= filtered_contracts['over/under'].quantile(0.5))].copy()
                    # print(menu.iloc[0].symbol)
                    # print(menu[['strike_price','delta','close_price','modeled_price','over/under']].describe())
                    menu['abs_delta'] = menu.delta.abs()
                    menu.sort_values('abs_delta', inplace=True, ascending=True)
                    menu = menu.iloc[0]

                    if not checkDupeOrdersAndPositions(menu,self.pos_dev,self.ord_dev):break

                    try:
                        quote = get_latest_quote(menu.symbol,'options').iloc[0]
                    except:
                        break
                    if not microstructureCheck(menu,quote,adj_factor=1.025):break
                    if not placeOrder(api.client['DEV'],menu,quote,bet_size/2):break

                    # ========================== Aim to create a straddle leg where possible ==========================
                    straddle = filtered_contracts.loc[(filtered_contracts.type!=direction) & (filtered_contracts['close_price'] <= pricelimit)].copy()
                    if straddle.empty:
                        print('[STRADDLE BREAK]')
                        force2ndLeg(client,menu,bet_size)
                        break

                    # parametric assumption that the undervalued contracts are actually relatively undervalued.
                    straddle = straddle.loc[(straddle['over/under'] <= straddle['over/under'].quantile(0.50))].copy()

                    straddle['abs_delta'] = straddle.delta.abs()
                    straddle.sort_values('abs_delta', inplace=True, ascending=True)
                    straddle = straddle.iloc[0]

                    if not checkDupeOrdersAndPositions(straddle,self.pos_dev,self.ord_dev):break
                    try:
                        quote = get_latest_quote(straddle.symbol,'options').iloc[0]
                    except:
                        force2ndLeg(client,menu,bet_size)
                        break
                    if not microstructureCheck(straddle,quote,adj_factor=1.025):force2ndLeg(client,menu,bet_size);break
                    if not placeOrder(api.client['DEV'],straddle,quote,bet_size):break
                    

                # Push orders to LIVE if conditions met
                if self.live:
                    for j in range(1):
                        leg_1 = filtered_contracts.loc[(filtered_contracts.type==direction) & (filtered_contracts['over/under'].between(-1,-0.05)) & (filtered_contracts['close_price'] <= pricelimit_LIVE)].copy()
                        if leg_1.empty:break
                            
                        leg_1['abs_delta'] = leg_1.delta.abs()
                        leg_1.sort_values('abs_delta', inplace=True, ascending=True)
                        leg_1 = leg_1.iloc[0]
                        if leg_1.modeled_price > pricelimit_LIVE:print('[]');break

                        if not checkDupeOrdersAndPositions(leg_1,pos_LIVE,ord_LIVE):break
                        try:
                            quote = get_latest_quote(leg_1.symbol,'options').iloc[0]
                        except:
                            break
                        if not microstructureCheck(leg_1,quote,adj_factor=1.025):break

                        # limit_price = min(leg_1.modeled_price,quote.mid_price)
                        # orderid = leg_1.symbol+"COPY"
                        # result = em.optionsOrder(leg_1.symbol,limit_price,client=api.client['LIVE'],orderID=orderid,side='buy',isMarketOrder=False,bet=1,weight=1,vol_limit=max(quote.mid_v//10,1))
                        # if "error" not in result:
                        #     print("[PROD] Copy Trade Initiated")
                        if not placeOrder(api.client['LIVE'],leg_1,quote,1.0):break

                        # Break the loop for LIVE for captial restricions
                        self.pm['LIVE'].update_values(api.client['LIVE'])
                        if self.pm['LIVE'].buyingpower_nm < 150:
                            self.live = False

                        # ========================== Aim to create a straddle leg where possible ==========================
                        leg_2 = filtered_contracts.loc[(filtered_contracts.type!=direction) & (filtered_contracts["over/under"] < abs(leg_1["over/under"])) & (filtered_contracts['close_price'] <= pricelimit_LIVE)].copy()
                        if leg_2.empty:print('[]');break

                        leg_2['abs_delta'] = leg_2.delta.abs()
                        leg_2.sort_values('abs_delta', inplace=True, ascending=True)
                        leg_2 = leg_2.iloc[0]
                        if leg_2.modeled_price > pricelimit_LIVE:print('[]');break

                        if not checkDupeOrdersAndPositions(leg_2,pos_LIVE,ord_LIVE):break
                        
                        try:
                            quote = get_latest_quote(leg_2.symbol,'options').iloc[0]
                        except:
                            break
                        if not microstructureCheck(leg_2,quote,adj_factor=1.025):break

                        if not placeOrder(api.client['LIVE'],leg_2,quote,1.0):break
            except Exception as e:
                logging.debug(f"{self.run_TSMOM_Options.__name__} Error: {e}")
                continue

    def run_TSMOM(self):    
        random.shuffle(self.universe)
        self.strategy_instances = {}

        self.pos_dev,self.ord_dev=self.getOpenPO(api.client['DEV'])
        if self.live:
            self.pos_live,self.ord_live=self.getOpenPO(api.client['LIVE'])

        for i,symbol in enumerate(self.universe[:]):
            if i % 25 == 0 and i != 0:
                print("...")
            # if len(self.universe) > 50:
            #     lookback = int(365*2)
            #     timeframe=TimeFrame(1, TimeFrameUnit('Day'))
            # else:
            lookback = int(365*2)
            timeframe=TimeFrame(12, TimeFrameUnit('Hour'))
            try:
                assetData = get_ohlc_alpaca(symbol, lookback, timeframe=timeframe,adjust="split",date_err=True)
            except Exception as e:
                print(e)

            if not isinstance(assetData,pd.DataFrame):continue
            if assetData.empty:print("problem....................");continue
                
            strategy_inst = Strategy_TSMOM(assetData, test_size=0.3, initial_investment=100, betsize=0.05, trigger=75, lag=1)
            result = strategy_inst.backtest()
            if not isinstance(result,pd.DataFrame):continue
            if result.empty:continue
                    
            self.strategy_instances[symbol] = strategy_inst
        self.buildPortfolio(0.05)

    def buildPortfolio(self,min_weight=0.01):
        max_start_date = max(instance.asset_OHLC.index.min() for instance in self.strategy_instances.values())
        min_end_date = min(instance.asset_OHLC.index.max() for instance in self.strategy_instances.values())

        # Ensure max_start_date and min_end_date are timezone-aware
        if max_start_date.tzinfo is None:
            max_start_date = max_start_date.tz_localize('UTC')
        if min_end_date.tzinfo is None:
            min_end_date = min_end_date.tz_localize('UTC')

        date_range_days = (min_end_date - max_start_date).days
        print(f"Number of years in the range: {date_range_days}")

        aligned_returns_dict = {}
        aligned_risk_dict = {}

        for symbol, instance in self.strategy_instances.items():
            # Ensure the index is timezone-aware
            if instance.asset_OHLC.index.tzinfo is None:
                instance.asset_OHLC.index = instance.data.asset_OHLC.tz_localize('UTC')
            
            returns = instance.asset_OHLC['log_returns'].loc[(instance.asset_OHLC.index >= max_start_date) & (instance.asset_OHLC.index <= min_end_date)].copy()
            returns = returns.fillna(0)
            returns_resampled = returns.resample('1h').sum()
            aligned_returns_dict[symbol] = returns_resampled
            aligned_risk_dict[symbol] = instance.asset_OHLC['CVaR'].iloc[-1]

        try:
            corr_matrix = pd.DataFrame({symbol: returns.values for symbol, returns in aligned_returns_dict.items()}).corr()
            self.symbol_to_index = {symbol: i for i, symbol in enumerate(corr_matrix.index)}
            weights = self.herc_model(corr_matrix,aligned_risk_dict,min_weight)

        except Exception as e:
            logging.debug(f"{self.buildPortfolio.__name__} Error: {e}")

        try:    
            for symbol, instance in self.strategy_instances.items():
                signal = instance.tradeSignal() 
                weight = weights[self.symbol_to_index[symbol]]
                # print(symbol,signal,weight)
                self.handleOrders(instance,signal,symbol,weight)
                if self.live:
                    self.prodExecution(instance,signal,symbol,weight)
        except Exception as e:
            logging.debug(f"{self.buildPortfolio.__name__} Error 2: {e}")

    def handleOrders(self,instance,signal,symbol,weight=1):
        client = api
        try:
            isPositionOpen = False
            if not self.pos_dev.empty:
                equities = self.pos_dev.loc[self.pos_dev['asset_class'].str.contains('equity', case=False)]
                position = equities.loc[equities['symbol'].str.lower() == symbol.lower()]
                # print(len(self.pos_dev),len(pos_11),len(position))
                if not position.empty:
                    pos_signal = 1.0 if "long" in position['side'].iloc[-1] else -1.0 # type: ignore
                    isPositionOpen = position['symbol'].str.contains(symbol, case=False).any()
        except Exception as e: 
            raise RuntimeError(e)

        isOpenOrder = False
        if not self.ord_dev.empty:  
            match = self.ord_dev.loc[(self.ord_dev['symbol'].str.lower() == symbol.lower()) & (self.ord_dev['symbol'].str.len() == len(symbol))] # type: ignore
            isOpenOrder = not match.empty

        isConfirmed = signal == -1.0 or signal == 1.0
        sr = instance.sharpe_ratio.iloc[1]
        time_in_market = instance.time_in_market
        trades = instance.trade_count
        cagr = instance.cagr
        trade_eff = cagr/time_in_market
        # logging.info(f'TEST: {instance.name} CAGR: {cagr:.2%} TIM: {time:.1%} SR: {sr:.2f} TC: {trades} Eff: {trade_eff:.1%}')

        try:
            performance_filter = api.adjustmentTimed(0.05,0.2,dt.datetime(2024, 5, 4),30)
            if trade_eff<performance_filter:
                self.underperforming.append(symbol)
                if isPositionOpen and position.qty_available.iloc[-1] > 0:
                    print(f'Low performer: {instance.name} CAGR: {cagr:.2%} TIM: {time_in_market:.1%} SR: {sr:.2f} TC: {trades} Eff: {trade_eff:.1%}/{performance_filter:.1%}')
                    logging.info(f'Low performer: {instance.name} CAGR: {cagr:.2%} TIM: {time_in_market:.1%} SR: {sr:.2f} TC: {trades} Eff: {trade_eff:.1%}/{performance_filter:.1%}')
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="exit",order_memo=instance.id))
                    result = em.exitOrder(symbol,orderID=instance.id)
                return

            if isPositionOpen:
                if not isOpenOrder:
                    if not isConfirmed:
                        # Close position if not confirmed
                        print(f'Closing {instance.name} SR: {sr:.3f} Weight: {weight:.4f}')
                        logging.info(f'Closing {instance.name} SR: {sr:.3f} Weight: {weight:.4f}')
                        self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="exit",order_memo=instance.id))
                        result = em.exitOrder(symbol, orderID=instance.id)
                        return result
                    elif isConfirmed and signal != pos_signal:
                        # Flip position if confirmed but signal has changed
                        print(f'Flipping {instance.name} SR: {sr:.3f} Weight: {weight:.4f}')
                        logging.info(f'Flipping {instance.name} SR: {sr:.3f} Weight: {weight:.4f}')
                        self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="exit",order_memo=instance.id))
                        result = em.exitOrder(symbol, orderID=instance.id)
                        time.sleep(3)  # pause before a new position is taken

            # Handle no open position or order scenarios
            elif not isPositionOpen and not isOpenOrder:
                if isConfirmed:
                    # Handle trade initiation based on the signal
                    side = 'sell' if signal == -1.0 else 'buy' if signal == 1.0 else 'unsure'
                    if side == 'sell' and self.long_only:
                        return  # Prevent selling if only long trades are allowed
                    
                    ls_weight = self.portfolio_balance(client, side, weight)
                    trade_info = f'Opening {instance.name} CAGR: {cagr:.2%} TIM: {time_in_market:.1%} SR: {sr:.2f} TC: {trades} Eff: {trade_eff:.1%}/{performance_filter:.1%}\n --  Weight: {weight:.4f} LS Weight: {ls_weight:.4f} side: {side}'
                    print(trade_info)
                    logging.info(trade_info)
                    # if self.isCrypto:
                    #     price = get_ohlc_alpaca(symbol, 14, timeframe=TimeFrame(2, TimeFrameUnit('Hour')),adjust="split",date_err=True)['close'].iloc[-1]
                    #     print(price)
                    # else:
                    quote = get_latest_quote(symbol)
                    price = quote['mid_price'].iloc[0]
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="market",price=price,side=side,weight=ls_weight,order_memo=instance.id))
                    result = em.entryOrder(symbol,price,instance.id,side=side,isMarketOrder=True,weight=ls_weight)
                    return result
                
            # Handle open orders that are not confirmed
            if not isConfirmed and isOpenOrder:
                self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="cancel_order"))
                result = client.cancel_order_by_id(match.id.iloc[-1])
                return result 
                   
        except Exception as e:
            if "cannot be sold short" not in str(e):
                # print(f'{instance.name}: {e}')
                logging.exception(f'{instance.name}: {e}')
            else:
                logging.debug(f'{instance.name}: {e}')

    def prodExecution(self,instance,signal,symbol,weight=1):
        client = api.prod
        try:
            isPositionOpen = False
            if not self.pos_live.empty:
                equities = self.pos_live.loc[self.pos_live['asset_class'].str.contains('equity', case=False)]
                position = equities.loc[equities['symbol'].str.lower() == symbol.lower()]
                if not position.empty:
                    pos_signal = 1.0 if "long" in position['side'].iloc[-1] else -1.0 # type: ignore
                    isPositionOpen = position['symbol'].str.contains(symbol, case=False).any()
        except Exception as e: 
            raise RuntimeError(e)

        # orderParams = GetOrdersRequest(status='open', limit=20, nested=False, symbols=[symbol])  # type: ignore
        # orders = api.get_orders(filter=orderParams)    

        # try:
        isOpenOrder = False
        if not self.ord_live.empty:  
            match = self.ord_live.loc[(self.ord_live['symbol'].str.lower() == symbol.lower()) & (self.ord_live['symbol'].str.len() == len(symbol))] # type: ignore
            isOpenOrder = not match.empty

        isConfirmed = signal == -1.0 or signal == 1.0
        sr = instance.sharpe_ratio.iloc[1]
        time_in_market = instance.time_in_market
        trades = instance.trade_count
        cagr = instance.cagr
        trade_eff = cagr/time_in_market

        try:
            performance_filter = api.adjustmentTimed(0.05,0.2,dt.datetime(2024, 5, 4),30)
            if trade_eff<performance_filter:
                self.underperforming.append(symbol)
                if isPositionOpen and position.qty_available.iloc[-1] > 0:
                    print(f'[PROD]: Low performer: {instance.name} CAGR: {cagr:.2%} TIM: {time_in_market:.1%} SR: {sr:.2f} TC: {trades} Eff: {trade_eff:.1%}/{performance_filter:.1%}')
                    logging.info(f'[PROD]: Low performer: {instance.name} CAGR: {cagr:.2%} TIM: {time_in_market:.1%} SR: {sr:.2f} TC: {trades} Eff: {trade_eff:.1%}/{performance_filter:.1%}')
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="exit",order_memo=instance.id))
                    result = em.exitOrder(symbol,client=client,orderID=instance.id)
                return

            if isPositionOpen and not isOpenOrder:
                if (not isConfirmed):
                    print(f'[PROD]: Closing {instance.name} SR: {sr:.3f} Weight: {weight:.4f}')
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="exit",order_memo=instance.id))
                    result = em.exitOrder(symbol,client=client,orderID=instance.id)
                    return result

                if (isConfirmed and signal != pos_signal):
                    print(f'[PROD]: Flipping {instance.name} SR: {sr:.3f} Weight: {weight:.4f}')
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="exit",order_memo=instance.id))
                    result = em.exitOrder(symbol,client=client,orderID=instance.id)
                    time.sleep(3)

            if (not isConfirmed and not isPositionOpen and isOpenOrder):
                self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="cancel_order"))
                client.cancel_order_by_id(match.id.iloc[-1])
                return

            if isConfirmed and (not isPositionOpen and not isOpenOrder):
                side = 'sell' if signal == -1.0 else 'buy' if signal == 1.0 else 'unsure'
                if side == 'sell':
                    # print(f'[PROD]: Rejected {instance.name} [LONG ONLY]')
                    return
                print(f'[PROD]: Opening {instance.name} SR: {sr:.3f} Weight: {weight:.4f} side: {side}')
                # print(f'bt_positon: {instance.isOpenPosition} bt_signal: {instance.isCurrentSignal} ')
                if self.isCrypto:
                    price = get_ohlc_alpaca(symbol, 2, timeframe=TimeFrame(2, TimeFrameUnit('Hour')),adjust="split",date_err=True)['close'].iloc[-1]
                else:
                    quote = get_latest_quote(symbol)
                    price = quote['mid_price'].iloc[0]
                    self.execManager.push_order_db(order=em.SkyOrder(client=client,symbol=symbol,order_type="market",price=price,side=side,weight=weight,order_memo=instance.id))
                    result = em.entryOrderProd(symbol,price,instance.id,side=side,isMarketOrder=True,weight=weight)
                    return result
        except Exception as e:
            print(f'[PROD]:  {instance.name}: {e}')
        
    def portfolio_balance(self,client,side,weight):
        if self.long_only:
            return weight

        if side == "sell":
            if client is api.client['LIVE']:
                pm = self.pm['LIVE']
            else:
                pm = self.pm['DEV']

            if pm.update_values(client=client):
                correctionFactor = pm.ls_ratio*pm.stock_allocation
                correctionFactor *= self.weight_factor
                return weight*correctionFactor
        
        return weight

    def hrp_model(self,correlation_matrix):
        distance_matrix = np.sqrt(0.5 * (1 - correlation_matrix))
        linkage_matrix = hierarchy.linkage(squareform(distance_matrix), method='ward')
        clusters = hierarchy.cut_tree(linkage_matrix, n_clusters=2)
        inv_var_clusters = []
        for cluster in np.unique(clusters):
            assets_in_cluster = np.where(clusters == cluster)[0]
            inv_var = 1 / distance_matrix.iloc[assets_in_cluster, assets_in_cluster].sum(axis=1)
            inv_var_clusters.append((assets_in_cluster, inv_var))
        
        weights = np.zeros(len(correlation_matrix))

        for assets_in_cluster, inv_var in inv_var_clusters:
            for asset_index in assets_in_cluster:
                symbol = correlation_matrix.index[asset_index]
                # print(f"Asset Index: {asset_index}, Symbol: {symbol}")
                # print("Shape of weights array:", weights.shape)
                # print("Type of weights array:", type(weights))
                # print("Asset Index:", asset_index, "Symbol:", symbol)
                # print("Value of inv_var:", inv_var)
                inv_var_sum = inv_var.sum()
                if inv_var_sum != 0 and not np.isnan(inv_var_sum):
                    weights[self.symbol_to_index[symbol]] = inv_var.iloc[0] / inv_var_sum
                else:
                    weights[:] = 1 / len(self.symbol_to_index)
        return weights    
        
    def herc_model(self, corr_matrix, risk_metric, min_weight=0.07):
        distance_matrix = np.sqrt(0.5 * (1 - corr_matrix))
        linkage_matrix = hierarchy.linkage(squareform(distance_matrix), method='ward')
        clusters = hierarchy.cut_tree(linkage_matrix, n_clusters=2)
        inv_volatility = 1 / np.array(list(risk_metric.values()))
        weights = np.zeros(len(corr_matrix))
        for cluster in np.unique(clusters):
            assets_in_cluster = np.where(clusters == cluster)[0]
            total_inv_vol = inv_volatility[assets_in_cluster].sum()
            if total_inv_vol > 0:  # Avoid division by zero
                # Calculate weights with minimum weight constraint
                weights[assets_in_cluster] = np.maximum(inv_volatility[assets_in_cluster] / total_inv_vol, min_weight)
            else:
                weights[assets_in_cluster] = np.maximum(1 / len(assets_in_cluster), min_weight)  # Equal weight if total_inv_vol is zero
        return weights

    def herc_model_constrained(self, corr_matrix, risk_metric, min_weight=0.07):
        # Calculate the distance matrix and linkage matrix
        distance_matrix = np.sqrt(0.5 * (1 - corr_matrix))
        linkage_matrix = hierarchy.linkage(squareform(distance_matrix), method='ward')
        clusters = hierarchy.cut_tree(linkage_matrix, n_clusters=2)
        
        # Calculate inverse volatility and initialize weights
        inv_volatility = 1 / np.array(list(risk_metric.values()))
        weights = np.zeros(len(corr_matrix))
        
        # Calculate initial weights based on clusters
        for cluster in np.unique(clusters):
            assets_in_cluster = np.where(clusters == cluster)[0]
            total_inv_vol = inv_volatility[assets_in_cluster].sum()
            
            if total_inv_vol > 0:  # Avoid division by zero
                # Calculate weights with minimum weight constraint
                weights[assets_in_cluster] = inv_volatility[assets_in_cluster] / total_inv_vol
            else:
                # Equal weight if total_inv_vol is zero
                weights[assets_in_cluster] = 1 / len(assets_in_cluster)
        
        # Constrain weights to include the minimum weight
        underweight_indices = np.where(weights < min_weight)[0]
        if underweight_indices.size > 0:
            # Calculate the total deficit
            total_deficit = np.sum(min_weight - weights[underweight_indices])
            
            # Set underweight indices to min_weight
            weights[underweight_indices] = min_weight
            
            # Redistribute the deficit across remaining weights proportionally
            remaining_indices = np.where(weights >= min_weight)[0]
            remaining_weight_sum = np.sum(weights[remaining_indices])
            
            if remaining_weight_sum > 0:
                # Adjust remaining weights
                weights[remaining_indices] += (total_deficit / remaining_weight_sum) * weights[remaining_indices]
        
        # Ensure the final sum of weights is 1
        weights /= np.sum(weights)
        
        return weights



            
