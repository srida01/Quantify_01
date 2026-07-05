import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

class PaperPortfolioWidget:
    """Paper Trading Portfolio Display and Management"""
    
    def __init__(self, api_base_url="http://127.0.0.1:5000/api"):
        self.api_base_url = api_base_url
    
    def display_portfolio_dashboard(self):
        """Display complete portfolio dashboard"""
        st.header("Paper Trading Portfolio")
        
        portfolio_data = self.get_portfolio_data()
        
        if not portfolio_data:
            st.error("Could not load portfolio data")
            return
        
        portfolio = portfolio_data.get('portfolio', {})
        
        self._display_overview(portfolio)
        
        self._display_positions(portfolio)
        
        self._display_transactions(portfolio)
        
        self._display_manual_trading()
        
    def _display_overview(self, portfolio):
        """Display portfolio overview"""
        st.subheader("Portfolio Overview")
        
        cash_balance = portfolio.get('cash_balance', 0)
        initial_balance = portfolio.get('initial_balance', 100000)
        portfolio_value = portfolio.get('portfolio_value', cash_balance)
        total_return = portfolio.get('total_return', 0)
        total_return_pct = portfolio.get('total_return_pct', 0)
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "Portfolio Value", 
                f"${portfolio_value:,.2f}",
                f"${total_return:,.2f}"
            )
        
        with col2:
            st.metric(
                "Cash Balance",
                f"${cash_balance:,.2f}"
            )
        
        with col3:
            st.metric(
                "Total Return",
                f"{total_return_pct:.2f}%",
                f"${total_return:,.2f}"
            )
        
        with col4:
            invested_amount = portfolio_value - cash_balance
            st.metric(
                "Invested",
                f"${invested_amount:,.2f}"
            )
        
        with col5:
            positions_count = len(portfolio.get('positions', {}))
            st.metric(
                "Active Positions",
                positions_count
            )
        
        if portfolio.get('positions_value'):
            self._display_allocation_chart(portfolio, cash_balance)
    
    def _display_allocation_chart(self, portfolio, cash_balance):
        """Display portfolio allocation pie chart"""
        positions_value = portfolio.get('positions_value', {})
        
        if positions_value:
            st.subheader("Portfolio Allocation")
            
            labels = list(positions_value.keys()) + ['Cash']
            values = [pos['current_value'] for pos in positions_value.values()] + [cash_balance]
            
            fig = go.Figure(data=[go.Pie(
                labels=labels, 
                values=values,
                hovertemplate='%{label}<br>$%{value:,.2f}<br>%{percent}<extra></extra>',
                textinfo='label+percent'
            )])
            
            fig.update_layout(
                title="Portfolio Allocation",
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def _display_positions(self, portfolio):
        """Display current positions"""
        positions_value = portfolio.get('positions_value', {})
        
        if not positions_value:
            st.info("No active positions")
            return
        
        st.subheader("Current Positions")
        
        positions_data = []
        for symbol, pos in positions_value.items():
            positions_data.append({
                'Symbol': symbol,
                'Quantity': pos['quantity'],
                'Avg Price': f"${pos['avg_price']:.2f}",
                'Current Price': f"${pos['current_price']:.2f}",
                'Market Value': f"${pos['current_value']:,.2f}",
                'Unrealized P&L': f"${pos['unrealized_pnl']:,.2f}",
                'P&L %': f"{pos['unrealized_pnl_pct']:.2f}%"
            })
        
        if positions_data:
            df = pd.DataFrame(positions_data)
            st.dataframe(df, use_container_width=True)
            
            st.write("**Quick Actions:**")
            cols = st.columns(len(positions_value))
            for i, symbol in enumerate(positions_value.keys()):
                with cols[i]:
                    if st.button(f"SELL {symbol}", key=f"sell_{symbol}", type="secondary"):
                        self.execute_trade(symbol, 'SELL')
                        st.rerun()
    
    def _display_transactions(self, portfolio):
        """Display recent transactions"""
        recent_transactions = portfolio.get('recent_transactions', [])
        
        if not recent_transactions:
            st.info("No recent transactions")
            return
        
        st.subheader("Recent Transactions")
        
        tx_data = []
        for tx in recent_transactions:
            profit_loss = tx.get('profit_loss', 0)
            profit_text = "[PROFIT]" if profit_loss > 0 else "[LOSS]" if profit_loss < 0 else "[NEUTRAL]"
            
            tx_data.append({
                'Date': datetime.fromisoformat(tx['timestamp']).strftime('%Y-%m-%d %H:%M'),
                'Symbol': tx['symbol'],
                'Action': tx['action'],
                'Quantity': tx['quantity'],
                'Price': f"${tx['price']:.2f}",
                'Total': f"${tx['total_value']:,.2f}",
                'P&L': f"{profit_text} ${profit_loss:,.2f}" if profit_loss != 0 else "-"
            })
        
        if tx_data:
            df = pd.DataFrame(tx_data)
            st.dataframe(df, use_container_width=True)
    
    def _display_manual_trading(self):
        """Display manual trading interface"""
        st.subheader("Manual Trading")
        
        col1, col2, col3, col4 = st.columns([2, 1.5, 1, 1])
        
        with col1:
            symbol = st.text_input(
                "Stock Symbol", 
                placeholder="e.g. AAPL, GOOGL",
                help="Enter stock symbol to trade"
            ).upper()
        
        with col2:
            quantity = st.number_input(
                "Quantity",
                min_value=1,
                value=1,
                step=1,
                help="Number of shares to buy/sell"
            )
        
        with col3:
            if st.button("BUY", type="primary", disabled=not symbol):
                if symbol:
                    result = self.execute_trade(symbol, 'BUY', quantity)
                    if result['success']:
                        st.success(f"{result['message']}")
                        st.rerun()
                    else:
                        st.error(f"{result['error']}")
        
        with col4:
            if st.button("SELL", disabled=not symbol, type="secondary"):
                if symbol:
                    result = self.execute_trade(symbol, 'SELL', quantity)
                    if result['success']:
                        st.success(f"{result['message']}")
                        st.rerun()
                    else:
                        st.error(f"{result['error']}")
        
        st.markdown("---")
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("**Reset Portfolio**: This will reset your portfolio to $100,000 and clear all positions")
        with col2:
            if st.button("Reset Portfolio", type="secondary"):
                result = self.reset_portfolio()
                if result['success']:
                    st.success("Portfolio reset!")
                    st.rerun()
                else:
                    st.error(f"{result['error']}")
    
    def get_portfolio_data(self):
        """Get portfolio data from API"""
        try:
            response = requests.get(f"{self.api_base_url}/portfolio", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Failed to get portfolio data: {response.status_code}")
                return None
        except requests.exceptions.ConnectionError:
            st.error("Backend server is not running")
            st.code("cd backend && python api_server.py", language="bash")
            return None
        except Exception as e:
            st.error(f"Error getting portfolio data: {str(e)}")
            return None
    
    def execute_trade(self, symbol, action, quantity=None):
        """Execute a trade"""
        try:
            payload = {
                'symbol': symbol,
                'action': action
            }
            if quantity is not None:
                payload['quantity'] = quantity
            response = requests.post(f"{self.api_base_url}/trade", json=payload, timeout=10)
            return response.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def reset_portfolio(self):
        """Reset portfolio"""
        try:
            response = requests.post(f"{self.api_base_url}/portfolio/reset", timeout=10)
            return response.json()
        except Exception as e:
            return {'success': False, 'error': str(e)}


def create_portfolio_section():
    """Create portfolio section for main app"""
    portfolio_widget = PaperPortfolioWidget()
    portfolio_widget.display_portfolio_dashboard()