import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import SignalType
from datetime import datetime
import json
import os


class PaperBroker:
    """Enhanced Paper Trading Broker with Virtual Money Management"""
    
    def __init__(self, initial_balance=100000, data_file="paper_portfolio.json"):
        self.initial_balance = initial_balance
        self.data_file = data_file
        self.load_portfolio()
    
    def load_portfolio(self):
        """Load portfolio from file or create new one"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.cash_balance = data.get('cash_balance', self.initial_balance)
                    self.positions = data.get('positions', {})
                    self.transactions = data.get('transactions', [])
                    self.total_invested = data.get('total_invested', 0)
            else:
                self.reset_portfolio()
        except Exception as e:
            print(f"Error loading portfolio: {e}")
            self.reset_portfolio()
    
    def save_portfolio(self):
        """Save portfolio to file"""
        try:
            data = {
                'cash_balance': self.cash_balance,
                'positions': self.positions,
                'transactions': self.transactions,
                'total_invested': self.total_invested,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving portfolio: {e}")
    
    def reset_portfolio(self):
        """Reset portfolio to initial state"""
        self.cash_balance = self.initial_balance
        self.positions = {}  # {symbol: {quantity: int, avg_price: float}}
        self.transactions = []
        self.total_invested = 0
    
    def get_portfolio_value(self, current_prices=None):
        """Calculate total portfolio value"""
        total_value = self.cash_balance
        
        if current_prices:
            for symbol, position in self.positions.items():
                if symbol in current_prices:
                    market_value = position['quantity'] * current_prices[symbol]
                    total_value += market_value
                    
        return total_value
    
    def get_portfolio_summary(self, current_prices=None):
        """Get complete portfolio summary"""
        summary = {
            'cash_balance': self.cash_balance,
            'initial_balance': self.initial_balance,
            'positions': self.positions,
            'total_transactions': len(self.transactions),
            'recent_transactions': self.transactions[-5:] if self.transactions else []
        }
        
        if current_prices:
            portfolio_value = self.get_portfolio_value(current_prices)
            total_return = portfolio_value - self.initial_balance
            total_return_pct = (total_return / self.initial_balance) * 100
            
            summary.update({
                'portfolio_value': portfolio_value,
                'total_return': total_return,
                'total_return_pct': total_return_pct,
                'positions_value': {}
            })
            
            # Calculate individual position values
            for symbol, position in self.positions.items():
                if symbol in current_prices:
                    current_value = position['quantity'] * current_prices[symbol]
                    cost_basis = position['quantity'] * position['avg_price']
                    unrealized_pnl = current_value - cost_basis
                    
                    summary['positions_value'][symbol] = {
                        'quantity': position['quantity'],
                        'avg_price': position['avg_price'],
                        'current_price': current_prices[symbol],
                        'current_value': current_value,
                        'cost_basis': cost_basis,
                        'unrealized_pnl': unrealized_pnl,
                        'unrealized_pnl_pct': (unrealized_pnl / cost_basis) * 100 if cost_basis > 0 else 0
                    }
        
        return summary
    
    def execute(self, signal, current_price=None, quantity=None):
        """Execute trading signal with proper money management"""
        if current_price is None:
            print("[ERROR] Cannot execute trade without current price")
            return False
            
        symbol = signal.symbol
        action = signal.action
        timestamp = datetime.now().isoformat()
        
        if action == SignalType.BUY:
            return self._execute_buy(symbol, current_price, timestamp, quantity)
        elif action == SignalType.SELL:
            return self._execute_sell(symbol, current_price, timestamp)
        
        return False
    
    def _execute_buy(self, symbol, price, timestamp, quantity=None):
        """Execute buy order"""
        if quantity is None:
            # Use 10% of available cash for each trade
            max_investment = self.cash_balance * 0.1
            quantity = int(max_investment // price)
        
        if quantity <= 0:
            print(f"[ERROR] Cannot buy {symbol}: Insufficient funds (Cash: ${self.cash_balance:.2f})")
            return False
        
        total_cost = quantity * price
        
        if total_cost > self.cash_balance:
            print(f"[ERROR] Cannot buy {symbol}: Insufficient funds")
            return False
        
        # Update cash and positions
        self.cash_balance -= total_cost
        
        if symbol in self.positions:
            # Average down
            old_quantity = self.positions[symbol]['quantity']
            old_total_cost = old_quantity * self.positions[symbol]['avg_price']
            new_total_cost = old_total_cost + total_cost
            new_quantity = old_quantity + quantity
            new_avg_price = new_total_cost / new_quantity
            
            self.positions[symbol] = {
                'quantity': new_quantity,
                'avg_price': new_avg_price
            }
        else:
            self.positions[symbol] = {
                'quantity': quantity,
                'avg_price': price
            }
        
        # Record transaction
        transaction = {
            'timestamp': timestamp,
            'symbol': symbol,
            'action': 'BUY',
            'quantity': quantity,
            'price': price,
            'total_value': total_cost,
            'cash_balance_after': self.cash_balance
        }
        self.transactions.append(transaction)
        
        print(f"[SUCCESS] BUY {quantity} shares of {symbol} at ${price:.2f} (Total: ${total_cost:.2f})")
        print(f"[INFO] Remaining cash: ${self.cash_balance:.2f}")
        
        self.save_portfolio()
        return True
    
    def _execute_sell(self, symbol, price, timestamp):
        """Execute sell order"""
        if symbol not in self.positions or self.positions[symbol]['quantity'] <= 0:
            print(f"[ERROR] Cannot sell {symbol}: No position held")
            return False
        
        position = self.positions[symbol]
        quantity = position['quantity']
        avg_price = position['avg_price']
        
        total_proceeds = quantity * price
        cost_basis = quantity * avg_price
        profit_loss = total_proceeds - cost_basis
        
        # Update cash and remove position
        self.cash_balance += total_proceeds
        del self.positions[symbol]
        
        # Record transaction
        transaction = {
            'timestamp': timestamp,
            'symbol': symbol,
            'action': 'SELL',
            'quantity': quantity,
            'price': price,
            'total_value': total_proceeds,
            'cost_basis': cost_basis,
            'profit_loss': profit_loss,
            'profit_loss_pct': (profit_loss / cost_basis) * 100,
            'cash_balance_after': self.cash_balance
        }
        self.transactions.append(transaction)
        
        profit_text = "[PROFIT]" if profit_loss > 0 else "[LOSS]"
        print(f"[SUCCESS] SELL {quantity} shares of {symbol} at ${price:.2f} (Total: ${total_proceeds:.2f})")
        print(f"{profit_text} P&L: ${profit_loss:.2f} ({(profit_loss/cost_basis)*100:.2f}%)")
        print(f"[INFO] New cash balance: ${self.cash_balance:.2f}")
        
        self.save_portfolio()
        return True
