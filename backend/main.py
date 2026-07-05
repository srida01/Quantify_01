import sys
import os
import time

# Add parent directory to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from project.backend.data.data_source import MockMarketDataSource
from project.backend.core.normalizer import SimpleMarketNormalizer
from project.backend.core.dispatcher import EventDispatcher
from project.backend.strategies.sma_manual import SMAStrategy
from project.backend.execution.paper_broker import PaperBroker
from project.backend.strategies.rsi_manual import RSIMomentumStrategy
from project.backend.strategies.pairs_trading_manual import PairsTradingStrategy
from project.backend.data.live_data_polling import LiveMarketDataSource
import time


def main():
    # source = MockMarketDataSource("AAPL", 150.0)
    source = LiveMarketDataSource("AAPL", poll_interval=5)
    normalizer = SimpleMarketNormalizer()
    strategy = SMAStrategy(3, 5)
    # strategy = RSIMomentumStrategy(rsi_period=14, rsi_lower=30, rsi_upper=70)
    broker = PaperBroker()

    def handle_event(event):
        signal = strategy.on_price(event.symbol, event.price)
        print(f"{signal.symbol} {signal.action.value}")
        broker.execute(signal)

    dispatcher = EventDispatcher(handle_event)

    while True:
        raw_event = source.get_next_event()

        if raw_event is None:
            print("No update from market feed")
            continue

        print(
            f"symbol={raw_event.symbol}, "
            f"price={raw_event.price}, "
            f"ts={raw_event.timestamp}"
        )

        event = normalizer.normalize(raw_event)

        if event is None:
            print("Event rejected")
            continue

        print(
            f"symbol={event.symbol}, "
            f"price={event.price}, "
            f"ts={event.timestamp}"
        )

        dispatcher.dispatch(event)


if __name__ == "__main__":
    main()
