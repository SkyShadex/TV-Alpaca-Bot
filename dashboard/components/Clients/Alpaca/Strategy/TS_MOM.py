from sklearn.model_selection import train_test_split
from scipy.signal import savgol_filter
from scipy.stats import zscore,boxcox
import scipy.sparse as sp
from pykalman import KalmanFilter
from arch import arch_model
import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt
import seaborn as sns
import datetime as dt
from components.Clients.Alpaca.api_alpaca import api
from components.Clients.Alpaca.portfolio import parse_positions
import time
import redis
import json
import config
import cProfile
import pstats

class Strategy_TSMOM:
    def __init__(self, data_OHLC, test_size=0.5,initial_investment = 500,betsize=0.1,trigger=75,lag=2,reversal=True):
        self.name = None
        self.test_size = test_size
        self.initial_investment = initial_investment
        self.betsize = betsize
        self.trigger = trigger
        self.reversal = reversal
        self.lag = lag
        self.id = 'TSMOM_V1'
        self.init_state = False
        self.complete_state = self.update(data_OHLC)
        

    def update(self, data_OHLC):
        if isinstance(data_OHLC,pd.DataFrame):
            if not data_OHLC.empty:
                self.asset_OHLC = data_OHLC.copy()
                self.name = f"{Strategy_TSMOM.__name__}_{data_OHLC['symbol'].iloc[-1]}_{data_OHLC['freq'].iloc[-1]}"
                self.init_state = True
                return True
        return False

    def backtest(self):
        try:

            pr = cProfile.Profile()
            pr.enable()

            if self.complete_state:self.preprocess_data()
            if self.complete_state:self.calculate_trigger_points()
            if self.complete_state:self.generate_signals()
            if self.complete_state:self.process_signal()
            if self.complete_state:self.validate_backtest()
            if self.complete_state:self.calculate_time()
            if self.complete_state:self.calculate_sharpe()
            if self.complete_state:self.calculate_performance()
            if self.complete_state:self.calculate_performance_cash()
            # if self.complete_state:self.visualize_metrics()
            
            pr.disable()

            # ps = pstats.Stats(pr).sort_stats(pstats.SortKey.CUMULATIVE)
            # print(self.data.shape)
            # ps.print_stats(5)
            # print(f"\n\n\n")

            if self.complete_state:return self.data    
            # else:raise Exception("Model Building failed")
            
        except ValueError as ve:
            print(f'{self.name}: {self.backtest.__name__}, ValueError: {ve}');return False
        except TypeError as te:
            print(f'{self.name}: {self.backtest.__name__}, TypeError: {te}');return False
        except KeyError as ke:
            print(f'{self.name}: {self.backtest.__name__}, KeyError: {ke}');return False
        except Exception as e:
            print(f'{self.name}: {self.backtest.__name__}, Exception: {e}');return False

    def validate_backtest(self):
        try:
            self.data = self.signals.copy()
            self.data['strategy'] = self.data['positions'].shift(max(self.lag,1)) * self.data['log_returns']
            self.data['strategy_raw'] = self.data['positions'] * self.data['log_returns']
            entry_time = []
            exit_time = []
            self.inpos = 0

            for date, pos_Tracked in zip(self.data.index, self.data['positions']):
                if self.inpos == 0 and pos_Tracked != 0:
                    entry_time.append(date)
                    self.inpos = 1

                elif self.inpos == 1 and pos_Tracked == 0:
                    exit_time.append(date)
                    self.inpos = 0
                

            if len(entry_time) <= 1:
                self.complete_state = False
            else:
                self.entry_time = entry_time
                self.exit_time = exit_time

        except ValueError as ve:
            print(f'{self.name}: {self.validate_backtest.__name__}, ValueError: {ve}');self.complete_state = False
        except TypeError as te:
            print(f'{self.name}: {self.validate_backtest.__name__}, TypeError: {te}');self.complete_state = False
        except KeyError as ke:
            print(f'{self.name}: {self.validate_backtest.__name__}, KeyError: {ke}');self.complete_state = False
        except Exception as e:
            print(f'{self.name}: {self.validate_backtest.__name__}, Exception: {e}');self.complete_state = False


    # def track_backtest(self):
    #     self.entry_time = []
    #     self.exit_time = []
    #     self.inpos = 0

    #     for idx, date in enumerate(self.data.index):
    #         pos_Tracked = self.data['positions'].iloc[idx]
    #         if self.inpos == 0 and pos_Tracked != 0:
    #             self.entry_time.append(date)
    #             self.inpos = 1

    #         elif self.inpos == 1 and pos_Tracked == 0:
    #             self.exit_time.append(date)
    #             self.inpos = 0
        
        # if len(self.entry_time) > 0.0 or len(self.exit_time) > 0.0:
        #     raise RuntimeError(f"No trades returned Entry: {len(self.entry_time)} Exit: {len(self.exit_time)}")    
        
    def preprocess_data(self):
        try:
            # Split data into training and testing sets
            self.train_data, self.test_data = train_test_split(self.asset_OHLC, test_size=self.test_size, shuffle=False)

            # Preprocess training data
            transformed_data_train, self.lambda_parameter= boxcox(self.train_data['log_returns'] + 1,lmbda=None) # type: ignore

            # Fit GARCH model to training data
            train_z = zscore(transformed_data_train)
            garch_model = arch_model(train_z, vol='FIGARCH')
            garch_result = garch_model.fit(disp='off')
            self.cond_volatility_train = garch_result.conditional_volatility

            # Preprocess testing data using parameters from training
            transformed_data_test = boxcox(self.test_data['log_returns'] + 1, lmbda=self.lambda_parameter)
            cond_volatility_test = np.repeat(self.cond_volatility_train[-1], len(transformed_data_test))
            self.normalized_returns_test = transformed_data_test / cond_volatility_test

        except ValueError as ve:
            print(f'{self.name}: {self.preprocess_data.__name__}, ValueError: {ve}');self.complete_state = False
        except TypeError as te:
            print(f'{self.name}: {self.preprocess_data.__name__}, TypeError: {te}');self.complete_state = False
        except KeyError as ke:
            print(f'{self.name}: {self.preprocess_data.__name__}, KeyError: {ke}');self.complete_state = False
        except Exception as e:
            print(f'{self.name}: {self.preprocess_data.__name__}, Exception: {e}');self.complete_state = False    
    
    def calculate_trigger_points(self):
        upside = self.normalized_returns_test[self.normalized_returns_test > 0]
        downside = self.normalized_returns_test[self.normalized_returns_test < 0]
        self.be_short = np.percentile(upside, self.trigger) 
        self.be_long = np.percentile(downside, 100 - self.trigger) 
        # return be_short, be_long
        
    def generate_signals(self):
        self.signals = self.test_data.copy()
        moving_avg = savgol_filter(self.signals['close'], 100, 3)

        above_ma = self.signals['close'] > moving_avg
        below_ma = self.signals['close'] < moving_avg

        self.signals['z'] = self.normalized_returns_test
        self.signals['z_upper_limit'] = self.be_short
        self.signals['z_lower_limit'] = self.be_long
        self.signals['signals'] = 0
        # self.signals.loc[(above_ma) & (self.signals['z'] > self.signals['z_upper_limit']),'signals'] = -1
        # self.signals.loc[(below_ma) & (self.signals['z'] < self.signals['z_lower_limit']),'signals'] = 1

        conditions = [
            (above_ma) & (self.signals['z'] > self.signals['z_upper_limit']),
            (below_ma) & (self.signals['z'] < self.signals['z_lower_limit'])
            ]
        choices = [1,-1] if self.reversal else [-1,1]

        self.signals['signals'] = np.select(conditions, choices, default=self.signals['signals'])
        # self.signals['signals'] = self.signals['signals'].replace(0,np.nan).fillna(0)
        # self.signals['positions'] = self.signals['signals'].replace(0, method='ffill').fillna(0)
    
    def process_signal(self): 
        # cache_key = f"kalman_state_{self.asset_OHLC['symbol'].iloc[-1]}_{self.asset_OHLC['freq'].iloc[-1]}"       
        # def serialize_kalman_state(state_mean, state_covariance):
        #     """Serialize Kalman state to JSON string."""
        #     return json.dumps({
        #         'state_mean': state_mean.tolist(),
        #         'state_covariance': state_covariance.tolist()
        #         })

        # def deserialize_kalman_state(state_json):
        #     """Deserialize Kalman state from JSON string."""
        #     state_dict = json.loads(state_json)
        #     state_mean = np.array(state_dict['state_mean'])
        #     state_covariance = np.array(state_dict['state_covariance'])
        #     return state_mean, state_covariance
        
        
        try:
            # redis_client = redis.Redis(host=str(config.DB_HOST), port=int(str(config.DB_PORT)), decode_responses=True)
            # cached_state = redis_client.get(cache_key)
            # if cached_state:
            #     print(f"[CACHED] Kalman Filter state for {self.name}")
            #     state_mean, state_covariance = deserialize_kalman_state(cached_state)
            #     em_vars=['']

            # Smoothing Method

            # state_mean = 0
            # state_covariance = 1
            # delta = 1e-3
            # trans_cov = delta / (1 - delta) * np.eye(1)

            # # Initialize Kalman Filter
            # kf = KalmanFilter(
            #     transition_matrices=[1],
            #     observation_matrices=[1],
            #     initial_state_mean=state_mean,
            #     initial_state_covariance=state_covariance,
            #     observation_covariance=1,
            #     transition_covariance=trans_cov
            #     )
            # state_means, state_covariances = kf.smooth(self.signals['signals'])

            self.signals['processed_signal_savgol_filter'] = savgol_filter(self.signals['signals'],5,3)           

            # Cache the final Kalman state
            # redis_client.set(cache_key, serialize_kalman_state(state_means[0], state_covariances[0]),ex=24*60*60)

            # Normalize the smoothed signal

            self.signals['processed_signal'] = zscore(self.signals['processed_signal_savgol_filter'])
            # cutoff = 1
            # positions = np.where(processed_signal[:, 0] > cutoff, -1,  # If signal > cutoff, set position to -1
            #             np.where(processed_signal[:, 0] < -cutoff, 1,  # If signal < -cutoff, set position to 1
            #             0))  # Otherwise, set position to 0

            self.signals['positions'] = self.signals['processed_signal'].clip(-1,1)
            self.signals.loc[self.signals['positions'].between(-1,1,inclusive='neither'),'positions'] = 0.0
            
            if self.reversal:
                self.signals['positions'] *= -1

        except ValueError as ve:
            print(f'{self.name}: {self.process_signal.__name__}, ValueError: {ve}');self.complete_state = False
        except TypeError as te:
            print(f'{self.name}: {self.process_signal.__name__}, TypeError: {te}');self.complete_state = False
        except KeyError as ke:
            print(f'{self.name}: {self.process_signal.__name__}, KeyError: {ke}');self.complete_state = False
        except Exception as e:
            print(f'{self.name}: {self.process_signal.__name__}, Exception: {e}');self.complete_state = False          
    
    @staticmethod
    def trading_cost(strategy_return, cost_rate=0.01):
        """
        Calculate trading costs based on the strategy return and a fixed cost rate.
        
        Args:
        - strategy_return (float): The return of the strategy for a single trade.
        - cost_rate (float): The fixed cost rate per trade.
        
        Returns:
        - float: The trading cost for the trade.
        """
        return abs(strategy_return) * cost_rate

    def calculate_time(self):
        try:
            
            
            if self.inpos == 1:
                self.exit_time.append(self.data.index[-1])    

            # print(len(self.entry_time),len(self.exit_time))
            entry = pd.DataFrame(self.entry_time) 
            exit = pd.DataFrame(self.exit_time)
            trade_time_info = pd.DataFrame()

            trade_time_info["entry_time"] = entry
            trade_time_info["exit_time"] = exit
            trade_time_info['seconds'] = (trade_time_info["exit_time"] - trade_time_info["entry_time"]).dt.total_seconds() # type: ignore
            trade_time_info['minutes'] = trade_time_info['seconds']/60
            trade_time_info['hours'] = trade_time_info['minutes']/60
            trade_time_info['days'] = trade_time_info['hours']/24
            trade_time_info['weeks'] = trade_time_info['days']/7

            first_entry_time = pd.to_datetime(trade_time_info.entry_time.min())
            last_exit_time = pd.to_datetime(trade_time_info.exit_time.max())

            # seconds_per_year = 86400
            # tradingdays_factor = (252*seconds_per_year)/(365*seconds_per_year)
            trade_window = (last_exit_time - first_entry_time).total_seconds()
            cumulative_exposures = trade_time_info['seconds'].sum()
            trade_time_info['cumulative_exposure'] = (cumulative_exposures / trade_window)
            self.trade_count = len(trade_time_info)
            self.time_in_market = trade_time_info["cumulative_exposure"].iloc[-1]
            self.data['trading_costs'] = self.data['strategy'].apply(self.trading_cost, cost_rate=0.01)
            self.data['cumulative_trading_costs'] = self.data['trading_costs'].cumsum()
        except ValueError as ve:
            print(f'{self.name}: {self.calculate_time.__name__}, ValueError: {ve}');self.complete_state = False
        except TypeError as te:
            print(f'{self.name}: {self.calculate_time.__name__}, TypeError: {te}');self.complete_state = False
        except KeyError as ke:
            print(f'{self.name}: {self.calculate_time.__name__}, KeyError: {ke}');self.complete_state = False
        except Exception as e:
            print(f'{self.name}: {self.calculate_time.__name__}, Exception: {e}');self.complete_state = False    
    
    def calculate_sharpe(self):
        amr_log =  self.data[['log_returns', 'strategy']].mean() * 252
        asd_log =  self.data[['log_returns', 'strategy']].std() * 252 ** 0.5

        # amr_norm = np.exp( self.data[['log_returns', 'strategy']].mean() * 252) - 1
        # asd_norm = ( self.data[['log_returns', 'strategy']].apply(np.exp) - 1).std() * 252 ** 0.5
        risk_free_rate = 0.05*self.time_in_market # Adjusted for time in the Market 
        sharpe_ratio = (amr_log - np.log(1+risk_free_rate)) / asd_log
        self.sharpe_ratio = sharpe_ratio.abs()

    def calculate_performance(self):
        self.data['cumret'] = self.data['strategy'].cumsum().apply(np.exp)
        self.data['cummax'] = self.data['cumret'].cummax()
        self.data['equity_pc'] = self.data['cumret'] 
        self.data['balance_pc'] = self.data['cummax']
        self.latest_balance = self.data['cummax'].iloc[-1]
        self.latest_equity = self.data['cumret'].iloc[-1]

        #Calculate Drawdown
        self.data['drawdown'] = self.data['cummax'] - self.data['cumret']
        self.drawdown_max = self.data['drawdown'].max().round(2)
        self.drawdown_latest = self.data['drawdown'].iloc[-1].round(2)

        #calculate CAGR
        start_date = self.data.index[0]
        end_date = self.data.index[-1]
        total_years = (end_date - start_date).days / 365.25
        start_value = self.data['cumret'].iloc[self.lag]
        if start_value != 0:  # To avoid division by zero
            cagr = (self.latest_equity / start_value) ** (1 / total_years) - 1
        else:
            cagr = np.nan
        self.cagr = cagr
        # print(f'{self.name} {self.cagr:.2%} {self.time_in_market:.2%} {self.trade_count}')

    def calculate_performance_cash(self):
        try:
            self.data['cumret_cash'] = self.initial_investment * self.betsize * np.exp(self.data['strategy'].cumsum())
            # self.data['cumret_cash'] = (1 + self.data['cumret_cash']).cumprod()  # Convert returns to cumulative returns
            self.data['cummax_cash'] = self.data['cumret_cash'].cummax()
        except:
            self.data['cumret_cash'] = self.initial_investment * np.exp(self.data['strategy'].cumsum())
            self.data['cummax_cash'] = self.data['cumret_cash'].cummax()  
        
    def tradeSignal(self):
        latest_signal = self.data['positions'].iloc[-1]
        stable_signal = sum(self.data['positions'].iloc[-3:]) / 3
        self.isOpenPosition = self.inpos == 1
        self.isCurrentSignal = latest_signal != 0

        if (self.isOpenPosition and self.isCurrentSignal) or (self.isCurrentSignal):
            return stable_signal
        return 6969

    def visualize_metrics(self):
        if "12Hour" in str(self.name):
            fig, axs = plt.subplots(3, 3, figsize=(20, 20))
            fig.suptitle(f"{self.name}", fontsize="x-large")

            axs[0, 0].plot(self.signals['z'], alpha=0.7, label='z')
            axs[0, 0].set_title("z")

            axs[0, 1].plot(self.signals['signals'], alpha=0.7, label='signals')
            axs[0, 1].set_title("signals")

            axs[1, 0].plot(self.signals['processed_signal_savgol_filter'], alpha=0.7, label='Savitzky-Golay')
            axs[1, 0].set_title("Savitzky-Golay")

            axs[1, 1].plot(self.signals['processed_signal'], alpha=0.7, label='Savitzky-Golay-Z')
            axs[1, 1].set_title("Savitzky-Golay-Z")

            axs[2, 0].plot(self.signals['positions'], alpha=0.7, label='Positions')
            axs[2, 0].set_title("Positions")

            axs[0, 2].plot(self.asset_OHLC['close'], alpha=0.7, label='Price Data', color='orange')
            axs[0, 2].set_title("Price Data")

            axs[1, 2].plot(self.data['close'], alpha=0.7, label='Price Data', color='orange')
            axs[1, 2].set_title("Test Data")

            axs[2, 2].plot(self.data[['balance_pc','equity_pc','drawdown']], alpha=0.7)
            axs[2, 2].set_title("Strategy Performance")

            # fig.tight_layout(rect=[0.0, 0.03, 1.0, 0.95])
            filename = f'logs/graphs/strat/{self.name}_{dt.datetime.now().strftime("%Y-%m-%d")}.png'
            fig.savefig(filename)
            plt.close(fig)