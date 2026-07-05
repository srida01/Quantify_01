from collections import deque
import sys
import os
import time

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import Signal, SignalType


class SMAStrategy:
    def __init__(self, fast=10, slow=20):
        self.fast = fast
        self.slow = slow

        self.prices = deque(maxlen=slow)

        self.prev_fast = None
        self.prev_slow = None

    def on_price(self, symbol, price):
        self.prices.append(price)

        if len(self.prices) < self.slow:
            return Signal(symbol, SignalType.HOLD, time.time())

        sma_fast = sum(list(self.prices)[-self.fast:]) / self.fast
        sma_slow = sum(self.prices) / self.slow

        action = SignalType.HOLD
        print(
            f"[SMA DEBUG] price={price:.2f} "
            f"fast_sma={sma_fast:.4f} "
            f"slow_sma={sma_slow:.4f} "
            f"prev_fast={self.prev_fast} "
            f"prev_slow={self.prev_slow}"
        )


        if self.prev_fast is not None and self.prev_slow is not None:
            if self.prev_fast <= self.prev_slow and sma_fast > sma_slow:
                action = SignalType.BUY
            elif self.prev_fast >= self.prev_slow and sma_fast < sma_slow:
                action = SignalType.SELL

        self.prev_fast = sma_fast
        self.prev_slow = sma_slow
        print(f"[SMA SIGNAL] {symbol} → {action.value}")
        return Signal(symbol, action, time.time())
