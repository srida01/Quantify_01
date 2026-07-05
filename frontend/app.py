import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
from datetime import datetime
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'components'))

class TradingAnalyzer:
    def __init__(self):
        self.api_base_url = "http://127.0.0.1:5000/api"
        self.strategies_info = None
        self.load_strategies()
    
    def load_strategies(self):
        """Load available strategies from backend"""
        try:
            response = requests.get(f"{self.api_base_url}/strategies", timeout=10)
            if response.status_code == 200:
                data = response.json()
                self.strategies_info = data.get("strategy_info", {})
                return True
            else:
                st.error("Failed to connect to backend API")
                return False
        except requests.exceptions.ConnectionError:
            st.error("Backend server is not running. Please start the API server first.")
            st.code("cd backend && python api_server.py")
            return False
        except Exception as e:
            st.error(f"Error connecting to backend: {e}")
            return False
    
    def analyze_symbol(self, symbol, strategy_type, params, period="1mo"):
        """Analyze symbol using backend API"""
        try:
            payload = {
                "symbol": symbol,
                "strategy": strategy_type,
                "params": params,
                "period": period
            }
            
            response = requests.post(f"{self.api_base_url}/analyze", 
                                   json=payload, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API request failed: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Analysis failed: {str(e)}"}
    
    def get_live_signal(self, symbol, strategy_type, params):
        """Get live signal from backend"""
        try:
            payload = {
                "symbol": symbol,
                "strategy": strategy_type,
                "params": params
            }
            
            response = requests.post(f"{self.api_base_url}/live-signal", 
                                   json=payload, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Live signal request failed: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Live signal failed: {str(e)}"}
    
    def create_price_chart(self, analysis_result):
        """Create price chart with strategy indicators"""
        if "error" in analysis_result:
            st.error(f"Analysis error: {analysis_result['error']}")
            return None
        
        data = analysis_result.get("data", {})
        indicators = analysis_result.get("indicators", {})
        signals = analysis_result.get("signals", [])
        strategy_type = analysis_result.get("strategy", "").upper()
        
        if not data.get("timestamps"):
            st.error("No data available for chart")
            return None
        
        timestamps = [datetime.fromisoformat(ts.replace('Z', '+00:00')) for ts in data["timestamps"]]
        
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=[f'{analysis_result["symbol"]} Price Chart with {strategy_type} Strategy', 
                          f'{strategy_type} Indicator'],
            vertical_spacing=0.1,
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )
        
        fig.add_trace(
            go.Candlestick(
                x=timestamps,
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data["close"],
                name='Price'
            ),
            row=1, col=1
        )
        
        if strategy_type == 'SMA':
            sma_fast = indicators.get('sma_fast', [])
            sma_slow = indicators.get('sma_slow', [])
            
            if sma_fast:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=sma_fast,
                        mode='lines',
                        name=f'SMA Fast ({indicators.get("fast_period", "N/A")})',
                        line=dict(color='orange', width=2)
                    ),
                    row=1, col=1
                )
            
            if sma_slow:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=sma_slow,
                        mode='lines',
                        name=f'SMA Slow ({indicators.get("slow_period", "N/A")})',
                        line=dict(color='purple', width=2)
                    ),
                    row=1, col=1
                )
            
            if sma_fast and sma_slow:
                sma_diff = [f - s if f is not None and s is not None else None 
                           for f, s in zip(sma_fast, sma_slow)]
                
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=sma_diff,
                        mode='lines',
                        name='SMA Difference',
                        line=dict(color='blue'),
                        fill='tonexty'
                    ),
                    row=2, col=1
                )
                
        elif strategy_type == 'RSI':
            rsi_values = indicators.get('rsi_values', [])
            if rsi_values:
                fig.add_trace(
                    go.Scatter(
                        x=timestamps,
                        y=rsi_values,
                        mode='lines',
                        name='RSI',
                        line=dict(color='purple', width=2)
                    ),
                    row=2, col=1
                )
                
                upper_threshold = indicators.get('upper_threshold', 70)
                lower_threshold = indicators.get('lower_threshold', 30)
                
                fig.add_hline(y=upper_threshold, line_dash="dash", line_color="red", row=2, col=1)
                fig.add_hline(y=lower_threshold, line_dash="dash", line_color="green", row=2, col=1)
                fig.add_hline(y=50, line_dash="dot", line_color="gray", row=2, col=1)
        
        buy_signals = []
        sell_signals = []
        buy_prices = []
        sell_prices = []
        
        for i, signal_data in enumerate(signals):
            if signal_data['signal'] == 'BUY':
                buy_signals.append(timestamps[i])
                buy_prices.append(signal_data['price'])
            elif signal_data['signal'] == 'SELL':
                sell_signals.append(timestamps[i])
                sell_prices.append(signal_data['price'])
        
        if buy_signals:
            fig.add_trace(
                go.Scatter(
                    x=buy_signals,
                    y=buy_prices,
                    mode='markers',
                    name='Buy Signals',
                    marker=dict(color='green', size=10, symbol='triangle-up')
                ),
                row=1, col=1
            )
        
        if sell_signals:
            fig.add_trace(
                go.Scatter(
                    x=sell_signals,
                    y=sell_prices,
                    mode='markers',
                    name='Sell Signals',
                    marker=dict(color='red', size=10, symbol='triangle-down')
                ),
                row=1, col=1
            )
        
        fig.update_layout(
            title=f'{analysis_result["symbol"]} - {strategy_type} Strategy Analysis',
            height=700,
            showlegend=True,
            xaxis_rangeslider_visible=False
        )
        
        return fig
    
    def display_performance_dashboard(self, result):
        """Display comprehensive performance dashboard"""
        performance = result.get('trading_performance', {})
        
        st.subheader("Trading Performance Dashboard")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Current Price", f"${result['current_price']:.2f}")
        with col2:
            if result['current_signal'] == 'BUY':
                signal_display = '<span style="color: green; font-weight: bold;">BUY</span>'
            elif result['current_signal'] == 'SELL':
                signal_display = '<span style="color: red; font-weight: bold;">SELL</span>'
            elif result['current_signal'] == 'HOLD':
                signal_display = '<span style="color: orange; font-weight: bold;">HOLD</span>'
            else:
                signal_display = result['current_signal']
            st.metric("Current Signal", "")
            st.markdown(f"**Current Signal:** {signal_display}", unsafe_allow_html=True)
        with col3:
            total_return = performance.get('total_return', 0)
            st.metric("Total Strategy Return", f"{total_return:.2%}", 
                     f"{total_return:.2%}")
        with col4:
            buy_hold = performance.get('buy_hold_return', 0)
            st.metric("Buy & Hold Return", f"{buy_hold:.2%}")
        with col5:
            vs_market = performance.get('strategy_vs_buy_hold', 0)
            st.metric("vs Market", f"{vs_market:.2%}", 
                     f"{vs_market:.2%}")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Trades", performance.get('total_trades', 0))
        with col2:
            win_rate = performance.get('win_rate', 0)
            st.metric("Win Rate", f"{win_rate:.1%}")
        with col3:
            avg_return = performance.get('avg_return_per_trade', 0)
            st.metric("Avg Return/Trade", f"{avg_return:.2%}")
        with col4:
            sharpe = performance.get('sharpe_ratio', 0)
            st.metric("Sharpe Ratio", f"{sharpe:.2f}")
        with col5:
            max_dd = performance.get('max_drawdown', 0)
            st.metric("Max Drawdown", f"{max_dd:.2%}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            volatility = performance.get('volatility', 0)
            st.metric("Annualized Volatility", f"{volatility:.2%}")
        with col2:
            price_sma20 = performance.get('price_to_sma_20', 1)
            st.metric("Price/SMA20 Ratio", f"{price_sma20:.2f}")
        with col3:
            price_sma50 = performance.get('price_to_sma_50', 1)
            st.metric("Price/SMA50 Ratio", f"{price_sma50:.2f}")
    
    def display_trading_analysis(self, result):
        """Display detailed trading analysis"""
        performance = result.get('trading_performance', {})
        trades = performance.get('trades', [])
        
        if not trades:
            st.info("No completed trades found for the selected period.")
            return
        
        st.subheader("Detailed Trading History")
    
        trades_df = pd.DataFrame(trades)
        trades_df['return_pct'] = trades_df['return'] * 100
        trades_df['entry_time'] = pd.to_datetime(trades_df['entry_time'])
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Winning Trades:**")
            winning_trades = trades_df[trades_df['return'] > 0]
            if not winning_trades.empty:
                st.write(f"- Count: {len(winning_trades)}")
                st.write(f"- Average Return: {winning_trades['return'].mean():.2%}")
                st.write(f"- Best Trade: {winning_trades['return'].max():.2%}")
                st.write(f"- Average Duration: {winning_trades['duration_days'].mean():.1f} days")
        
        with col2:
            st.write("**Losing Trades:**")
            losing_trades = trades_df[trades_df['return'] <= 0]
            if not losing_trades.empty:
                st.write(f"- Count: {len(losing_trades)}")
                st.write(f"- Average Return: {losing_trades['return'].mean():.2%}")
                st.write(f"- Worst Trade: {losing_trades['return'].min():.2%}")
                st.write(f"- Average Duration: {losing_trades['duration_days'].mean():.1f} days")
        
        st.subheader("All Trades")
        display_df = trades_df[['entry_time', 'entry_price', 'exit_time', 'exit_price', 'return_pct', 'profit', 'duration_days']].copy()
        display_df.columns = ['Entry Date', 'Entry Price', 'Exit Date', 'Exit Price', 'Return %', 'Profit $', 'Duration (days)']
        display_df['Return %'] = display_df['Return %'].round(2)
        display_df['Profit $'] = display_df['Profit $'].round(2)
        
        st.dataframe(display_df, use_container_width=True)
        
        if len(trades_df) > 1:
            st.subheader("Returns Distribution")
            
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=trades_df['return_pct'],
                nbinsx=20,
                name='Trade Returns',
                marker_color='lightblue',
                opacity=0.7
            ))
            
            fig.update_layout(
                title="Distribution of Trade Returns (%)",
                xaxis_title="Return (%)",
                yaxis_title="Number of Trades",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)

