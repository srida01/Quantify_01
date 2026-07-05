# import os
# # Force all underlying C-libraries to use a single thread
# os.environ["OMP_NUM_THREADS"] = "1"
# os.environ["OPENBLAS_NUM_THREADS"] = "1"
# os.environ["MKL_NUM_THREADS"] = "1"
# os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
# os.environ["NUMEXPR_NUM_THREADS"] = "1"

import backtrader as bt
import numpy as np
import pandas as pd
import yfinance as yf

"""
    Change log:
    Fix 1: Neutralize the Bear Universe
    Shorting the market based on a lagging HMM is dangerous. 
    Let's make the Bear regime a pure capital preservation play.Change: 0: ["BIL", "SH", "UUP"] 
    $\rightarrow$ 0: ["BIL"] (100% Cash Equivalents).
    Fix 2: Relax the Bull Gatekeeper
    Let's lower the ADX threshold so we don't miss out on slow-grinding bull markets.
    Change: In get_eligible_assets, drop the Bull entry requirement from > 25 to > 20, 
    and the hold requirement to > 15.
    Fix 3: Unleash the Bull Optimizer
    Let's drop the base risk aversion so the Merton model takes larger position sizes when the weather is good.
    Change: In the params dictionary, change base_gamma=5.0 to base_gamma=2.5.

    v2 Swapping out the calc_merton_weights fun as compared to the previous rendition

    v3 Going to add a dummy indicator to keep backtrader in the prenext stage during our 2014 warmup year,
    it'll keep in prenext for that period as we want. (Keeps the math clean)
    Also swapped out the double print blocks to be one now that we aren't doing the recalculation ourselves

    v4 Making the strat face bid-ask slippage and commissions, tweaking params to make it work 
    under these circumstances.

    Got rid of multithreading to remove the floating point errors, *attempted to, still multithreading
"""


# Import your incredibly robust HMM logic directly from your implement4 file!
# (Make sure implement4.py is in the same folder)
from .HMMOracle import get_regime_signals_with_ks_filter

# ============================================================================
# PART 1: DATA FEEDS
# ============================================================================

class PandasRegimeData(bt.feeds.PandasData):
    """Custom Backtrader data feed to inject regime signals."""
    lines = ('regime',)
    params = (('regime', 'regime'),)

##########
class LogReturns(bt.Indicator):
    """Custom indicator to calculate daily log returns."""
    lines = ('logret',)
    
    def next(self):
        # Prevent math errors on the very first bar
        if len(self.data) > 1:
            self.lines.logret[0] = np.log(self.data.close[0] / self.data.close[-1])
        else:
            self.lines.logret[0] = 0.0
#########

# ============================================================================
# PART 2: THE MACRO-TO-MICRO STRATEGY
# ============================================================================

