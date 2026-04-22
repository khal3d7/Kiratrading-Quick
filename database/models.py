from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text, Boolean,
    ForeignKey, JSON, Index, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .db import Base


class Coin(Base):
    __tablename__ = "coins"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), unique=True, nullable=False, index=True)
    name = Column(String(64))
    market_cap = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PriceData(Base):
    __tablename__ = "price_data"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    timeframe = Column(String(8), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_price_point"),
        Index("ix_price_lookup", "symbol", "timeframe", "timestamp"),
    )


class Analysis(Base):
    __tablename__ = "analyses"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    timeframe = Column(String(8), default="1d")
    indicators_json = Column(JSON, nullable=False)
    support_resistance_json = Column(JSON, nullable=False)
    market_structure = Column(String(16))
    summary_text = Column(Text)


class Signal(Base):
    __tablename__ = "signals"
    id = Column(Integer, primary_key=True)
    symbol = Column(String(32), nullable=False, index=True)
    strategy = Column(String(64), nullable=False)
    direction = Column(String(8), nullable=False)  # LONG / SHORT
    kind = Column(String(16), default="standard", index=True)  # standard | quick
    entry = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=False)
    take_profit_3 = Column(Float, nullable=False)
    confidence = Column(Float, default=0.0)
    risk_reward = Column(Float, default=0.0)
    reasoning = Column(Text)
    status = Column(String(16), default="new")  # new, opened, expired
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    trades = relationship("Trade", back_populates="signal")


class Trade(Base):
    __tablename__ = "trades"
    id = Column(Integer, primary_key=True)
    signal_id = Column(Integer, ForeignKey("signals.id"))
    symbol = Column(String(32), nullable=False, index=True)
    direction = Column(String(8), nullable=False)
    kind = Column(String(16), default="standard", index=True)  # standard | quick
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=False)
    take_profit_1 = Column(Float, nullable=False)
    take_profit_2 = Column(Float, nullable=False)
    take_profit_3 = Column(Float, nullable=False)
    position_size = Column(Float, nullable=False)
    risk_usd = Column(Float, default=0.0)
    status = Column(String(16), default="open", index=True)  # open, closed
    result = Column(String(16))  # win, loss, breakeven, expired
    tp1_hit = Column(Boolean, default=False)
    tp2_hit = Column(Boolean, default=False)
    tp3_hit = Column(Boolean, default=False)
    exit_price = Column(Float)
    pnl_percent = Column(Float, default=0.0)
    pnl_usd = Column(Float, default=0.0)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime)
    notes = Column(Text)

    signal = relationship("Signal", back_populates="trades")


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True)
    period = Column(String(16), nullable=False)  # weekly, monthly
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    summary = Column(Text, nullable=False)
    stats_json = Column(JSON)
