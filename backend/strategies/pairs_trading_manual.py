from collections import deque
import sys
import os
import time
import math

# Add parent directories to path so 'project' module can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from project.backend.core.event import Signal, SignalType

class PairsTradingStrategy:
    def __init__(
        self,
        beta,
        lookback=60,
        entry_z=2.0,
        exit_z=0.5
    ):
        self.beta = beta
        self.lookback = lookback
        self.entry_z = entry_z
        self.exit_z = exit_z
        self.spreads = deque(maxlen=lookback)

        self.in_position = False

    def on_price(self, symbol_y, price_y, symbol_x, price_x):
        now = time.time()

        spread = price_y - self.beta * price_x
        self.spreads.append(spread)

        if len(self.spreads) < self.lookback:
            return (
                Signal(symbol_y, SignalType.HOLD, now),
                Signal(symbol_x, SignalType.HOLD, now),
            )

        mean = sum(self.spreads) / self.lookback
        variance = sum((s - mean) ** 2 for s in self.spreads) / self.lookback
        std = math.sqrt(variance)

        if std == 0:
            return (
                Signal(symbol_y, SignalType.HOLD, now),
                Signal(symbol_x, SignalType.HOLD, now),
            )

        zscore = (spread - mean) / std

        y_action = SignalType.HOLD
        x_action = SignalType.HOLD

        if not self.in_position:
            if zscore > self.entry_z:
                y_action = SignalType.SELL
                x_action = SignalType.BUY
                self.in_position = True

            elif zscore < -self.entry_z:
                y_action = SignalType.BUY
                x_action = SignalType.SELL
                self.in_position = True

        else:
            if abs(zscore) < self.exit_z:
                y_action = SignalType.EXIT
                x_action = SignalType.EXIT
                self.in_position = False

        return (
            Signal(symbol_y, y_action, now),
            Signal(symbol_x, x_action, now),
        )
