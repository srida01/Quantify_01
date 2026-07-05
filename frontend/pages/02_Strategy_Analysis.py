import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import requests
import json
from datetime import datetime, timedelta
import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from project.frontend.app import TradingAnalyzer

st.set_page_config(
    page_title="Trading Strategy Analyzer",
    page_icon="",
    layout="wide"
)

st.title("Trading Strategy Analyzer")
st.markdown("Analyze stocks with backend-powered strategies")

analyzer = TradingAnalyzer()

if not analyzer.strategies_info:
    st.stop()

with st.sidebar:
    st.header("Configuration")
    symbol = st.text_input("Stock Symbol", value="AAPL", help="Enter stock ticker (e.g., AAPL, GOOGL)")
    period_options = {
        "1 Month": "1mo",
        "3 Months": "3mo",
        "6 Months": "6mo",
        "1 Year": "1y",
        "2 Years": "2y"
    }
    selected_period = st.selectbox("Time Period", list(period_options.keys()), index=2)
    period = period_options[selected_period]
    available_strategies = list(analyzer.strategies_info.keys())
    strategy_names = {
        "sma": "SMA (Simple Moving Average)",
        "rsi": "RSI (Relative Strength Index)"
    }

    strategy_display = st.selectbox(
        "Strategy",
        [strategy_names.get(s, s.upper()) for s in available_strategies] + ["Compare Both"]
    )

    if strategy_display == "Compare Both":
        strategy = "both"
    else:
        strategy = next(k for k, v in strategy_names.items() if v == strategy_display)

    st.subheader("Strategy Parameters")

    params = {}

    if strategy in ["sma", "both"]:
        if strategy == "both":
            st.write("**SMA Parameters**")

        sma_info = analyzer.strategies_info.get("sma", {}).get("params", {})
        params["sma"] = {
            "fast": st.slider("Fast SMA Period",
                             sma_info.get("fast", {}).get("min", 5),
                             sma_info.get("fast", {}).get("max", 30),
                             sma_info.get("fast", {}).get("default", 10)),
            "slow": st.slider("Slow SMA Period",
                             sma_info.get("slow", {}).get("min", 20),
                             sma_info.get("slow", {}).get("max", 100),
                             sma_info.get("slow", {}).get("default", 20))
        }

    if strategy in ["rsi", "both"]:
        if strategy == "both":
            st.write("**RSI Parameters**")

        rsi_info = analyzer.strategies_info.get("rsi", {}).get("params", {})
        params["rsi"] = {
            "period": st.slider("RSI Period",
                               rsi_info.get("period", {}).get("min", 10),
                               rsi_info.get("period", {}).get("max", 30),
                               rsi_info.get("period", {}).get("default", 14)),
            "lower": st.slider("RSI Lower Threshold",
                              rsi_info.get("lower", {}).get("min", 20),
                              rsi_info.get("lower", {}).get("max", 40),
                              rsi_info.get("lower", {}).get("default", 30)),
            "upper": st.slider("RSI Upper Threshold",
                              rsi_info.get("upper", {}).get("min", 60),
                              rsi_info.get("upper", {}).get("max", 80),
                              rsi_info.get("upper", {}).get("default", 70))
        }

    analyze_btn = st.button("Analyze", type="primary")

    st.subheader("Live Trading Signal")

    col1, col2 = st.columns([2, 1])

    with col1:
        if st.button("Get Live Signal", type="primary") and symbol and strategy != "both":
            with st.spinner("Getting live signal with historical context..."):
                live_result = analyzer.get_live_signal(
                    symbol.upper(),
                    strategy,
                    params.get(strategy, {})
                )

                if "error" in live_result:
                    st.error(f"Live signal error: {live_result['error']}")
                else:
                    if live_result['signal'] == 'BUY':
                        signal_display = '<span style="color: green; font-weight: bold;">BUY</span>'
                    elif live_result['signal'] == 'SELL':
                        signal_display = '<span style="color: red; font-weight: bold;">SELL</span>'
                    elif live_result['signal'] == 'HOLD':
                        signal_display = '<span style="color: orange; font-weight: bold;">HOLD</span>'
                    else:
                        signal_display = live_result['signal']

                    st.markdown(f"**Live Signal:** {signal_display}", unsafe_allow_html=True)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"Price: **${live_result['price']:.2f}**")

                        if 'price_change' in live_result:
                            change = live_result['price_change']
                            change_pct = live_result.get('price_change_pct', 0)
                            change_text = "[UP]" if change > 0 else "[DOWN]" if change < 0 else "[FLAT]"
                            st.caption(f"{change_text} {change:+.2f} ({change_pct:+.2f}%)")

                    with col2:
                        if 'volume' in live_result:
                            st.info(f"Volume: **{live_result['volume']:,}**")

                    with col3:
                        if 'context' in live_result:
                            st.info(f"{live_result['context']}")

                    if live_result['signal'] == 'HOLD':
                        if strategy == 'sma':
                            st.caption(" **SMA Strategy**: Waiting for moving average crossover signal...")
                        elif strategy == 'rsi':
                            st.caption("**RSI Strategy**: No clear momentum signal at current levels...")
                    elif live_result['signal'] == 'BUY':
                        st.success("**Strategy Recommendation**: Consider buying position")
                    elif live_result['signal'] == 'SELL':
                        st.warning("**Strategy Recommendation**: Consider selling position")

    with col2:
        auto_refresh = st.checkbox("Auto-refresh (30s)")
        if auto_refresh and symbol and strategy != "both":
            st.empty()

