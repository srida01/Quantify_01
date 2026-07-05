import sys
import os

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import MarketEvent


class SimpleMarketNormalizer:
    def normalize(self, event: MarketEvent) -> MarketEvent | None:
        if event.price <= 0:
            return None
        return event
