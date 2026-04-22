from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


@dataclass
class Signal:
    symbol: str
    strategy: str
    direction: str            # LONG or SHORT
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confidence: float         # 0..100
    reasoning: List[str] = field(default_factory=list)

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry - self.stop_loss)
        reward = abs(self.take_profit_2 - self.entry)
        return round(reward / risk, 2) if risk > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "direction": self.direction,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "take_profit_1": self.take_profit_1,
            "take_profit_2": self.take_profit_2,
            "take_profit_3": self.take_profit_3,
            "confidence": self.confidence,
            "risk_reward": self.risk_reward,
            "reasoning": self.reasoning,
        }


class BaseStrategy(ABC):
    name: str = "base"

    @abstractmethod
    def evaluate(self, analysis: Dict[str, Any]) -> Optional[Signal]:
        """Return a Signal if conditions are met, otherwise None."""
        raise NotImplementedError
