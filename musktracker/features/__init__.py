"""Feature engineering for time-series modeling."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import func, select

from musktracker.db.models import Feature, RawTweet, TimeBucket
from musktracker.db.session import get_db_session
from musktracker.enrich import EventEnricher
from musktracker.logging_config import get_logger

logger = get_logger(__name__)


class FeatureEngineer:
    """Computes features for statistical modeling."""

    def __init__(self) -> None:
        """Initialize feature engineer."""
        self.event_enricher = EventEnricher()
        self.logger = logger.bind(component="feature_engineer")

    def compute_time_buckets(
        self,
        start_time: datetime,
        end_time: datetime,
        granularity: str = "hourly",
    ) -> int:
        """Compute time-bucketed aggregates.

        Args:
            start_time: Start of time range (UTC)
            end_time: End of time range (UTC)
            granularity: 'hourly' or 'daily'

        Returns:
            Number of buckets created
        """
        if granularity not in ("hourly", "daily"):
            raise ValueError(f"Invalid granularity: {granularity}")

        # Determine bucket size
        delta = timedelta(hours=1) if granularity == "hourly" else timedelta(days=1)

        bucket_count = 0
        current = start_time

        with get_db_session() as session:
            while current < end_time:
                bucket_end = current + delta

                # Count tweets in bucket
                count = session.execute(
                    select(func.count(RawTweet.id))
                    .where(
                        RawTweet.created_at >= current,
                        RawTweet.created_at < bucket_end,
                        RawTweet.is_deleted == False,
                    )
                ).scalar_one()

                # Check if bucket already exists
                existing = session.execute(
                    select(TimeBucket)
                    .where(
                        TimeBucket.bucket_start == current,
                        TimeBucket.granularity == granularity,
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing bucket
                    existing.tweet_count = count
                    existing.computed_at = datetime.now(timezone.utc)
                else:
                    # Create new bucket
                    bucket = TimeBucket(
                        bucket_start=current,
                        bucket_end=bucket_end,
                        granularity=granularity,
                        tweet_count=count,
                        computed_at=datetime.now(timezone.utc),
                    )
                    session.add(bucket)

                bucket_count += 1
                current = bucket_end

        self.logger.info(
            "Computed time buckets",
            granularity=granularity,
            bucket_count=bucket_count,
        )

        return bucket_count

    def get_bucket_counts(
        self,
        start_time: datetime,
        end_time: datetime,
        granularity: str = "hourly",
    ) -> pd.DataFrame:
        """Get time-bucketed counts as DataFrame.

        Args:
            start_time: Start of time range (UTC)
            end_time: End of time range (UTC)
            granularity: 'hourly' or 'daily'

        Returns:
            DataFrame with columns: timestamp, count
        """
        with get_db_session() as session:
            buckets = session.execute(
                select(TimeBucket)
                .where(
                    TimeBucket.bucket_start >= start_time,
                    TimeBucket.bucket_start < end_time,
                    TimeBucket.granularity == granularity,
                )
                .order_by(TimeBucket.bucket_start)
            ).scalars().all()

            if not buckets:
                return pd.DataFrame(columns=["timestamp", "count"])

            df = pd.DataFrame([
                {
                    "timestamp": bucket.bucket_start,
                    "count": bucket.tweet_count,
                }
                for bucket in buckets
            ])

            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df

    def compute_features(
        self,
        reference_time: datetime,
        lookback_days: int = 14,
    ) -> Optional[int]:
        """Compute features for a reference time point.

        Args:
            reference_time: Time point for feature computation (UTC)
            lookback_days: Days of historical data to use

        Returns:
            Feature ID, or None if insufficient data
        """
        # Ensure hourly buckets exist
        lookback_start = reference_time - timedelta(days=lookback_days)
        self.compute_time_buckets(lookback_start, reference_time, granularity="hourly")

        # Get hourly counts
        df = self.get_bucket_counts(lookback_start, reference_time, granularity="hourly")

        if df.empty:
            self.logger.warning("No data available for feature computation", time=reference_time.isoformat())
            return None

        # Set timestamp as index
        df = df.set_index("timestamp").sort_index()

        # Compute lagged features
        lag_1h = self._get_lag_count(df, reference_time, hours=1)
        lag_6h = self._get_lag_count(df, reference_time, hours=6)
        lag_12h = self._get_lag_count(df, reference_time, hours=12)
        lag_24h = self._get_lag_count(df, reference_time, hours=24)
        lag_7d = self._get_lag_count(df, reference_time, hours=24 * 7)

        # Compute rolling aggregates
        rolling_mean_24h = self._get_rolling_mean(df, reference_time, hours=24)
        rolling_std_24h = self._get_rolling_std(df, reference_time, hours=24)
        rolling_mean_7d = self._get_rolling_mean(df, reference_time, hours=24 * 7)
        rolling_std_7d = self._get_rolling_std(df, reference_time, hours=24 * 7)

        # Calendar features
        hour_of_day = reference_time.hour
        day_of_week = reference_time.weekday()
        is_weekend = day_of_week >= 5

        # Event features
        event_window_start = reference_time - timedelta(hours=24)
        event_intensity, events_count = self.event_enricher.compute_window_intensity(
            event_window_start, reference_time
        )

        # Store feature
        with get_db_session() as session:
            # Check if feature exists
            existing = session.execute(
                select(Feature).where(Feature.reference_time == reference_time)
            ).scalar_one_or_none()

            if existing:
                # Update existing
                existing.lag_1h = lag_1h
                existing.lag_6h = lag_6h
                existing.lag_12h = lag_12h
                existing.lag_24h = lag_24h
                existing.lag_7d = lag_7d
                existing.rolling_mean_24h = rolling_mean_24h
                existing.rolling_std_24h = rolling_std_24h
                existing.rolling_mean_7d = rolling_mean_7d
                existing.rolling_std_7d = rolling_std_7d
                existing.hour_of_day = hour_of_day
                existing.day_of_week = day_of_week
                existing.is_weekend = is_weekend
                existing.event_intensity = event_intensity
                existing.events_in_window = events_count
                existing.computed_at = datetime.now(timezone.utc)
                feature_id = existing.id
            else:
                # Create new
                feature = Feature(
                    reference_time=reference_time,
                    lag_1h=lag_1h,
                    lag_6h=lag_6h,
                    lag_12h=lag_12h,
                    lag_24h=lag_24h,
                    lag_7d=lag_7d,
                    rolling_mean_24h=rolling_mean_24h,
                    rolling_std_24h=rolling_std_24h,
                    rolling_mean_7d=rolling_mean_7d,
                    rolling_std_7d=rolling_std_7d,
                    hour_of_day=hour_of_day,
                    day_of_week=day_of_week,
                    is_weekend=is_weekend,
                    event_intensity=event_intensity,
                    events_in_window=events_count,
                    computed_at=datetime.now(timezone.utc),
                )
                session.add(feature)
                session.flush()
                feature_id = feature.id

        return feature_id

    def _get_lag_count(self, df: pd.DataFrame, ref_time: datetime, hours: int) -> Optional[int]:
        """Get count at lag offset."""
        lag_time = ref_time - timedelta(hours=hours)
        try:
            return int(df.loc[lag_time, "count"])
        except KeyError:
            return None

    def _get_rolling_mean(self, df: pd.DataFrame, ref_time: datetime, hours: int) -> Optional[float]:
        """Get rolling mean."""
        window_start = ref_time - timedelta(hours=hours)
        window_data = df[(df.index >= window_start) & (df.index < ref_time)]
        if window_data.empty:
            return None
        return float(window_data["count"].mean())

    def _get_rolling_std(self, df: pd.DataFrame, ref_time: datetime, hours: int) -> Optional[float]:
        """Get rolling standard deviation."""
        window_start = ref_time - timedelta(hours=hours)
        window_data = df[(df.index >= window_start) & (df.index < ref_time)]
        if window_data.empty or len(window_data) < 2:
            return None
        return float(window_data["count"].std())

    def compute_features_bulk(
        self,
        start_time: datetime,
        end_time: datetime,
        granularity_hours: int = 1,
    ) -> int:
        """Compute features for multiple time points.

        Args:
            start_time: Start of time range (UTC)
            end_time: End of time range (UTC)
            granularity_hours: Hours between feature computations

        Returns:
            Number of features computed
        """
        count = 0
        current = start_time
        delta = timedelta(hours=granularity_hours)

        while current <= end_time:
            feature_id = self.compute_features(current)
            if feature_id:
                count += 1
            current += delta

        self.logger.info("Computed bulk features", feature_count=count)
        return count