class DynamicRegimeMerton(bt.Strategy):
    params = dict(
        lookback=63,
        base_gamma=2.5,
        risk_free_rate=0.02,
        max_weight=0.4,
        max_leverage=1.0,
        rebalance_threshold=0.05
    )

    def __init__(self):
        # 1. Define Regime-Specific Universes
        self.universes = {
            2: ["SPY", "QQQ", "IWM", "XLK"],  # Bull: Risk-On
            1: ["GLD", "TLT", "DBC", "XLU"],  # Kangaroo: Defensive
            0: ["BIL"]          # Bear: Risk-Off Before: ["BIL", "SH", "UUP"] 
        }
        
        self.regime_data = self.getdatabyname('REGIME')
        self.asset_feeds = {d._name: d for d in self.datas if d._name != 'REGIME'}
        
        # 2. Initialize Indicators for Gatekeepers
        self.inds = {}
        for ticker, data in self.asset_feeds.items():
            log_returns = LogReturns(data, period=1)
            
            adx = bt.indicators.ADX(data, period=14)
            rsi = bt.indicators.RSI_Safe(data, period=14)
            vol = bt.indicators.StandardDeviation(log_returns, period=20) 
            
            # --- THE INDICATOR MUTE ---
            # Hide the subplots for all background asset indicators
            # if ticker != "SPY":
            log_returns.plotinfo.plot = False
            adx.plotinfo.plot = False
            rsi.plotinfo.plot = False
            vol.plotinfo.plot = False

            self.inds[ticker] = {
                'adx': adx,
                'rsi': rsi,
                'vol': vol 
            }

        # Force Backtrader to sleep (and pause analyzers) for the 2014 warmup year
        self.warmup_clock = bt.indicators.SMA(self.asset_feeds["SPY"], period=252)

        self.daily_snapshots=[] #For generating a log file to plot from

    def get_eligible_assets(self, regime):
        """The Master Gatekeeper (Hysteresis + Volatility Shocks)"""
        eligible = []
        target_universe = self.universes.get(regime, [])
        
        for ticker in target_universe:
            data = self.asset_feeds[ticker]
            
            vol_history = self.inds[ticker]['vol'].get(size=252)
            if len(vol_history) < 252:
                continue 
                
            current_adx = self.inds[ticker]['adx'][0]
            current_rsi = self.inds[ticker]['rsi'][0]
            current_vol = vol_history[-1]
            is_invested = self.getposition(data).size != 0
            
            # --- Universal Volatility Check ---
            if is_invested and current_vol > np.percentile(vol_history, 90):
                continue
            elif not is_invested and current_vol > np.percentile(vol_history, 80):
                continue

            # --- Regime Specific Checks ---
            if regime in [0, 2]:  # Bull / Bear (Trend)
                if is_invested and current_adx > 15: 
                    eligible.append(ticker)
                elif not is_invested and current_adx > 25: 
                    eligible.append(ticker)
                        
            elif regime == 1:     # Kangaroo (Mean Reversion)
                if is_invested and 35 < current_rsi < 65: 
                    eligible.append(ticker)
                elif not is_invested and 45 < current_rsi < 55: 
                    eligible.append(ticker)
                        
        return eligible

    def calculate_merton_weights(self, eligible_assets, regime):
        """The Micro Allocator (Long-Only Merton Optimization with Shrinkage)"""
        
        # FIX 1: If only 1 asset survives, give it 100% of the leverage, not 40%.
        if len(eligible_assets) < 2:
            if len(eligible_assets) == 1:
                return {eligible_assets[0]: self.p.max_leverage}
            return {} 
            
        R = np.column_stack([self.returns_buffer[ticker] for ticker in eligible_assets])
        
        alpha = 0.05 
        mu_ewma = np.average(R, axis=0, weights=[(1-alpha)**(len(R)-1-i) for i in range(len(R))])
        boost = 1.2 if regime == 2 else 1.0 
        mu = mu_ewma * 252 * boost
        
        S_sample = np.cov(R, rowvar=False) * 252
        target_matrix = np.eye(len(eligible_assets)) * np.mean(np.diag(S_sample))
        Sigma = (0.1 * target_matrix) + (0.9 * S_sample) + (np.eye(len(eligible_assets)) * 1e-6)
        
        gamma_multiplier = {2: 0.5, 1: 1.5, 0: 3.0}.get(regime, 1.0)
        gamma = self.p.base_gamma * gamma_multiplier
            
        try:
            raw_weights = np.linalg.solve(Sigma, mu - self.p.risk_free_rate) / gamma
        except np.linalg.LinAlgError:
            return {}

        # FIX 2: Long-Only Constraint. No shorting allowed (0.0 floor)
        weights = np.clip(raw_weights, 0.0, self.p.max_weight)
        
        # FIX 3: Scale the positive weights to utilize 100% of our capital
        lev = np.sum(weights)
        if lev > 0:
            weights *= (self.p.max_leverage / lev)
            
        return {ticker: weights[i] for i, ticker in enumerate(eligible_assets)}

    def next(self):
        """Main Execution Loop"""
        curr_regime = self.regime_data.regime[0]
        if np.isnan(curr_regime):
            return

        # Update Returns Buffer
        if not hasattr(self, 'returns_buffer'):
            self.returns_buffer = {ticker: [] for ticker in self.asset_feeds.keys()}
            
        for ticker, data in self.asset_feeds.items():
            if len(data) > 1:
                self.returns_buffer[ticker].append(np.log(data.close[0] / data.close[-1]))
                if len(self.returns_buffer[ticker]) > self.p.lookback:
                    self.returns_buffer[ticker].pop(0)

        if any(len(buf) < self.p.lookback for buf in self.returns_buffer.values()):
            return

        # 1. Gatekeeper
        eligible_assets = self.get_eligible_assets(curr_regime)

        # 2. Merton Allocation
        target_weights = self.calculate_merton_weights(eligible_assets, curr_regime)

        # 3. Execution
        port_value = self.broker.getvalue()
        if port_value <= 0: return

        for ticker, data in self.asset_feeds.items():
            pos_size = self.getposition(data).size
            current_weight = (pos_size * data.close[0]) / port_value if pos_size != 0 else 0.0
            target_weight = target_weights.get(ticker, 0.0)
            
            if target_weight == 0.0 and pos_size != 0:
                self.order_target_percent(data, 0.0)
            elif abs(target_weight - current_weight) > self.p.rebalance_threshold:
                self.order_target_percent(data, target=target_weight)

        # ADD THIS AT THE VERY END OF NEXT(): Capture the daily state
        dt = self.datas[0].datetime.date(0)
        port_value = self.broker.getvalue()
        regime = self.regime_data.regime[0]
        
        # Capture current holdings (weights) FOR PLOTTING and Logging
        holdings = {}
        for ticker, data in self.asset_feeds.items():
            pos_size = self.getposition(data).size
            if pos_size > 0:
                # Calculate what percentage of the portfolio this asset takes up
                weight = (pos_size * data.close[0]) / port_value
                holdings[ticker] = round(weight, 3)

        self.daily_snapshots.append({
            'Date': dt,
            'Portfolio_Value': port_value,
            'Regime': regime,
            'Holdings': str(holdings) # Saved as a string so it easily writes to CSV
        })
    
    def stop(self):
        """
        Called automatically by Backtrader when the data feeds run out.
        Liquidates all open positions so TradeAnalyzer captures the final Unrealized PnL.
        """
        for ticker, data in self.asset_feeds.items():
            if self.getposition(data).size != 0:
                self.close(data=data)
                # Optional: Print statement to verify the liquidation
                # print(f"END OF BACKTEST: Liquidating open position in {ticker}")

        # ADD THIS: Export the logger to a CSV when the backtest finishes To plot and log
        df = pd.DataFrame(self.daily_snapshots)
        df.set_index('Date', inplace=True)
        df.to_csv("presentation_data.csv")
        print("\nExported daily snapshots to presentation_data.csv")

