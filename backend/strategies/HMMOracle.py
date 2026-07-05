import yfinance as yf
import numpy as np
import pandas as pd
import backtrader as bt
from hmmlearn import hmm
from scipy.stats import ks_2samp
from scipy.optimize import minimize
from sklearn.preprocessing import StandardScaler
import warnings
import matplotlib.pyplot as plt
warnings.filterwarnings('ignore')


def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def get_regime_signals_with_ks_filter(ticker, start, end):
    N_REGIMES = 3
    RANDOM_STATE = 42
    INITIAL_TRAINING_DAYS = 252
    RETRAIN_FREQUENCY = 40
    KS_WINDOW = 40
    KS_PVALUE_THRESHOLD = 0.20 #0.05 to 0.20
    HMM_CONFIDENCE_THRESHOLD = 0.55 #0.70 to 0.55
    MIN_HOLDING_DAYS = 20
    MIN_HISTORICAL_SAMPLES = 30
    
    print("="*70)
    print("REGIME DETECTION: HMM + K-S FILTER + WALK-FORWARD")
    print("="*70)
    
    print(f"\n[1/5] Downloading {ticker} data...")
    data = yf.download(ticker, start=start, end=end, progress=False)
    prices = data['Close'].squeeze()
    
    print("[2/5] Engineering features...")
    returns = np.log(prices / prices.shift(1)).dropna()
    vol = returns.rolling(20).std().dropna()
    rsi = calculate_rsi(prices, 14)
    trend = returns.rolling(50).mean()
    
    common_idx = returns.index.intersection(vol.index).intersection(rsi.index).intersection(trend.index)
    returns_aligned = returns.loc[common_idx]
    vol_aligned = vol.loc[common_idx]
    rsi_aligned = rsi.loc[common_idx]
    trend_aligned = trend.loc[common_idx]
    
    print(f"      Total trading days: {len(common_idx)}")
    print(f"      Training start after: {INITIAL_TRAINING_DAYS} days")
    
    print("[3/5] Running walk-forward HMM training...")
    
    regime_signals = []
    regime_probs_storage = []
    ks_stats = []
    ks_pvalues = []
    switch_signals = []
    
    active_regime = None
    regime_entry_idx = None
    last_train_idx = 0
    trained_model = None
    scaler = None
    order = None
    
    historical_regime_assignments = []
    
    for i in range(len(common_idx)):
        current_date = common_idx[i]
        
        ks_stat = np.nan
        ks_pvalue = np.nan
        switch_signal = False
        regime_probs = [np.nan, np.nan, np.nan]
        hmm_suggests = np.nan
        
        if i < INITIAL_TRAINING_DAYS:
            regime_signals.append(np.nan)
            regime_probs_storage.append(regime_probs)
            ks_stats.append(ks_stat)
            ks_pvalues.append(ks_pvalue)
            switch_signals.append(switch_signal)
            historical_regime_assignments.append(np.nan)
            continue
        
        should_retrain = (trained_model is None) or (last_train_idx == 0) or ((i - last_train_idx) >= RETRAIN_FREQUENCY)
        
        if should_retrain:
            train_df = pd.DataFrame({
                'returns': returns_aligned.iloc[:i],
                'vol': vol_aligned.iloc[:i],
                'rsi': rsi_aligned.iloc[:i],
                'trend': trend_aligned.iloc[:i]
            }).dropna()
            
            if len(train_df) < 100:
                regime_signals.append(np.nan)
                regime_probs_storage.append(regime_probs)
                ks_stats.append(ks_stat)
                ks_pvalues.append(ks_pvalue)
                switch_signals.append(switch_signal)
                historical_regime_assignments.append(np.nan)
                continue
            
            X_train = train_df.values
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X_train)
            
            trained_model = hmm.GaussianHMM(
                n_components=N_REGIMES,
                covariance_type="full",
                n_iter=200,
                random_state=RANDOM_STATE,
                min_covar=1e-5
            )
            
            try:
                trained_model.fit(X_scaled)
                state_means = trained_model.means_[:, 0]
                order = np.argsort(state_means)
                last_train_idx = i
            except Exception as e:
                print(f"      Warning: Training failed at index {i}: {e}")
                trained_model = None
        
        if trained_model is not None and scaler is not None:
            if np.isnan(trend_aligned.iloc[i]) or np.isnan(rsi_aligned.iloc[i]):
                regime_signals.append(np.nan)
                regime_probs_storage.append(regime_probs)
                ks_stats.append(ks_stat)
                ks_pvalues.append(ks_pvalue)
                switch_signals.append(switch_signal)
                historical_regime_assignments.append(np.nan)
                continue
            
            try:
                current_features = np.array([[
                    returns_aligned.iloc[i],
                    vol_aligned.iloc[i],
                    rsi_aligned.iloc[i],
                    trend_aligned.iloc[i]
                ]])
                current_scaled = scaler.transform(current_features)
                probs_raw = trained_model.predict_proba(current_scaled)[0]
                
                regime_probs = [
                    probs_raw[order[0]],
                    probs_raw[order[1]],
                    probs_raw[order[2]]
                ]
                
                hmm_suggests = np.argmax(regime_probs)
                hmm_confidence = regime_probs[hmm_suggests]
            except Exception as e:
                regime_signals.append(np.nan)
                regime_probs_storage.append([np.nan, np.nan, np.nan])
                ks_stats.append(ks_stat)
                ks_pvalues.append(ks_pvalue)
                switch_signals.append(switch_signal)
                historical_regime_assignments.append(np.nan)
                continue
        else:
            regime_signals.append(np.nan)
            regime_probs_storage.append(regime_probs)
            ks_stats.append(ks_stat)
            ks_pvalues.append(ks_pvalue)
            switch_signals.append(switch_signal)
            historical_regime_assignments.append(np.nan)
            continue
        
        if active_regime is None:
            active_regime = hmm_suggests
            regime_entry_idx = i
            regime_signals.append(active_regime)
            regime_probs_storage.append(regime_probs)
            ks_stats.append(np.nan)
            ks_pvalues.append(np.nan)
            switch_signals.append(False)
            historical_regime_assignments.append(active_regime)
            continue
        
        days_in_regime = i - regime_entry_idx
        
        historical_mask = np.array(historical_regime_assignments) == active_regime
        historical_mask = historical_mask[:i]
        
        if np.sum(historical_mask) >= MIN_HISTORICAL_SAMPLES:
            sample_A = returns_aligned.iloc[:i][historical_mask].values
            start_idx = max(0, i - KS_WINDOW)
            sample_B = returns_aligned.iloc[start_idx:i].values
            
            if len(sample_B) >= 10:
                try:
                    ks_stat, ks_pvalue = ks_2samp(sample_A, sample_B)
                except Exception as e:
                    pass
        
        condition_1 = days_in_regime >= MIN_HOLDING_DAYS
        condition_2 = ks_pvalue < KS_PVALUE_THRESHOLD if not np.isnan(ks_pvalue) else False
        condition_3 = hmm_confidence > HMM_CONFIDENCE_THRESHOLD
        condition_4 = hmm_suggests != active_regime
        
        if condition_1 and condition_2 and condition_3 and condition_4:
            old_regime = active_regime
            active_regime = hmm_suggests
            regime_entry_idx = i
            switch_signal = True
            
            regime_names = {0: "Bear", 1: "Kangaroo", 2: "Bull"}
            print(f"      {current_date.date()}: {regime_names[old_regime]} → {regime_names[active_regime]} "
                  f"(KS p={ks_pvalue:.3f}, Conf={hmm_confidence:.2f})")
        
        regime_signals.append(active_regime)
        regime_probs_storage.append(regime_probs)
        ks_stats.append(ks_stat)
        ks_pvalues.append(ks_pvalue)
        switch_signals.append(switch_signal)
        historical_regime_assignments.append(active_regime)
    
    print("[4/5] Building results dataframe...")
    
    results_df = pd.DataFrame({
        'regime': regime_signals,
        'bear_prob': [p[0] for p in regime_probs_storage],
        'kangaroo_prob': [p[1] for p in regime_probs_storage],
        'bull_prob': [p[2] for p in regime_probs_storage],
        'ks_statistic': ks_stats,
        'ks_pvalue': ks_pvalues,
        'switch_signal': switch_signals
    }, index=common_idx)
    
    print("[5/5] Summary statistics...")
    valid_signals = results_df['regime'].dropna()
    
    if len(valid_signals) > 0:
        regime_counts = valid_signals.value_counts().sort_index()
        regime_names = {0: "Bear", 1: "Kangaroo", 2: "Bull"}
        
        print("\n" + "="*70)
        print("REGIME DISTRIBUTION")
        print("="*70)
        for regime_id, count in regime_counts.items():
            pct = count / len(valid_signals) * 100
            print(f"{regime_names[regime_id]:10s}: {count:4d} days ({pct:5.1f}%)")
        
        n_switches = results_df['switch_signal'].sum()
        print(f"\nTotal regime switches: {n_switches}")
        print(f"Average days per regime: {len(valid_signals) / (n_switches + 1):.1f}")
    
    print("\n" + "="*70)
    
    return data.loc[common_idx], results_df






