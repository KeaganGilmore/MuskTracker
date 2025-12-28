"""Database models for MuskTracker."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class RawTweet(Base):
    """Raw tweet metadata from X API."""

    __tablename__ = "raw_tweets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tweet_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    author_id: Mapped[str] = mapped_column(String(32), nullable=False)

    # Metadata
    is_retweet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_quote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Source and ingestion tracking
    source: Mapped[str] = mapped_column(String(64), default="api", nullable=False)
    ingest_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Optional metadata (can be null)
    language: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    possibly_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<RawTweet(tweet_id={self.tweet_id}, created_at={self.created_at})>"


class TimeBucket(Base):
    """Time-aggregated tweet counts."""

    __tablename__ = "time_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    bucket_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granularity: Mapped[str] = mapped_column(String(16), nullable=False)  # 'hourly' or 'daily'

    # Aggregated metrics
    tweet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retweet_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reply_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quote_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Computation tracking
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("bucket_start", "granularity", name="uq_bucket_granularity"),
    )

    def __repr__(self) -> str:
        return f"<TimeBucket(start={self.bucket_start}, count={self.tweet_count})>"


class ExogenousEvent(Base):
    """Exogenous events for model enrichment."""

    __tablename__ = "exogenous_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    event_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    event_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Event metadata
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intensity: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # Source tracking
    source: Mapped[str] = mapped_column(String(64), default="manual", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<ExogenousEvent(name={self.name}, start={self.event_start})>"


class Feature(Base):
    """Computed features for modeling."""

    __tablename__ = "features"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    granularity: Mapped[str] = mapped_column(String(16), nullable=False)

    # Lagged features
    count_lag_1: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_lag_2: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_lag_3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_lag_24: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_lag_168: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # 1 week

    # Rolling statistics
    count_rolling_6h_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_rolling_24h_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_rolling_7d_mean: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_rolling_6h_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    count_rolling_24h_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Calendar features
    hour_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Event features
    event_intensity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Computation tracking
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("timestamp", "granularity", name="uq_feature_timestamp_granularity"),
    )

    def __repr__(self) -> str:
        return f"<Feature(timestamp={self.timestamp}, granularity={self.granularity})>"