# ============================================================================
# PART 3: MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    ALL_TICKERS = ["SPY", "QQQ", "IWM", "XLK", "GLD", "TLT", "DBC", "XLU", "BIL"]
    START, END = "2014-01-01", "2025-01-01"

    print("Generating HMM Regimes via implement4.py...")
    price_data, regime_df = get_regime_signals_with_ks_filter("SPY", START, END)
    regime_df = regime_df[['regime']].dropna()

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000)

    # --- REAL-WORLD TRADING COSTS ---
    
    # 1. Broker Commissions (e.g., 0.1% per trade)
    cerebro.broker.setcommission(commission=0.00005) #changed to reflect modern etf pricing

    # 2. Bid-Ask Slippage (e.g., 0.05% penalty on the execution price)
    cerebro.broker.set_slippage_perc(perc=0.0002)

    print("Downloading Asset Data...")
    for ticker in ALL_TICKERS:
        df = yf.download(ticker, start=START, end=END, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        data = bt.feeds.PandasData(dataname=df)
        
        # --- THE SURGICAL MUTE ---
        # Hide the visual clutter of the background assets, only plot the SPY benchmark
        # if ticker != "SPY":
        #     data.plotinfo.plot = False
            
        cerebro.adddata(data, name=ticker)

    regime_data = PandasRegimeData(dataname=regime_df)
    regime_data.plotinfo.plot=False
    cerebro.adddata(regime_data, name='REGIME')

    # Add Strategy 
    cerebro.addstrategy(DynamicRegimeMerton)

    # Add Analyzers (With annualize=True for Geometric Sharpe)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days, riskfreerate=0.0, annualize=True)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')

    print("\nRunning Backtest...")
    results = cerebro.run()
    strat = results[0]

    # --- PRINT NATIVE RESULTS ---
    print(f"\n{'-'*40}")
    print(f"Starting Portfolio Value (2015): $100,000.00")
    print(f"Ending Portfolio Value (2025):   ${cerebro.broker.getvalue():,.2f}")
    print(f"{'-'*40}")

    # Core Metrics
    sharpe = strat.analyzers.sharpe.get_analysis()
    print(f"Annualized Sharpe Ratio: {sharpe.get('sharperatio', 0.0):.3f}")

    dd = strat.analyzers.dd.get_analysis()
    print(f"Max Drawdown: {dd['max']['drawdown']:.2f}%")

    returns = strat.analyzers.returns.get_analysis()
    print(f"Total Return (Logarithmic): {returns['rtot'] * 100:.2f}%")
    true_total_return = (cerebro.broker.getvalue() / 100000.0) - 1.0
    print(f"Total Return (Usual): {true_total_return * 100:.2f}%")
    print(f"CAGR (Annualized): {returns['rnorm100']:.2f}%")

    # Yearly Breakdown
    annual = strat.analyzers.annual.get_analysis()
    print(f"\n{'-'*40}\nYEARLY RETURNS\n{'-'*40}")
    for year, ret in annual.items():
        print(f"  {year}: {ret:.2%}")

    # Trade Breakdown
    trades = strat.analyzers.trades.get_analysis()
    print(f"\n{'-'*40}\nTRADE ANALYSIS\n{'-'*40}")
    if 'total' in trades and trades['total']['total'] > 0:
        print(f"  Total Trades:   {trades['total']['total']}")
        print(f"  Winning Trades: {trades['won']['total']}")
        print(f"  Losing Trades:  {trades['lost']['total']}")
        print(f"  Total PnL:      ${trades['pnl']['net']['total']:,.2f}")
    else:
        print("  No closed trades recorded.")
    #Note P and L has a discrepancy with the final value because the trades being called by stop aren't being 
    # executed as there is no day to execute them on as per the end parameter.  


    # ==========================================================
    # CUSTOM UNIVERSE PLOTTING HACK (V5 - Headless Export)
    # ==========================================================
    import matplotlib.pyplot as plt
    
    # Shrink the legend font globally so all 9 assets fit inside the box
    plt.rcParams['legend.fontsize'] = 8
    
    bull_universe = ["SPY", "QQQ", "IWM", "XLK"]
    kangaroo_universe = ["GLD", "TLT", "DBC", "XLU"]
    bear_universe = ["BIL"]
    
    universes = {
        "Bull Assets": bull_universe,
        "Kangaroo Assets": kangaroo_universe,
        "Bear Assets": bear_universe
    }

    # # ----------------------------------------------------------
    # # FIGURE 1: THE MASTER PORTFOLIO DASHBOARD
    # # ----------------------------------------------------------
    # print("\nSaving Master Portfolio Dashboard to PNG...")
    
    # # Price Charts: Only show SPY
    # for data in cerebro.datas:
    #     data.plotinfo.plot = (data._name == 'SPY')

    # # Observers: Keep Broker and Trades ON, Mute hidden assets' BuySell arrows
    # for obs in strat.observers:
    #     obs_name = obs.__class__.__name__.lower()
    #     if 'buysell' in obs_name:
    #         if hasattr(obs, 'data') and obs.data is not None:
    #             obs.plotinfo.plot = (obs.data._name == 'SPY')
    #     else:
    #         obs.plotinfo.plot = True
            
    # # Capture the figure object and save it
    # figs = cerebro.plot(volume=False, numfigs=1)
    # master_fig = figs[0][0]
    # master_fig.savefig("01_Master_Dashboard.png", bbox_inches='tight', dpi=300)
    # plt.close(master_fig) # Closes the window so the script keeps running

    # # ----------------------------------------------------------
    # # FIGURES 2, 3, 4: THE ASSET UNIVERSES
    # # ----------------------------------------------------------
    
    # for universe_name, tickers in universes.items():
    #     print(f"Saving plot window for {universe_name}...")
        
    #     # 1. Price Charts: Turn ON specific universe
    #     for data in cerebro.datas:
    #         data.plotinfo.plot = (data._name in tickers)
                
    #     # 2. Observers: Bulletproof Mute for Broker and Trades
    #     for obs in strat.observers:
    #         obs_name = obs.__class__.__name__.lower()
            
    #         if 'broker' in obs_name or 'trade' in obs_name:
    #             obs.plotinfo.plot = False 
    #         elif 'buysell' in obs_name:
    #             if hasattr(obs, 'data') and obs.data is not None:
    #                 obs.plotinfo.plot = (obs.data._name in tickers)

    #     # Capture, save, and close
    #     figs = cerebro.plot(volume=False, numfigs=1)
    #     universe_fig = figs[0][0]
        
    #     # Format the filename (e.g., "02_bull_assets.png")
    #     safe_name = universe_name.replace(" ", "_").lower()
    #     filename = f"02_{safe_name}.png" 
        
    #     universe_fig.savefig(filename, bbox_inches='tight', dpi=300)
    #     plt.close(universe_fig)
        
    # print("\nAll charts successfully exported to your current directory!")