def download_multi_asset_data(tickers, start, end):
    """
    Download data for multiple assets to enable portfolio optimization
    
    Args:
        tickers: List of ticker symbols
        start: Start date
        end: End date
    
    Returns:
        Dictionary of DataFrames, one per ticker
    """
    print("\n" + "="*70)
    print(f"DOWNLOADING MULTI-ASSET DATA FOR PORTFOLIO OPTIMIZATION")
    print("="*70)
    
    data_dict = {}
    
    for ticker in tickers:
        print(f"  Downloading {ticker}...")
        try:
            data = yf.download(ticker, start=start, end=end, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            data.columns = [x.lower() for x in data.columns]
            data_dict[ticker] = data
        except Exception as e:
            print(f"  Warning: Failed to download {ticker}: {e}")
    
    print(f"\nSuccessfully downloaded {len(data_dict)} assets")
    print("="*70)
    
    return data_dict


# ============================================================================
# PART 3: REGIME-ADAPTIVE STRATEGY
# ============================================================================

class RegimeAdaptiveStrategy(bt.Strategy):
    """
    Adaptive strategy that switches between different approaches based on market regime:
    
    - BULL (regime=2): Aggressive momentum strategy with SPY
    - BEAR (regime=0): Capital preservation (100% cash)
    - KANGAROO (regime=1): Minimum Variance Portfolio across multiple assets
    """
    
    params = (
        # Bull regime parameters
        ('sma_period', 200),
        ('momentum_period', 10),
        
        # Kangaroo regime parameters
        ('rebalance_days', 20),
        ('lookback_period', 60),
        ('min_weight', 0.0),
        ('max_weight', 0.4),
        
        # General
        ('verbose', True),
    )

    def log(self, txt):
        """Logging function"""
        dt = self.datas[0].datetime.date(0)
        if self.params.verbose:
            print(f'{dt}: {txt}')

    def __init__(self):
        """Initialize the strategy"""
        # Main price data (SPY)
        self.main_data = self.datas[0]
        self.dataclose = self.main_data.close
        
        # Regime signal data
        self.regime_data = self.datas[-1]
        self.regime = self.regime_data.regime
        
        # Portfolio assets (all except last which is regime signal)
        self.portfolio_assets = self.datas[:-1]
        
        # Bull regime indicators (only for main SPY data)
        self.sma200 = bt.indicators.SimpleMovingAverage(
            self.main_data, 
            period=self.params.sma_period
        )
        self.roc = bt.indicators.RateOfChange(
            self.main_data, 
            period=self.params.momentum_period
        )
        
        # Kangaroo regime tracking
        self.day_counter = 0
        self.returns_history = {d: [] for d in self.portfolio_assets}
        self.current_weights = None
        self.last_regime = None
        
        self.log("Strategy initialized with regime-adaptive approach")

    def next(self):
        """Main strategy logic"""
        self.day_counter += 1
        
        # Get current regime
        curr_regime = self.regime[0]
        
        # Skip if regime not available
        if np.isnan(curr_regime):
            return
        
        # Detect regime change
        if self.last_regime is not None and curr_regime != self.last_regime:
            regime_names = {0: "BEAR", 1: "KANGAROO", 2: "BULL"}
            self.log(f"*** REGIME CHANGE: {regime_names[self.last_regime]} → {regime_names[curr_regime]} ***")
            
            # Close all positions on regime change
            for data in self.portfolio_assets:
                if self.getposition(data).size != 0:
                    self.close(data=data)
            
            # Reset kangaroo tracking
            self.returns_history = {d: [] for d in self.portfolio_assets}
        
        self.last_regime = curr_regime
        
        # Route to appropriate strategy
        if curr_regime == 2.0:
            self.execute_bull_strategy()
        elif curr_regime == 0.0:
            self.execute_bear_strategy()
        elif curr_regime == 1.0:
            self.execute_kangaroo_strategy()

    def execute_bull_strategy(self):
        """Aggressive momentum strategy for bull markets"""
        if len(self.main_data) < self.params.sma_period:
            return
        
        curr_price = self.dataclose[0]
        is_above_sma = curr_price > self.sma200[0]
        has_momentum = self.roc[0] > 0
        
        # Long entry
        if is_above_sma and has_momentum:
            if not self.getposition(self.main_data):
                size = int(self.broker.get_cash() / curr_price * 0.95)
                self.buy(data=self.main_data, size=size)
                self.log(f'BULL ENTRY @ ${curr_price:.2f} (size={size})')
        
        # Exit on SMA break
        elif not is_above_sma and self.getposition(self.main_data):
            self.close(data=self.main_data)
            self.log(f'BULL EXIT (SMA Break) @ ${curr_price:.2f}')

    def execute_bear_strategy(self):
        """Capital preservation - exit all positions"""
        for data in self.portfolio_assets:
            if self.getposition(data).size != 0:
                self.close(data=data)
                self.log(f'BEAR: Closed {data._name}')

    def execute_kangaroo_strategy(self):
        """Minimum variance portfolio optimization for sideways markets"""
        # Update returns history for all assets
        for data in self.portfolio_assets:
            if len(data) > 1:
                ret = (data.close[0] / data.close[-1]) - 1
                self.returns_history[data].append(ret)
                
                # Keep only lookback_period data points
                if len(self.returns_history[data]) > self.params.lookback_period:
                    self.returns_history[data].pop(0)
        
        # Rebalance periodically
        if self.day_counter % self.params.rebalance_days == 0:
            self.rebalance_minimum_variance()
    def rebalance_minimum_variance(self):
        portfolio_value = self.broker.getvalue()
    
    # Build returns matrix with validation
        returns_matrix = []
        valid_assets = []
    
        for data in self.portfolio_assets:
            if len(self.returns_history[data]) >= max(self.params.lookback_period, 20):  # Min 20 days
                returns_matrix.append(self.returns_history[data])
                valid_assets.append(data)
    
        if len(valid_assets) < 2:
            self.log("KANGAROO: Not enough assets for optimization")
            return
    
        returns_matrix = np.array(returns_matrix).T
    
    # Calculate covariance with regularization
        cov_matrix = np.cov(returns_matrix.T) + np.eye(len(valid_assets)) * 1e-8
    
    # Validate covariance
        if np.isnan(cov_matrix).any() or np.isinf(cov_matrix).any():
            self.log("KANGAROO: Invalid covariance matrix")
            return
    
    # Optimize
        weights = self.optimize_minimum_variance(cov_matrix, len(valid_assets))
    
        if weights is None:
            self.log("KANGAROO: Optimization failed")
            return
    
    # Rebalance with minimum position filter
        self.log(f"KANGAROO REBALANCE (Portfolio: ${portfolio_value:,.2f})")
        MIN_POSITION_SIZE = 100  # Don't buy positions < $100
    
        for i, data in enumerate(valid_assets):
            weight = weights[i]
            target_value = portfolio_value * weight
        
            if target_value < MIN_POSITION_SIZE:
                target_shares = 0
            else:
                target_shares = round(target_value / data.close[0])  # Use round instead of int
        
            current_position = self.getposition(data).size
        
            if target_shares != current_position:
                self.order_target_size(data, target_shares)
                self.log(f"  {data._name:6s}: {weight:6.2%} → {target_shares:4d} shares")
    
    # Store weights AFTER rebalancing
        self.current_weights = {valid_assets[i]: weights[i] for i in range(len(valid_assets))}
    
        portfolio_variance = weights.T @ cov_matrix @ weights
        annualized_vol = np.sqrt(portfolio_variance * 252)
        self.log(f"  Portfolio Volatility: {annualized_vol:.2%}")

    def optimize_minimum_variance(self, cov_matrix, n_assets):
        initial_weights = np.ones(n_assets) / n_assets
    
        constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]
        bounds = [(self.params.min_weight, self.params.max_weight) for _ in range(n_assets)]
    
        def portfolio_variance(weights):
            return weights.T @ cov_matrix @ weights
    
        result = minimize(
            portfolio_variance,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'ftol': 1e-6, 'maxiter': 1000}  # Relaxed tolerance
        )
    
        return result.x if result.success else None

    def stop(self):
        """Called when backtest ends"""
        final_value = self.broker.getvalue()
        self.log(f"\n{'='*70}")
        self.log(f"BACKTEST COMPLETE - Final Value: ${final_value:,.2f}")
        self.log(f"{'='*70}")


