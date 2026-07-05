import backtrader as bt
import pandas as pd
import yfinance as yf
import os
import base64

from .MertonOptimizer import DynamicRegimeMerton, PandasRegimeData
from .HMMOracle import get_regime_signals_with_ks_filter
from .build_dashboard import build_presentation_dashboard
from .build_cinematic_replay import build_cinematic_replay, stream_cinematic_replay

def run_merton_backtest(start_date, end_date):
    pass

def run_merton_backtest_and_stream(start_date, end_date, socketio, client_id,results_store):
    """
    Runs the backtest and streams the cinematic replay video frames via WebSocket.
    """
    ALL_TICKERS = ["SPY", "QQQ", "IWM", "XLK", "GLD", "TLT", "DBC", "XLU", "BIL"]
    
    print(f"Streaming Backtest: Generating HMM Regimes from {start_date} to {end_date}...")
    price_data, regime_df = get_regime_signals_with_ks_filter("SPY", start_date, end_date)
    regime_df = regime_df[['regime']].dropna()

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0.00005)
    cerebro.broker.set_slippage_perc(perc=0.0002)

    print("Streaming Backtest: Downloading Asset Data...")
    for ticker in ALL_TICKERS:
        df = yf.download(ticker, start=start_date, end=end_date, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data, name=ticker)

    regime_data = PandasRegimeData(dataname=regime_df)
    cerebro.adddata(regime_data, name='REGIME')

    cerebro.addstrategy(DynamicRegimeMerton)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days, riskfreerate=0.0, annualize=True)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn, _name='annual')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='dd')

    print("\nStreaming Backtest: Running Cerebro...")
    results = cerebro.run()
    strat = results[0]
    
    print("\nStreaming Backtest: Starting cinematic replay stream...")
    final_frame_b64 = stream_cinematic_replay(
        csv_file="presentation_data.csv", 
        socketio=socketio,
        client_id=client_id,
        return_final_frame=True
    )

    print("\nStreaming Backtest: Building final results payload...")
    dashboard_file = "Interactive_Presentation.html"
    build_presentation_dashboard(csv_file="presentation_data.csv")
    
    dashboard_html_content = None
    if os.path.exists(dashboard_file):
        with open(dashboard_file, 'r', encoding='utf-8') as f:
            dashboard_html_content = f.read()
        os.remove(dashboard_file)

    final_value = cerebro.broker.getvalue()
    sharpe = strat.analyzers.sharpe.get_analysis().get('sharperatio', 0.0)
    dd = strat.analyzers.dd.get_analysis()['max']['drawdown']
    log_total_return = strat.analyzers.returns.get_analysis()['rtot'] * 100
    cagr = strat.analyzers.returns.get_analysis()['rnorm100']
    annual_returns = strat.analyzers.annual.get_analysis()
    trades = strat.analyzers.trades.get_analysis()

    trade_analysis = {}
    if 'total' in trades and trades['total']['total'] > 0:
        trade_analysis = {
            "total_trades": trades['total']['total'],
            "winning_trades": trades['won']['total'],
            "losing_trades": trades['lost']['total'],
            "total_pnl": trades['pnl']['net']['total']
        }

    annual_returns_df = pd.DataFrame(annual_returns.items(), columns=['Year', 'Return']).set_index('Year')
    annual_returns_json = annual_returns_df.to_json(orient='split')

    final_results = {
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": 100000,
        "final_portfolio_value": final_value,
        "annualized_sharpe_ratio": sharpe,
        "max_drawdown_percent": dd,
        "total_return_log_percent": log_total_return,
        "cagr_percent": cagr,
        "annual_returns_df": annual_returns_json,
        "trade_analysis": trade_analysis,
        "dashboard_html": dashboard_html_content,
        "final_frame_b64": final_frame_b64
    }
    
    socketio.emit('backtest_results', final_results, room=client_id)
    print(f"Emitted final backtest results to client {client_id}")

    results_store['latest'] = final_results
    results_store[client_id] = final_results

    print(f"Stored results for client {client_id}. results_store keys: {list(results_store.keys())}")