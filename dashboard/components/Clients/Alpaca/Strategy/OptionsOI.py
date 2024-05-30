import seaborn as sns
import datetime as dt
import pandas as pd
import numpy as np 
import matplotlib.pyplot as plt

from components.Clients.Alpaca.options import AlpacaOptionContracts
from scipy.optimize import minimize, Bounds, brentq
from scipy.stats import zscore, linregress,gaussian_kde,boxcox,median_abs_deviation, norm
# from sklearn.model_selection import KFold, TimeSeriesSplit, GridSearchCV, train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import silhouette_score
# from pykalman import KalmanFilter

class Strategy_OI:
    def __init__(self):
        self.isValid = False
  
    def estimateFV(self,df: pd.DataFrame,dof=1,retplot=True,mad_lim=0.6):
        # model = LinearRegression()
        # model.fit(df[['days_to_expiry']], df['moneyness'])
        # slope = model.coef_[0]
        # y_first = model.predict(df[['days_to_expiry']].iloc[[0]])
        # if y_first < 0:
        #     raise ValueError(f"Negative Expected Return")
        # if slope > 0:
        #     raise ValueError(f"Negative Time Skew on Expected Returns")
        
        try:
            decay_rate = 0.0055
            weights = np.exp(-decay_rate * df['days_to_expiry'])
            df['weighted_open_interest'] = df['open_interest'] * weights
            best_silhouette_score = -1
            best_num_bins = -1
            num_bins_range = range(2, 20)
            for num_bins in num_bins_range:
                close_bins = pd.qcut(df['weighted_open_interest'], q=num_bins, retbins=True, duplicates='drop')[0]
                silhouette = silhouette_score(df[['weighted_open_interest']], close_bins)
                if silhouette > best_silhouette_score:
                    best_silhouette_score = silhouette
                    best_num_bins = num_bins

            close_bins, bin_edges = pd.qcut(zscore(df['weighted_open_interest']), q=best_num_bins, retbins=True,duplicates='drop')
            # print(f'split into {best_num_bins} qbins')
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

            # Fit polynomial regression for 25th, 50th, and 75th percentiles
            reg_df = df.groupby(close_bins, observed=True)['strike_price']
            fair_values = {}
            for percentile in [0.05,0.10,0.25,0.50,0.75,0.90,0.95]:
                coeffs = np.polyfit(bin_centers, reg_df.quantile(percentile).values,deg=dof,full=False)
                fair_value = np.polyval(coeffs, bin_centers[-1])
                fair_values[f"fair_value_nl_{percentile*100}"] = fair_value

            self.fair_values = [fair_values[key] for key in sorted(fair_values.keys())]
            fair_value_nl_25 = self.fair_values[2]
            fair_value_nl_50 = self.fair_values[3]
            fair_value__nl_75 = self.fair_values[4]

            # print("fair value estimate range:",self.fair_values)
            fair_value = fair_value_nl_50
        except Exception as e:
            return False
            raise RuntimeError(f"Not enough data for regression\n{e}")

        close_ul = df['underlying_price'].iloc[-1]

        total_open_interest = df['open_interest'].sum()
        cumulative_open_interest = df.groupby(close_bins,observed=True)['open_interest'].cumsum()
        idx = (cumulative_open_interest <= total_open_interest * 0.5).idxmax()
        open_interest_balance = df.loc[idx, 'strike_price']

        close_ul_scaled = (close_ul - np.min(self.fair_values)) / (np.max(self.fair_values) - np.min(self.fair_values))
        fair_values_scaled = (self.fair_values - np.min(self.fair_values)) / (np.max(self.fair_values) - np.min(self.fair_values))
        absolute_diffs = np.abs(close_ul_scaled  - fair_values_scaled )
        mad = np.mean(absolute_diffs)
        
        strength_score = 0

        if fair_value_nl_25 < open_interest_balance < fair_value__nl_75:
            strength_score += 0.5

        if fair_value_nl_25 < fair_value_nl_50 < fair_value__nl_75:
            strength_score += 2
        else:
            strength_score -= 10
                
        if fair_value_nl_25 < close_ul < fair_value__nl_75 or fair_value_nl_25 > close_ul > fair_value__nl_75:
            strength_score -= 0.5
        else:
            strength_score += 1
        
        direction = "NEUTRAL" if mad > 0.5 else "BULLISH" if close_ul > fair_value_nl_50 else "BEARISH"
        quality = "VERY" if strength_score > 2.5 else "NOT VERY" if strength_score < 1.5 else ""
        directional = mad < mad_lim and strength_score > 1.5
        # neutral = mad < 7 and strength_score > 2.5
        self.isValid = directional

        # if self.isValid:
        #     print(f"{quality} {direction}, {strength_score:.3f}, {mad:.3f}")

        # if retplot and self.isValid:
        #         fig, axs = plt.subplots(1,3, figsize=(30, 16))

        #         sns.violinplot(data=df, x=close_bins, y='strike_price', density_norm='count', hue='type', split=True, ax=axs[0])
        #         axs[0].axhline(y=fair_value_nl_25, color='red', linestyle='--', label=f'Fair Value 25th: {fair_value_nl_25:.2f}', alpha=0.3)
        #         axs[0].axhline(y=fair_value_nl_50, color='green', linestyle='--', label=f'Fair Value 50th: {fair_value_nl_50:.2f}', alpha=0.3)
        #         axs[0].axhline(y=fair_value__nl_75, color='blue', linestyle='--', label=f'Fair Value 75th: {fair_value__nl_75:.2f}', alpha=0.3)
        #         axs[0].axhline(y=open_interest_balance, color='black', linestyle='--', label=f'OI Balanced: {open_interest_balance:.2f}', alpha=0.75)
        #         axs[0].axhline(y=close_ul, color='pink', linestyle='--', label=f'Underlying: {close_ul:.2f}', alpha=1)
        #         axs[0].axhline(y=df['underlying_price_2'].iloc[-1], color='purple', linestyle='--', label=f'Underlying Previous: {df["underlying_price_2"].iloc[-1]:.2f}', alpha=1)
        #         axs[0].set_title(f'{df["underlying_symbol"].iloc[-1]} Options Chain. Last Expiry {df["expiration_date"].max()}')
        #         axs[0].tick_params(rotation=45)
        #         axs[0].legend()

        #         reg_plot = sns.regplot(x='days_to_expiry', y='moneyness', data=df, ax=axs[1])
        #         params = reg_plot.get_lines()[0].get_data()
        #         x_first = df['days_to_expiry'].iloc[0]
        #         y_first = params[0][0] * x_first + params[1][0]
        #         slope, intercept = np.polyfit(params[0], params[1], 1)
        #         axs[1].set_xlabel('Days to Expiry')
        #         axs[1].set_ylabel('Moneyness')
        #         axs[1].set_title(f'Regression Plot of Moneyness vs Days to Expiry {slope:.3f} ({x_first},{y_first})')

        #         df['interest_difference'] = np.log(df['weighted_open_interest']/df['open_interest'])
        #         axs[2].plot(df['days_to_expiry'], df['interest_difference'], marker='o', linestyle='-')
        #         axs[2].set_xlabel('Days to Expiry')
        #         axs[2].set_ylabel('Difference')
        #         axs[2].set_title('Difference between Open Interest and Weighted Open Interest')
        #         axs[2].grid(True)

        #         plt.tight_layout()
        #         plt.show()

        self.close_ul = close_ul
        self.fair_value = fair_value_nl_50
        self.open_interest_balance = open_interest_balance
        self.strength = strength_score
        self.sentiment = quality+direction
        self.contracts = df 
        return True    

    def rankContract(self,price_filter=1.5,days_filter=[60,200],limit=50):
        df_execute = self.contracts.loc[
            (self.contracts['moneyness'].abs()/100 < self.contracts['ul_vol']*1.5) &
            (self.contracts['close_price'].between(0.1,price_filter)) & 
            (self.contracts['open_interest'] > max(self.contracts['open_interest'].quantile(0.25),1)) & 
            (self.contracts['days_to_expiry'].between(days_filter[0], days_filter[1]))
        ].copy() # filter for budget

        if df_execute.empty:
            return df_execute
        
        fair_values_array = np.array(self.fair_values)
        # closest_index = np.argmin(np.abs(fair_values_array - df_execute['underlying_price'].iloc[-1]))
        df_execute['strike_difference'] = abs(df_execute['strike_price'] - df_execute['underlying_price'])
        # df_execute['strike_difference'] = abs(df_execute['strike_price'] - self.fair_values[closest_index])
        sorted_df = df_execute.nsmallest(limit, 'strike_difference')
        row = sorted_df.sort_values(by='strike_difference',ascending=True)
        return row[['symbol','underlying_symbol','days_to_expiry','open_interest','type','strike_price','strike_difference','close_price','contract_value','moneyness']]    
    

