from flask_socketio import SocketIO
import threading
import time
from typing import Dict, List
import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.data.live_api_service import LiveAPIService


class LivePriceStream:
    """WebSocket-based live price streaming"""
    
    def __init__(self, socketio: SocketIO):
        self.socketio = socketio
        self.api_service = LiveAPIService()
        self.active_symbols: Dict[str, bool] = {}
        self.price_threads: Dict[str, threading.Thread] = {}
        self.clients: Dict[str, List[str]] = {}  # symbol -> [client_ids]
        
    def start_streaming(self, symbol: str, client_id: str):
        """Start streaming prices for a symbol"""
        symbol = symbol.upper()
        
        if symbol not in self.clients:
            self.clients[symbol] = []
        if client_id not in self.clients[symbol]:
            self.clients[symbol].append(client_id)
            
        if symbol not in self.active_symbols or not self.active_symbols[symbol]:
            self.active_symbols[symbol] = True
            thread = threading.Thread(target=self._price_worker, args=(symbol,))
            thread.daemon = True
            self.price_threads[symbol] = thread
            thread.start()
            print(f" Started live streaming for {symbol}")
    
    def stop_streaming(self, symbol: str, client_id: str):
        """Stop streaming prices for a symbol"""
        symbol = symbol.upper()
        if symbol in self.clients and client_id in self.clients[symbol]:
            self.clients[symbol].remove(client_id)
            
        if symbol in self.clients and len(self.clients[symbol]) == 0:
            self.active_symbols[symbol] = False
            print(f" Stopped streaming for {symbol}")
    
    def _price_worker(self, symbol: str):
        """Background worker to fetch and broadcast prices"""
        last_price = None
        error_count = 0
        
        while self.active_symbols.get(symbol, False):
            try:
                data = self.api_service.get_live_price(symbol)
                
                if data and data["price"] != last_price:
                    last_price = data["price"]
                    error_count = 0
                    
                    self.socketio.emit('price_update', {
                        'symbol': symbol,
                        'price': data["price"],
                        'volume': data.get("volume", 0),
                        'timestamp': data["timestamp"],
                        'provider': data["provider"]
                    }, room=f"symbol_{symbol}")
                    
                    print(f"[INFO] Broadcasted {symbol}: ${data['price']}")
                
                time.sleep(1)  
                
            except Exception as e:
                error_count += 1
                print(f"[ERROR] Price worker error for {symbol}: {e}")
                if error_count > 5:
                    print(f"Too many errors for {symbol}, stopping stream")
                    self.active_symbols[symbol] = False
                time.sleep(10)
    
    def get_active_streams(self) -> List[str]:
        """Get list of currently active symbol streams"""
        return [symbol for symbol, active in self.active_symbols.items() if active]