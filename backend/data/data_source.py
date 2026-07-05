import random
import time
import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import MarketEvent


class MockMarketDataSource:
    def __init__(self, symbol: str, start_price: float):
        self.symbol = symbol
        self.price = start_price

    def get_next_event(self) -> MarketEvent:
        self.price += random.uniform(-0.5, 0.5)
        return MarketEvent(
            symbol=self.symbol,
            price=round(self.price, 2),
            timestamp=time.time()
        )
