import yfinance as yf
import requests
import time
from typing import Optional, Dict, Any
import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import MarketEvent


class LiveAPIService:
    """Enhanced live data service with multiple API providers"""
    
    def __init__(self, primary_provider: str = "yfinance"):
        self.primary_provider = primary_provider
        self.providers = {
            "yfinance": self._get_yfinance_data,
        }
    def get_live_price(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get live price with fallback providers"""
        
        try:
            return self.providers[self.primary_provider](symbol)
        except Exception as e:
            print(f"Primary provider {self.primary_provider} failed: {e}")
            
                    
        return None
    
    def _get_yfinance_data(self, symbol: str) -> Dict[str, Any]:
        """Yahoo Finance data (your current working solution)"""
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d", interval="1m")
        
        if data.empty:
            raise RuntimeError(f"No yfinance data for {symbol}")
            
        price = float(data["Close"].iloc[-1])
        volume = int(data["Volume"].iloc[-1]) if not data["Volume"].empty else 0
        
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "volume": volume,
            "timestamp": time.time(),
            "provider": "yfinance"
        }
    
class EnhancedLiveMarketDataSource:
    """Enhanced live market data with multiple providers"""
    
    def __init__(self, symbol: str, poll_interval: int = 5, provider: str = "yfinance"):
        self.symbol = symbol
        self.poll_interval = poll_interval
        self.last_price = None
        self.api_service = LiveAPIService(provider)
        self.error_count = 0
        self.max_errors = 5
        
    def get_next_event(self) -> Optional[MarketEvent]:
        """Get next market event with enhanced error handling"""
        try:
            data = self.api_service.get_live_price(self.symbol)
            
            if data is None:
                self.error_count += 1
                if self.error_count >= self.max_errors:
                    print(f"Too many errors ({self.error_count}), stopping...")
                    return None
                time.sleep(self.poll_interval)
                return None
                
            price = data["price"]
            
            if self.last_price is not None and price == self.last_price:
                time.sleep(self.poll_interval)
                return None
                
            self.last_price = price
            self.error_count = 0 
            
            print(f"Live data from {data['provider']}: ${price}")
            
            time.sleep(self.poll_interval)
            
            return MarketEvent(
                symbol=self.symbol,
                price=price,
                timestamp=data["timestamp"]
            )
            
        except Exception as e:
            print(f"Error getting live data: {e}")
            self.error_count += 1
            time.sleep(self.poll_interval * 2) 
            return None
    
    def get_current_price(self) -> Optional[float]:
        """Get current price without creating event"""
        try:
            data = self.api_service.get_live_price(self.symbol)
            return data["price"] if data else None
        except Exception:
            return None