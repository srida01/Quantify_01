import time
import yfinance as yf
import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import MarketEvent


class LiveMarketDataSource:
    def __init__(self, symbol: str, poll_interval: int = 5):
        self.symbol = symbol
        self.poll_interval = poll_interval
        self.last_price = None

    def get_next_event(self) -> MarketEvent:

        ticker = yf.Ticker(self.symbol)
        data = ticker.history(period="1d", interval="1m")

        if data.empty:
            raise RuntimeError(f"No live data available for {self.symbol}")

        price = float(data["Close"].iloc[-1])
        if self.last_price is not None and price == self.last_price:
            time.sleep(self.poll_interval)
            return None

        self.last_price = price

        time.sleep(self.poll_interval)

        return MarketEvent(
            symbol=self.symbol,
            price=round(price, 2),
            timestamp=time.time()
        )
