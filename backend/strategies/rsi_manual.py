from collections import deque
import sys
import os
import time

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import Signal, SignalType

class RSIMomentumStrategy:
    def __init__(self, rsi_period=14, rsi_lower=30, rsi_upper=70):
        self.period = rsi_period
        self.rsi_lower = rsi_lower
        self.rsi_upper = rsi_upper
        self.prices = deque(maxlen=rsi_period + 1)
        self.avg_gain = None
        self.avg_loss = None
        self.prev_price = None

    def on_price(self, symbol, price):
        now = time.time()
        self.prices.append(price)

        if len(self.prices) < self.period + 1:
            self.prev_price = price
            return Signal(symbol, SignalType.HOLD, now)

        delta = price - self.prices[-2]
        gain = max(delta, 0)
        loss = max(-delta, 0)

        if self.avg_gain is None:
            gains = []
            losses = []
            for i in range(1, len(self.prices)):
                diff = self.prices[i] - self.prices[i - 1]
                gains.append(max(diff, 0))
                losses.append(max(-diff, 0))

            self.avg_gain = sum(gains) / self.period
            self.avg_loss = sum(losses) / self.period
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period

        if self.avg_loss == 0:
            rsi = 100
        else:
            rs = self.avg_gain / self.avg_loss
            rsi = 100 - (100 / (1 + rs))

        momentum = price - self.prev_price if self.prev_price is not None else 0
        self.prev_price = price

        action = SignalType.HOLD

        if momentum > 0 and rsi > self.rsi_lower:
            action = SignalType.BUY
        elif momentum < 0 or rsi > self.rsi_upper:
            action = SignalType.SELL

        return Signal(symbol, action, now)
