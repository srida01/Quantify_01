import streamlit as st
import requests
import time
import json
from datetime import datetime

class LivePriceWidget:
    """Live price display widget with WebSocket support"""
    
    def __init__(self, api_base_url="http://127.0.0.1:5000/api"):
        self.api_base_url = api_base_url
        
    def display_live_price(self, symbol):
        """Display live price for a symbol"""
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.subheader(f"{symbol} Live Price")
            
        with col3:
            if st.button("Refresh", key=f"refresh_{symbol}"):
                st.rerun()
        
        price_placeholder = st.empty()
        
        try:
            response = requests.get(f"{self.api_base_url}/live-price/{symbol}", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    price = data["price"]
                    timestamp = data["timestamp"]
                    provider = data["provider"]
                    
                    with price_placeholder.container():
                        col1, col2, col3 = st.columns([2, 2, 2])
                        
                        with col1:
                            st.metric(
                                label="Current Price",
                                value=f"${price:.2f}",
                                delta=None
                            )
                            
                        with col2:
                            st.metric(
                                label="Data Source",
                                value=provider.replace('_', ' ').title()
                            )
                            
                        with col3:
                            dt = datetime.fromtimestamp(timestamp)
                            st.metric(
                                label="Updated",
                                value=dt.strftime("%H:%M:%S")
                            )
                    
                    st.success("Live data streaming")
                    
                    return price
                else:
                    st.error(f"Error: {data.get('error', 'Unknown error')}")
            else:
                st.error(f"Failed to fetch live price (Status: {response.status_code})")
                
        except requests.exceptions.ConnectionError:
            st.error("Backend server is not running")
            st.code("cd backend && python api_server.py")
        except Exception as e:
            st.error(f"Error fetching live price: {str(e)}")
        
        return None
    
    def display_price_comparison(self, symbols):
        """Display multiple symbols with live prices"""
        st.subheader("Live Price Dashboard")
        
        cols = st.columns(len(symbols))
        
        for i, symbol in enumerate(symbols):
            with cols[i]:
                price = self.get_live_price(symbol)
                if price:
                    st.metric(
                        label=symbol,
                        value=f"${price:.2f}",
                        delta=None
                    )
                else:
                    st.metric(
                        label=symbol,
                        value="N/A",
                        delta=None
                    )
    
    def get_live_price(self, symbol):
        """Get live price for a symbol"""
        try:
            response = requests.get(f"{self.api_base_url}/live-price/{symbol}", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data["success"]:
                    return data["price"]
        except:
            pass
        return None
    
    def display_streaming_status(self):
        """Display current streaming status"""
        try:
            response = requests.get(f"{self.api_base_url}/streaming/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                active_streams = data.get("active_streams", [])
                
                if active_streams:
                    st.success(f"Live streaming active for: {', '.join(active_streams)}")
                else:
                    st.info("No active live streams")
                    
                return active_streams
        except:
            st.warning("Unable to check streaming status")
        
        return []

def create_live_price_section():
    """Create live price section for the main app"""
    st.markdown("---")
    st.header("Live Market Data")
    
    live_widget = LivePriceWidget()
    
    col1, col2 = st.columns([3, 1])
    with col1:
        symbol = st.text_input(
            "Enter Stock Symbol", 
            value="AAPL", 
            help="Enter a stock symbol (e.g., AAPL, GOOGL, MSFT)"
        ).upper()
    
    with col2:
        st.write("")
        show_live = st.checkbox("Live Mode", value=True)
    
    if show_live and symbol:
        price = live_widget.display_live_price(symbol)
        
        live_widget.display_streaming_status()
        
        time.sleep(2)
        st.rerun()
    
    elif symbol:
        st.info("Enable Live Mode to see real-time prices")
        
    st.subheader("Multiple Symbols")
    popular_symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
    selected_symbols = st.multiselect(
        "Select symbols for comparison",
        popular_symbols,
        default=["AAPL", "GOOGL"]
    )
    
    if selected_symbols:
        live_widget.display_price_comparison(selected_symbols)