def main():
    st.set_page_config(
        page_title="Quantify - Trading Strategy Analyzer",
        page_icon="",
        layout="wide"
    )
    
    st.title("Welcome to Quantify!")
    st.markdown("### Your personal trading strategy analysis and paper trading platform.")
    
    analyzer = TradingAnalyzer()
    
    if not analyzer.strategies_info:
        st.warning("Could not connect to the backend. Please ensure the backend server is running.")
        st.code("cd backend && python api_server.py")
        st.stop()
        
    st.success("Successfully connected to the backend API!")
    
    st.markdown("""
    **This application is now divided into several pages:**

    - **Portfolio**: Manage and track your paper trading portfolio.
    - **Strategy Analysis**: Analyze stock performance using various trading strategies like SMA and RSI. Get live trading signals.
    - **Dynamic Merton Backtest**: Run sophisticated backtests using the Dynamic Regime Merton model.

    Please use the sidebar to navigate to the desired section.
    """)

    st.markdown("---")
    st.header("Available Strategies")
    
    for strategy_key, strategy_info in analyzer.strategies_info.items():
        st.markdown(f"""
        #### {strategy_info.get('name', strategy_key.upper())}
        - *{strategy_info.get('description', 'No description available')}*
        """)
    
    st.info("Select a page from the sidebar to get started!")

if __name__ == "__main__":
    main()
