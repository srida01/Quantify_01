from dataclasses import dataclass
from enum import Enum
import time


@dataclass
class MarketEvent:
    symbol: str
    price: float
    timestamp: float


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class Signal:
    symbol: str
    action: SignalType
    timestamp: float