# ============================================================================
# PART 4: BACKTRADER DATA FEED FOR REGIME SIGNALS
# ============================================================================

class PandasRegimeData(bt.feeds.PandasData):
    """Custom data feed for regime signals"""
    lines = ('regime',)
    params = (('regime', 'regime'),)


# ============================================================================
# PART 5: MAIN EXECUTION
# ============================================================================

def run_regime_adaptive_backtest(
    main_ticker="SPY",
    portfolio_tickers=["SPY", "TLT", "GLD", "QQQ"],
    start_date="2008-01-01",
    end_date="2015-01-01",
    initial_cash=50000.0,
    commission=0.001
):
    """
    Main function to run the complete regime-adaptive backtest
    
    Args:
        main_ticker: Primary ticker for regime detection
        portfolio_tickers: Assets for Kangaroo regime portfolio optimization
        start_date: Backtest start date
        end_date: Backtest end date
        initial_cash: Starting capital
        commission: Commission rate (0.001 = 0.1%)
    """
    
    # Step 1: Get regime signals
    print("\n" + "="*70)
    print("STEP 1: REGIME DETECTION")
    print("="*70)
    
    price_data, regime_signals = get_regime_signals_with_ks_filter(
        ticker=main_ticker,
        start=start_date,
        end=end_date
    )
    
    # Clean column names
    if isinstance(price_data.columns, pd.MultiIndex):
        price_data.columns = price_data.columns.get_level_values(0)
    price_data.columns = [x.lower() for x in price_data.columns]
    regime_signals.columns = [x.lower() for x in regime_signals.columns]
    
    # Step 2: Download multi-asset data
    print("\n" + "="*70)
    print("STEP 2: MULTI-ASSET DATA")
    print("="*70)
    
    multi_asset_data = download_multi_asset_data(
        tickers=portfolio_tickers,
        start=start_date,
        end=end_date
    )
    
    # Step 3: Setup Backtrader
    print("\n" + "="*70)
    print("STEP 3: BACKTEST EXECUTION")
    print("="*70)
    
    cerebro = bt.Cerebro()
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)
    
    # Add data feeds for each asset
    for ticker in portfolio_tickers:
        if ticker in multi_asset_data:
            # Align with regime signals
            aligned_data = multi_asset_data[ticker].loc[regime_signals.index]
            data_feed = bt.feeds.PandasData(dataname=aligned_data)
            cerebro.adddata(data_feed, name=ticker)
    
    # Add regime signal feed (last data feed)
    regime_feed = PandasRegimeData(dataname=regime_signals)
    cerebro.adddata(regime_feed, name='REGIME')
    
    # Add strategy
    cerebro.addstrategy(RegimeAdaptiveStrategy, verbose=True)
    
    # Add analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    
    # Run backtest
    print(f'\nStarting Portfolio Value: ${cerebro.broker.getvalue():,.2f}')
    results = cerebro.run()
    final_value = cerebro.broker.getvalue()
    print(f'Final Portfolio Value:    ${final_value:,.2f}')
    
    # Step 4: Performance Analysis
    print("\n" + "="*70)
    print("PERFORMANCE METRICS")
    print("="*70)
    
    strat = results[0]
    
    # Sharpe Ratio
    sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', None)
    if sharpe:
        print(f"Sharpe Ratio:      {sharpe:.3f}")
    else:
        print(f"Sharpe Ratio:      N/A")
    
    # Drawdown
    dd = strat.analyzers.drawdown.get_analysis()
    print(f"Max Drawdown:      {dd['max']['drawdown']:.2f}%")
    
    # Returns
    rets = strat.analyzers.returns.get_analysis()
    total_return = rets['rtot'] * 100
    annual_return = rets.get('rnorm100', total_return)
    print(f"Total Return:      {total_return:.2f}%")
    print(f"Annual Return:     {annual_return:.2f}%")
    
    # Trade Analysis
    trades = strat.analyzers.trades.get_analysis()
    if 'total' in trades and trades['total']['total'] > 0:
        print(f"\nTotal Trades:      {trades['total']['total']}")
        print(f"Winning Trades:    {trades['won']['total']}")
        print(f"Losing Trades:     {trades['lost']['total']}")
        if trades['won']['total'] > 0:
            print(f"Avg Win:           {trades['won']['pnl']['average']:.2f}")
        if trades['lost']['total'] > 0:
            print(f"Avg Loss:          {trades['lost']['pnl']['average']:.2f}")
    
    print("="*70)
    
    # Return results for further analysis
    return {
        'cerebro': cerebro,
        'results': results,
        'final_value': final_value,
        'regime_signals': regime_signals,
        'price_data': price_data
    }


