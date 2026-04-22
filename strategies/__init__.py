from .base import BaseStrategy, Signal
from .trend_following import TrendFollowingStrategy
from .breakout import BreakoutStrategy
from .mean_reversion import MeanReversionStrategy
from .ichimoku import IchimokuStrategy
from .smart_money import SmartMoneyStrategy
from .quick_scalp import QuickMomentumStrategy, QuickReversalStrategy

ALL_STRATEGIES = [
    TrendFollowingStrategy(),
    BreakoutStrategy(),
    MeanReversionStrategy(),
    IchimokuStrategy(),
    SmartMoneyStrategy(),
]

QUICK_STRATEGIES = [
    QuickMomentumStrategy(),
    QuickReversalStrategy(),
]

__all__ = [
    "BaseStrategy", "Signal",
    "ALL_STRATEGIES", "QUICK_STRATEGIES",
    "TrendFollowingStrategy", "BreakoutStrategy",
    "MeanReversionStrategy", "IchimokuStrategy", "SmartMoneyStrategy",
    "QuickMomentumStrategy", "QuickReversalStrategy",
]