options = AlpacaOptionContracts()
class Strategy_PricingModel:
    def __init__(self):
        self.riskfreerate = 0.05161
        self.TimeStep = 1/365
        self.printStats = False
        self.good_status = True

    def trinomial_tree(self,K,S0,u,sigma=None,N=1000,opttype='put',otm_lim=0.01):
        # Precompute values
        r = self.riskfreerate
        T = self.TimeStep
        dt = T / N

        if sigma is None:
            d = 1/u
            pu = ((np.exp(r * dt) - d) / (u - d)) / 2
            pd = ((u - np.exp(r * dt)) / (u - d)) / 2
        else:
            sigma = u
            u = np.exp(sigma * np.sqrt(3 * dt))
            d = 1 / u
            pu = ((np.exp(r * dt / 2) - np.exp(-sigma * np.sqrt(dt / 2))) / (np.exp(sigma * np.sqrt(dt / 2)) - np.exp(-sigma * np.sqrt(dt / 2)))) ** 2
            pd = ((np.exp(sigma * np.sqrt(dt / 2)) - np.exp(r * dt / 2)) / (np.exp(sigma * np.sqrt(dt / 2)) - np.exp(-sigma * np.sqrt(dt / 2)))) ** 2
        
        pm = 1 - pu - pd
        disc = np.exp(-r * dt)

        # Initialize stock prices at maturity
        S = S0 * d ** np.arange(N, -1, -1) * u ** np.arange(0, N + 1)
        C = np.maximum(0, K - S if opttype == 'put' else S - K)
        deltas = []
        delta_matrix = np.zeros((N, N-1))

        # Backward recursion through the tree
        for i in range(N - 1, -1, -1):
            # Calculate the maximum valid index for slicing
            max_idx = min(len(C), i + 3)  # Prevent index out of bounds
            pu_slice = C[2:max_idx]
            pm_slice = C[1:max_idx-1]
            pd_slice = C[:max_idx-2]

            # Aggregate contributions for the next period's prices
            C_new = np.zeros(i + 2)
            if len(pu_slice):
                C_new[-len(pu_slice):] = pu * pu_slice
            if len(pm_slice):
                C_new[-len(pm_slice)-1:-1] = pm * pm_slice
            if len(pd_slice):
                C_new[:len(pd_slice)] = pd * pd_slice  # Adjusted for correct range

            C_new *= disc

            # Adjust stock prices for intrinsic value
            S = S0 * d ** np.arange(i, -1, -1) * u ** np.arange(0, i + 1)
            intrinsic_value = np.maximum(0, K - S if opttype == 'put' else S - K)
            C_new = np.maximum(C_new[:len(C_new)-1], intrinsic_value[:len(C_new)])  # Ensure arrays align

            C[:len(C_new)] = C_new  # Update option values

            # Calculate delta only if S has at least two elements
            if i > 1 and len(S) > 1:
                middle_index = i // 2  # Approximate middle index
                delta = (C[middle_index + 1] - C[middle_index - 1]) / (S[middle_index + 1] - S[middle_index - 1])
                deltas.append(delta)

            if i > 0 and len(S) > 1:
                for j in range(len(S) - 1):
                    delta_matrix[i-1, j] = (C_new[j+1] - C_new[j]) / (S[j+1] - S[j])

            overall_delta = np.nanmean(delta_matrix) if delta_matrix.size else 0
            overall_delta += np.nanmean(deltas) / 2 if deltas else 0

            # overall_delta = np.mean(delta_matrix) + np.mean(deltas) / 2
        return max(C[0], otm_lim),overall_delta
    
    def getData(self,symbol,startoffset=1,maxTime=365,limit=100):
        start = dt.datetime.today()+dt.timedelta(days=startoffset)
        expiry = start+dt.timedelta(days=maxTime)
        try: #TODO: Handle cases where underlying price data is missing
            self.priceData = options.get_option_contracts(underlying_symbols=symbol,expiration_date_gte=start.strftime('%Y-%m-%d'),expiration_date_lte=expiry.strftime('%Y-%m-%d'), limit=limit)
            self.priceData['days_to_expiry'] += 1
            self.priceData['days_to_expiry'] = self.priceData['days_to_expiry'].clip(1,None) #TODO: Handle cases where expiry is now 
            self.symbol = symbol
            if self.printStats:
                print(f"{self.symbol} Contracts: {len(self.priceData)}")
            return self.priceData
        except Exception as e:
            self.good_status = False
            raise
            return pd.DataFrame()
        
    def fitModel(self):
        #TODO: Handle cases where underlying price data is missing and fitModel can't run
        strike_prices = self.priceData.strike_price.to_list()
        observed_prices = self.priceData.close_price.to_list()
        days_to_expiry = self.priceData.days_to_expiry.to_list()
        contype = self.priceData.type.to_list()
        self.ul_price = self.priceData.underlying_price.iloc[-1]
        vol = self.priceData['ul_vol'].iloc[-1]
        # print(vol)
        # initial_guess = 0.97
        initial_guess = vol

        def objective_function(u):
            u = u.round(3)
            if not (vol/2 < u < vol*1.5 and u != 1.0):
                return 1e6
            calculated_prices, deltas = zip(*[self.trinomial_tree(K, self.ul_price, u,sigma=vol, N=N, opttype=con, otm_lim=0.01) for K, N, con in zip(strike_prices, days_to_expiry, contype)])
            squared_diff = [(calculated_prices[i] - observed_prices[i])**2 for i in range(len(strike_prices))]
            r2 = np.mean(squared_diff)
            # print(r2,u)
            return r2

        try:
            result = minimize(objective_function, initial_guess, method='Nelder-Mead')
            minis = result.x
            self.minimum = result.fun 
            self.upfactor = minis[0]
            self.pricefloor = 0.01
        except Exception as e:
            print(f'pricing model error: {e}')

        if self.printStats:
            print("Optimized Up Factor:", self.upfactor)
            # print("Optimized Limit:", self.pricefloor)
            print("R2:", self.minimum)

        def calculate_price_and_delta(row):
            price, delta = self.trinomial_tree(row['strike_price'], self.ul_price,self.upfactor, N=row['days_to_expiry'], opttype=row['type'], otm_lim=self.pricefloor)
            return price, delta

        self.priceData[['modeled_price', 'delta']] = self.priceData.apply(calculate_price_and_delta, axis=1, result_type='expand').round(3)
        self.priceData['delta'] = self.priceData['delta'].clip(-1, 1)
        self.priceData['over/under'] = np.log(self.priceData['close_price']/self.priceData['modeled_price']).round(3).clip(-1,1)
        self.target_spread = np.nanmean(self.priceData['over/under'])

        # Filter put options
        put_options = self.priceData[self.priceData['type'] == 'put'].copy()
        if not put_options.empty:
            # Calculate the error for each put option
            put_options['error'] = np.log(put_options['close_price'] / put_options['modeled_price'])
            # Compute the mean error for put options
            mean_error_puts = np.nanmean(put_options['error'])/10
            # Adjust the modeled prices for put options by the mean error
            self.priceData.loc[self.priceData['type'] == 'put', 'adjusted_modeled_price'] = np.exp(np.log(self.priceData.loc[self.priceData['type'] == 'put', 'modeled_price']) + mean_error_puts)
            # For non-put options, the adjusted modeled price is the same as the original modeled price
            self.priceData.loc[self.priceData['type'] != 'put', 'adjusted_modeled_price'] = self.priceData['modeled_price']
            # Recalculate the "over/under" column using the adjusted modeled prices
            self.priceData['over/under'] = np.log(self.priceData['close_price'] / self.priceData['adjusted_modeled_price']).round(3).clip(-1, 1)

        self.target_spread = np.nanmean(self.priceData['over/under'])
        # print(self.target_spread,len(put_options),mean_error_puts)
        self.priceData.sort_values('delta',inplace=True,ascending=False)
        return self.priceData
    
    def iv_solver(self,market_price, S, K, opttype):
        """
        Solves for the implied volatility given a market price of an option.
        """
        def objective_function(vol):
            # Re-use trinomial tree pricing model
            model_price, _ = self.trinomial_tree(K, S, np.exp(vol * np.sqrt(self.TimeStep)), N=1000, opttype=opttype)
            return model_price - market_price

        # Initial volatility guess
        vol_guess = 0.2
        try:
            implied_vol = brentq(objective_function, 0.01, 2.0)
            return implied_vol
        except ValueError:
            return np.nan

    def compute_skew(self,S0):
        strikes = [S0 * (1 - x/100) for x in range(-10, 15, 5)]
        implied_vols = []
        for K in strikes:
            theoretical_price, _ = self.trinomial_tree(K, S0, u=self.upfactor, N=1000, opttype='call' if K > S0 else 'put')
            iv = self.iv_solver(theoretical_price, S0, K, 'call' if K > S0 else 'put')
            implied_vols.append(iv)
        # Example skew calculation: difference in IV between low and high strikes
        skew = implied_vols[-1] - implied_vols[0]
        return skew

    def forecast(self,strike,days_to_expiry,type):
        price, delta = self.trinomial_tree(strike, self.ul_price, self.upfactor, N=days_to_expiry, opttype=type, otm_lim=self.pricefloor)
        return price, delta

    def filterResults(self,minDays=0,maxDays=200,minDelta=0.3,maxDelta=0.7,minValue=-1.0,maxValue=-0.1,minPrice=0.1,maxPrice=10.0,byType=True):
        df_filtered = self.priceData.loc[(self.priceData['close_price'].between(minPrice,maxPrice)) & (self.priceData['days_to_expiry'].between(minDays,maxDays)) & (self.priceData['over/under'].between(minValue,maxValue)) & (self.priceData['delta'].abs().between(minDelta,maxDelta))].copy()
        if not byType:
            df_filtered.sort_values('delta',inplace=True,ascending=False)
            return df_filtered #[['symbol','type','days_to_expiry','underlying_price','strike_price','delta','close_price','modeled_price','over/under']]
        
        puts_filtered = df_filtered.loc[df_filtered['type'] == 'put'].copy()
        calls_filtered = df_filtered.loc[df_filtered['type'] == 'call'].copy()

        puts_filtered.sort_values('delta', inplace=True, ascending=True)
        calls_filtered.sort_values('delta', inplace=True, ascending=False)

        highest_put = puts_filtered.head(3) 
        highest_call = calls_filtered.head(3)

        highest_options = pd.concat([highest_put, highest_call])
        return highest_options #[['symbol','type','days_to_expiry','underlying_price','strike_price','delta','close_price','modeled_price','over/under']]