if analyze_btn and symbol:
    with st.spinner(f"Analyzing {symbol} with backend strategies..."):

        if strategy == "sma":
            st.subheader("SMA Strategy Analysis")
            result = analyzer.analyze_symbol(symbol.upper(), "sma", params["sma"], period)

            if "error" not in result:
                analyzer.display_performance_dashboard(result)
                fig = analyzer.create_price_chart(result)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                analyzer.display_trading_analysis(result)
            else:
                st.error(f"Analysis failed: {result['error']}")

        elif strategy == "rsi":
            st.subheader("RSI Strategy Analysis")
            result = analyzer.analyze_symbol(symbol.upper(), "rsi", params["rsi"], period)

            if "error" not in result:
                analyzer.display_performance_dashboard(result)

                fig = analyzer.create_price_chart(result)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

                analyzer.display_trading_analysis(result)
            else:
                st.error(f"Analysis failed: {result['error']}")

        elif strategy == "both":
            st.subheader("SMA Strategy Analysis")
            sma_result = analyzer.analyze_symbol(symbol.upper(), "sma", params["sma"], period)
            if "error" not in sma_result:
                fig_sma = analyzer.create_price_chart(sma_result)
                if fig_sma:
                    st.plotly_chart(fig_sma, use_container_width=True)

            st.subheader("RSI Strategy Analysis")
            rsi_result = analyzer.analyze_symbol(symbol.upper(), "rsi", params["rsi"], period)
            if "error" not in rsi_result:
                fig_rsi = analyzer.create_price_chart(rsi_result)
                if fig_rsi:
                    st.plotly_chart(fig_rsi, use_container_width=True)

            if "error" not in sma_result and "error" not in rsi_result:
                st.subheader("Strategy Comparison")

                col1, col2 = st.columns(2)
                with col1:
                    st.write("**SMA Strategy**")
                    if sma_result['current_signal'] == 'BUY':
                        sma_signal_display = '<span style="color: green; font-weight: bold;">BUY</span>'
                    elif sma_result['current_signal'] == 'SELL':
                        sma_signal_display = '<span style="color: red; font-weight: bold;">SELL</span>'
                    elif sma_result['current_signal'] == 'HOLD':
                        sma_signal_display = '<span style="color: orange; font-weight: bold;">HOLD</span>'
                    else:
                        sma_signal_display = sma_result['current_signal']
                    st.markdown(f"Current Signal: {sma_signal_display}", unsafe_allow_html=True)
                    st.write(f"Buy Signals: {sma_result['buy_count']}")
                    st.write(f"Sell Signals: {sma_result['sell_count']}")

                with col2:
                    st.write("**RSI Strategy**")
                    if rsi_result['current_signal'] == 'BUY':
                        rsi_signal_display = '<span style="color: green; font-weight: bold;">BUY</span>'
                    elif rsi_result['current_signal'] == 'SELL':
                        rsi_signal_display = '<span style="color: red; font-weight: bold;">SELL</span>'
                    elif rsi_result['current_signal'] == 'HOLD':
                        rsi_signal_display = '<span style="color: orange; font-weight: bold;">HOLD</span>'
                    else:
                        rsi_signal_display = rsi_result['current_signal']
                    st.markdown(f"Current Signal: {rsi_signal_display}", unsafe_allow_html=True)
                    st.write(f"Buy Signals: {rsi_result['buy_count']}")
                    st.write(f"Sell Signals: {rsi_result['sell_count']}")

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'components'))
from live_price_widget import create_live_price_section
create_live_price_section()