# ============================================================================
# PART 6: VISUALIZATION
# ============================================================================

def plot_regime_analysis(price_data, regime_signals):
    """
    Create visualization of regime detection results
    """
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    
    # Plot 1: Price with regime background
    ax1 = axes[0]
    ax1.plot(price_data.index, price_data['close'], color='black', linewidth=1)
    
    # Color background by regime
    regime_colors = {0: 'red', 1: 'yellow', 2: 'green'}
    regime_names = {0: 'Bear', 1: 'Kangaroo', 2: 'Bull'}
    
    for regime in [0, 1, 2]:
        mask = regime_signals['regime'] == regime
        if mask.any():
            ax1.fill_between(
                price_data.index, 
                price_data['close'].min(), 
                price_data['close'].max(),
                where=mask,
                alpha=0.2,
                color=regime_colors[regime],
                label=regime_names[regime]
            )
    
    ax1.set_ylabel('Price ($)')
    ax1.set_title('Price with Market Regimes')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Regime probabilities
    ax2 = axes[1]
    ax2.plot(regime_signals.index, regime_signals['bear_prob'], 
             label='Bear', color='red', alpha=0.7)
    ax2.plot(regime_signals.index, regime_signals['kangaroo_prob'], 
             label='Kangaroo', color='orange', alpha=0.7)
    ax2.plot(regime_signals.index, regime_signals['bull_prob'], 
             label='Bull', color='green', alpha=0.7)
    ax2.set_ylabel('Probability')
    ax2.set_title('Regime Probabilities')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 1])
    
    # Plot 3: K-S p-value
    ax3 = axes[2]
    ax3.plot(regime_signals.index, regime_signals['ks_pvalue'], 
             color='blue', alpha=0.6, linewidth=0.8)
    ax3.axhline(y=0.05, color='red', linestyle='--', 
                label='Significance Threshold', linewidth=1)
    ax3.set_ylabel('K-S p-value')
    ax3.set_xlabel('Date')
    ax3.set_title('Kolmogorov-Smirnov Test p-value')
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    ax3.set_yscale('log')
    
    plt.tight_layout()
    return fig


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    
    print("\n" + "="*70)
    print(" REGIME-ADAPTIVE TRADING SYSTEM ")
    print(" Multi-Strategy Approach with HMM Regime Detection ")
    print("="*70)
    
    # Configuration
    MAIN_TICKER = "SPY"
    PORTFOLIO_TICKERS = ["SPY", "TLT", "GLD", "QQQ", "IWM"]  # Diversified portfolio
    START_DATE = "2015-01-01"
    END_DATE = "2025-01-01"
    INITIAL_CASH = 100000.0
    
    # Run backtest
    results = run_regime_adaptive_backtest(
        main_ticker=MAIN_TICKER,
        portfolio_tickers=PORTFOLIO_TICKERS,
        start_date=START_DATE,
        end_date=END_DATE,
        initial_cash=INITIAL_CASH,
        commission=0.001
    )
    
    # Create visualization
    print("\n" + "="*70)
    
    # Optional: Show plot (comment out if running headless)
    plt.show()
    
    print("\n" + "="*70)
    print(" EXECUTION COMPLETE ")
    print("="*70)