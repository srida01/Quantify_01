from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
import yfinance as yf
import pandas as pd
import numpy as np
import sys
import os
from datetime import datetime

# Add parent directory to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from project.backend.strategies.rsi_manual import RSIMomentumStrategy
from project.backend.strategies.sma_manual import SMAStrategy
from project.backend.core.event import MarketEvent, SignalType
from project.backend.data.data_source import MockMarketDataSource
from project.backend.data.live_data_polling import LiveMarketDataSource
from project.backend.data.live_api_service import EnhancedLiveMarketDataSource, LiveAPIService

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'websocket'))
from price_stream import LivePriceStream
from video_stream import LiveBacktestStream

from project.backend.execution.paper_broker import PaperBroker

from project.backend.strategies.merton_backtest_runner import run_merton_backtest
results_store = {}  
app = Flask(__name__)
CORS(app)  
socketio = SocketIO(app, cors_allowed_origins="*")

price_stream = LivePriceStream(socketio)
backtest_stream = LiveBacktestStream(socketio)
paper_broker = PaperBroker()  

class StrategyAPI:
    def __init__(self):
        self.strategies = {
            'sma': SMAStrategy,
            'rsi': RSIMomentumStrategy
        }
    
    def get_available_strategies(self):
        """Return list of available strategies"""
        return list(self.strategies.keys())
    
    def analyze_symbol(self, symbol, strategy_type, params, period="1mo"):
        """Analyze a symbol with given strategy and parameters"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period=period, interval="1d")
            
            if data.empty:
                return {"error": f"No data found for symbol {symbol}"}
            
            if strategy_type == 'sma':
                strategy = self.strategies[strategy_type](
                    fast=params.get('fast', 10),
                    slow=params.get('slow', 20)
                )
            elif strategy_type == 'rsi':
                strategy = self.strategies[strategy_type](
                    rsi_period=params.get('period', 14),
                    rsi_lower=params.get('lower', 30),
                    rsi_upper=params.get('upper', 70)
                )
            else:
                return {"error": f"Unknown strategy type: {strategy_type}"}
            
            signals = []
            prices = []
            timestamps = []
            
            for timestamp, row in data.iterrows():
                price = float(row['Close'])
                signal = strategy.on_price(symbol, price)
                
                signals.append({
                    'timestamp': timestamp.isoformat(),
                    'price': price,
                    'signal': signal.action.value,
                    'volume': int(row['Volume'])
                })
                prices.append(price)
                timestamps.append(timestamp.isoformat())
            
            buy_signals = [i for i, s in enumerate(signals) if s['signal'] == 'BUY']
            sell_signals = [i for i, s in enumerate(signals) if s['signal'] == 'SELL']
            
            trading_performance = self._calculate_trading_performance(signals, data)
            
            indicators = self._get_strategy_indicators(strategy, data, strategy_type, params)
            
            return {
                "symbol": symbol,
                "strategy": strategy_type,
                "params": params,
                "signals": signals,
                "buy_count": len(buy_signals),
                "sell_count": len(sell_signals),
                "current_signal": signals[-1]['signal'] if signals else 'HOLD',
                "current_price": prices[-1] if prices else 0,
                "indicators": indicators,
                "trading_performance": trading_performance,
                "data": {
                    "open": data['Open'].tolist(),
                    "high": data['High'].tolist(),
                    "low": data['Low'].tolist(),
                    "close": data['Close'].tolist(),
                    "volume": data['Volume'].tolist(),
                    "timestamps": timestamps
                }
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _get_strategy_indicators(self, strategy, data, strategy_type, params):
        """Calculate strategy-specific indicators for plotting"""
        indicators = {}
        
        if strategy_type == 'sma':
            fast = params.get('fast', 10)
            slow = params.get('slow', 20)
            
            sma_fast = []
            sma_slow = []
            
            for i in range(len(data)):
                if i >= fast - 1:
                    fast_val = data.iloc[max(0, i-fast+1):i+1]['Close'].mean()
                    sma_fast.append(fast_val)
                else:
                    sma_fast.append(None)
                
                if i >= slow - 1:
                    slow_val = data.iloc[max(0, i-slow+1):i+1]['Close'].mean()
                    sma_slow.append(slow_val)
                else:
                    sma_slow.append(None)
            
            indicators = {
                'sma_fast': sma_fast,
                'sma_slow': sma_slow,
                'fast_period': fast,
                'slow_period': slow
            }
            
        elif strategy_type == 'rsi':
            period = params.get('period', 14)
            lower = params.get('lower', 30)
            upper = params.get('upper', 70)
            
            rsi_values = []
            for i in range(len(data)):
                if i >= period:
                    gains = []
                    losses = []
                    for j in range(i-period+1, i+1):
                        if j > 0:
                            change = data.iloc[j]['Close'] - data.iloc[j-1]['Close']
                            gains.append(max(change, 0))
                            losses.append(max(-change, 0))
                    
                    avg_gain = sum(gains) / period if gains else 0
                    avg_loss = sum(losses) / period if losses else 0
                    
                    if avg_loss == 0:
                        rsi = 100
                    else:
                        rs = avg_gain / avg_loss
                        rsi = 100 - (100 / (1 + rs))
                    rsi_values.append(rsi)
                else:
                    rsi_values.append(None)
            
            indicators = {
                'rsi_values': rsi_values,
                'period': period,
                'lower_threshold': lower,
                'upper_threshold': upper
            }
        
        return indicators
    
    def _calculate_trading_performance(self, signals, data):
        """Calculate comprehensive trading performance metrics"""
        trades = []
        current_position = None
        total_return = 0
        total_trades = 0
        winning_trades = 0
        losing_trades = 0
        
        for i, signal_data in enumerate(signals):
            signal = signal_data['signal']
            price = signal_data['price']
            timestamp = signal_data['timestamp']
            
            if signal == 'BUY' and current_position is None:
                current_position = {
                    'type': 'LONG',
                    'entry_price': price,
                    'entry_time': timestamp,
                    'entry_index': i
                }
                
            elif signal == 'SELL' and current_position is not None:
                exit_price = price
                exit_time = timestamp
                
                if current_position['type'] == 'LONG':
                    trade_return = (exit_price - current_position['entry_price']) / current_position['entry_price']
                    trade_profit = exit_price - current_position['entry_price']
                else:
                    trade_return = (current_position['entry_price'] - exit_price) / current_position['entry_price']
                    trade_profit = current_position['entry_price'] - exit_price
                
                trade = {
                    'entry_price': current_position['entry_price'],
                    'exit_price': exit_price,
                    'entry_time': current_position['entry_time'],
                    'exit_time': exit_time,
                    'return': trade_return,
                    'profit': trade_profit,
                    'duration_days': (pd.to_datetime(exit_time) - pd.to_datetime(current_position['entry_time'])).days
                }
                
                trades.append(trade)
                total_return += trade_return
                total_trades += 1
                
                if trade_return > 0:
                    winning_trades += 1
                else:
                    losing_trades += 1
                
                current_position = None
        
        if total_trades > 0:
            avg_return = total_return / total_trades
            win_rate = winning_trades / total_trades
            
            returns = [trade['return'] for trade in trades]
            sharpe_ratio = np.mean(returns) / np.std(returns) if np.std(returns) > 0 else 0
            
            cumulative_returns = np.cumsum(returns)
            running_max = np.maximum.accumulate(cumulative_returns)
            drawdown = cumulative_returns - running_max
            max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
            
        else:
            avg_return = 0
            win_rate = 0
            sharpe_ratio = 0
            max_drawdown = 0
        
        price_data = data['Close']
        current_price = price_data.iloc[-1]
        start_price = price_data.iloc[0]
        
        buy_hold_return = (current_price - start_price) / start_price
        
        daily_returns = price_data.pct_change().dropna()
        volatility = daily_returns.std() * np.sqrt(252)
        
        sma_20 = price_data.rolling(20).mean().iloc[-1] if len(price_data) >= 20 else current_price
        sma_50 = price_data.rolling(50).mean().iloc[-1] if len(price_data) >= 50 else current_price
        
        return {
            'trades': trades,
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_return': total_return,
            'avg_return_per_trade': avg_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'buy_hold_return': buy_hold_return,
            'strategy_vs_buy_hold': total_return - buy_hold_return,
            'volatility': volatility,
            'current_price': current_price,
            'sma_20': sma_20,
            'sma_50': sma_50,
            'price_to_sma_20': current_price / sma_20 if sma_20 > 0 else 1,
            'price_to_sma_50': current_price / sma_50 if sma_50 > 0 else 1
        }
    
    def get_live_signal(self, symbol, strategy_type, params):
        """Get current live signal for a symbol"""
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="50d", interval="1d")
            
            if data.empty:
                return {"error": "No live data available"}
            
            if strategy_type == 'sma':
                strategy = self.strategies[strategy_type](
                    fast=params.get('fast', 10),
                    slow=params.get('slow', 20)
                )
            elif strategy_type == 'rsi':
                strategy = self.strategies[strategy_type](
                    rsi_period=params.get('period', 14),
                    rsi_lower=params.get('lower', 30),
                    rsi_upper=params.get('upper', 70)
                )
            else:
                return {"error": f"Unknown strategy type: {strategy_type}"}
            
            for i, (timestamp, row) in enumerate(data[:-1].iterrows()):
                price = float(row['Close'])
                strategy.on_price(symbol, price)
            
            latest_price = float(data['Close'].iloc[-1])
            signal = strategy.on_price(symbol, latest_price)
            
            latest_timestamp = data.index[-1]
            volume = int(data['Volume'].iloc[-1])
            
            price_change = latest_price - float(data['Close'].iloc[-2])
            price_change_pct = (price_change / float(data['Close'].iloc[-2])) * 100
            
            return {
                "symbol": symbol,
                "price": latest_price,
                "timestamp": latest_timestamp.isoformat(),
                "signal": signal.action.value,
                "strategy": strategy_type,
                "volume": volume,
                "price_change": price_change,
                "price_change_pct": price_change_pct,
                "context": f"Based on {len(data)} days of historical data"
            }
            
        except Exception as e:
            return {"error": str(e)}

strategy_api = StrategyAPI()


@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    """Get list of available strategies"""
    return jsonify({
        "strategies": strategy_api.get_available_strategies(),
        "strategy_info": {
            "sma": {
                "name": "Simple Moving Average",
                "description": "Crossover strategy using fast and slow moving averages",
                "params": {
                    "fast": {"type": "int", "default": 10, "min": 5, "max": 30},
                    "slow": {"type": "int", "default": 20, "min": 20, "max": 100}
                }
            },
            "rsi": {
                "name": "RSI Momentum",
                "description": "Relative Strength Index momentum strategy",
                "params": {
                    "period": {"type": "int", "default": 14, "min": 10, "max": 30},
                    "lower": {"type": "int", "default": 30, "min": 20, "max": 40},
                    "upper": {"type": "int", "default": 70, "min": 60, "max": 80}
                }
            }
        }
    })

@app.route('/api/backtest/dynamic_merton', methods=['POST'])
def backtest_dynamic_merton():
    return jsonify({
        "success": False, 
        "error": "This HTTP endpoint is deprecated. Please use the WebSocket interface."
    }), 404


@app.route('/api/analyze', methods=['POST'])
def analyze():
    """Analyze a symbol with given strategy"""
    data = request.get_json()
    
    symbol = data.get('symbol', 'AAPL').upper()
    strategy_type = data.get('strategy', 'sma')
    params = data.get('params', {})
    period = data.get('period', '1mo')
    
    result = strategy_api.analyze_symbol(symbol, strategy_type, params, period)
    return jsonify(result)

@app.route('/api/live-signal', methods=['POST'])
def get_live_signal():
    """Get live signal for a symbol"""
    data = request.get_json()
    
    symbol = data.get('symbol', 'AAPL').upper()
    strategy_type = data.get('strategy', 'sma')
    params = data.get('params', {})
    
    result = strategy_api.get_live_signal(symbol, strategy_type, params)
    return jsonify(result)

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/live-price/<symbol>', methods=['GET'])
def get_live_price(symbol):
    """Get current live price for a symbol"""
    try:
        api_service = LiveAPIService()
        data = api_service.get_live_price(symbol.upper())
        
        if data:
            return jsonify({
                "success": True,
                "symbol": symbol.upper(),
                "price": data["price"],
                "timestamp": data["timestamp"],
                "provider": data["provider"]
            })
        else:
            return jsonify({"success": False, "error": "No live data available"}), 404
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/streaming/status', methods=['GET'])
def get_streaming_status():
    """Get current streaming status"""
    active_streams = price_stream.get_active_streams()
    return jsonify({
        "active_streams": active_streams,
        "total_streams": len(active_streams)
    })

@app.route('/api/portfolio', methods=['GET'])
def get_portfolio():
    """Get current paper trading portfolio"""
    try:
        current_prices = {}
        for symbol in paper_broker.positions.keys():
            try:
                api_service = LiveAPIService()
                price_data = api_service.get_live_price(symbol)
                if price_data:
                    current_prices[symbol] = price_data["price"]
            except:
                current_prices[symbol] = paper_broker.positions[symbol]['avg_price']  # Fallback
        
        summary = paper_broker.get_portfolio_summary(current_prices)
        
        return jsonify({
            "success": True,
            "portfolio": summary,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/portfolio/reset', methods=['POST'])
def reset_portfolio():
    """Reset paper trading portfolio"""
    try:
        paper_broker.reset_portfolio()
        paper_broker.save_portfolio()
        
        return jsonify({
            "success": True,
            "message": "Portfolio reset to $100,000",
            "new_balance": paper_broker.cash_balance
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/get_results/<client_id>')
def get_results(client_id):
    data = results_store.get(client_id) or (
        results_store[next(reversed(results_store))]
        if results_store else None
    )
    if data:
        return jsonify({"ready": True, "results": data})
    return jsonify({"ready": False})

@app.route('/api/trade', methods=['POST'])
def execute_trade():
    """Execute paper trade"""
    try:
        data = request.get_json()
        symbol = data.get('symbol', '').upper()
        action = data.get('action', '').upper()  
        quantity = data.get('quantity')  
        
        if not symbol or action not in ['BUY', 'SELL']:
            return jsonify({"success": False, "error": "Invalid symbol or action"}), 400
        
        if action == 'BUY' and quantity is not None and quantity <= 0:
            return jsonify({"success": False, "error": "Quantity must be greater than 0"}), 400
        
        api_service = LiveAPIService()
        price_data = api_service.get_live_price(symbol)
        
        if not price_data:
            return jsonify({"success": False, "error": "Could not get current price"}), 400
        
        current_price = price_data["price"]
        
        from project.backend.core.event import Signal, SignalType
        import time
        signal_type = SignalType.BUY if action == 'BUY' else SignalType.SELL
        signal = Signal(symbol, signal_type, time.time())  # Add timestamp
        
        success = paper_broker.execute(signal, current_price, quantity)
        
        if success:
            current_prices = {symbol: current_price}
            summary = paper_broker.get_portfolio_summary(current_prices)
            
            return jsonify({
                "success": True,
                "message": f"{action} order executed for {symbol}",
                "trade": {
                    "symbol": symbol,
                    "action": action,
                    "price": current_price,
                    "timestamp": datetime.now().isoformat()
                },
                "portfolio": summary
            })
        else:
            return jsonify({"success": False, "error": "Trade execution failed"}), 400
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@socketio.on('connect')
def handle_connect():
    emit('connection_status', {'status': 'connected'})
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('start_backtest_stream')
def handle_start_backtest_stream(data):
    client_id = request.sid
    start_date = data.get('start_date', '2015-01-01')
    end_date = data.get('end_date', '2025-01-01')
    print(f"Received 'start_backtest_stream' from client {client_id}")
    results_store.clear()
    backtest_stream.start_streaming(start_date, end_date, client_id, results_store)
    emit('stream_status', {'status': 'started', 'message': 'Backtest stream initiated. Waiting for frames...'})

@app.route('/clear_results', methods=['POST'])
def clear_results():
    results_store.clear()
    return jsonify({"cleared": True})

@socketio.on('subscribe_price')
def handle_subscribe_price(data):
    """Subscribe to live price updates for a symbol"""
    symbol = data.get('symbol', '').upper()
    client_id = request.sid
    
    if symbol:
        join_room(f"symbol_{symbol}")
        price_stream.start_streaming(symbol, client_id)
        emit('subscription_status', {
            'symbol': symbol,
            'status': 'subscribed',
            'message': f'Subscribed to {symbol} live prices'
        })
        print(f"[INFO] Client {client_id} subscribed to {symbol}")

@socketio.on('unsubscribe_price')
def handle_unsubscribe_price(data):
    """Unsubscribe from live price updates"""
    symbol = data.get('symbol', '').upper()
    client_id = request.sid
    
    if symbol:
        leave_room(f"symbol_{symbol}")
        price_stream.stop_streaming(symbol, client_id)
        emit('subscription_status', {
            'symbol': symbol,
            'status': 'unsubscribed',
            'message': f'Unsubscribed from {symbol} live prices'
        })
        print(f"Client {client_id} unsubscribed from {symbol}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
