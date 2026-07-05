from collections import deque
from project.backend.core.event import Signal, SignalType
import time


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
        

        if self.prev_fast is not None:
            if self.prev_fast <= self.prev_slow and sma_fast > sma_slow:
                action = SignalType.BUY
            elif self.prev_fast >= self.prev_slow and sma_fast < sma_slow:
                action = SignalType.SELL

        self.prev_fast = sma_fast
        self.prev_slow = sma_slow

        return Signal(symbol, action, time.time())
