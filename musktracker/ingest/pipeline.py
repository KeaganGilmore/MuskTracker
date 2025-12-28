"""Tweet ingestion pipeline with idempotency."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from musktracker.db.models import RawTweet
from musktracker.db.session import get_db_session
from musktracker.ingest.x_client import XAPIClient
from musktracker.logging_config import get_logger

logger = get_logger(__name__)


class TweetIngestor:
    """Idempotent tweet ingestion pipeline.

    Fetches tweets from X API and stores in database, handling duplicates gracefully.
    """

    def __init__(self) -> None:
        """Initialize tweet ingestor."""
        self.client = XAPIClient()
        self.logger = logger.bind(component="tweet_ingestor")

    def get_last_ingested_time(self) -> Optional[datetime]:
        """Get timestamp of most recently ingested tweet.

        Returns:
            Last tweet created_at timestamp, or None if no tweets
        """
        with get_db_session() as session:
            stmt = (
                select(RawTweet.created_at)
                .where(RawTweet.is_deleted == False)
                .order_by(RawTweet.created_at.desc())
                .limit(1)
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result:
                self.logger.info("Found last ingested tweet", timestamp=result.isoformat())

            return result

    def ingest_tweets(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        """Ingest tweets from X API with idempotent handling.

        Args:
            start_time: Earliest tweet timestamp (UTC). If None, uses last ingested time.
            end_time: Latest tweet timestamp (UTC). If None, uses current time.

        Returns:
            Number of new tweets ingested
        """
        # Set default times
        if end_time is None:
            end_time = datetime.now(timezone.utc)

        if start_time is None:
            last_time = self.get_last_ingested_time()
            if last_time:
                # Start from 1 minute after last tweet to avoid overlap
                start_time = last_time + timedelta(minutes=1)
            else:
                # Default to 7 days ago (API limit)
                start_time = end_time - timedelta(days=7)

        # Ensure UTC timezone
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        self.logger.info(
            "Starting tweet ingestion",
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
        )

        # Fetch tweets from API
        tweets = self.client.fetch_recent_tweets(
            start_time=start_time,
            end_time=end_time,
        )

        if not tweets:
            self.logger.info("No new tweets to ingest")
            return 0

        # Store tweets in database
        new_count = 0
        duplicate_count = 0

        with get_db_session() as session:
            for tweet_data in tweets:
                tweet_id = str(tweet_data["id"])

                # Check if tweet already exists
                existing = session.execute(
                    select(RawTweet).where(RawTweet.tweet_id == tweet_id)
                ).scalar_one_or_none()

                if existing:
                    duplicate_count += 1
                    continue

                # Create new tweet record
                tweet = RawTweet(
                    tweet_id=tweet_id,
                    created_at=tweet_data["created_at"],
                    author_id=tweet_data.get("author_id", "44196397"),
                    is_retweet=tweet_data.get("is_retweet", False),
                    is_reply=tweet_data.get("is_reply", False),
                    is_quote=tweet_data.get("is_quote", False),
                    language=tweet_data.get("language"),
                    possibly_sensitive=tweet_data.get("possibly_sensitive", False),
                    source="x_api_v2",
                    ingest_time=datetime.now(timezone.utc),
                    is_deleted=False,
                )

                session.add(tweet)
                new_count += 1

        self.logger.info(
            "Completed tweet ingestion",
            new_tweets=new_count,
            duplicates=duplicate_count,
            total_fetched=len(tweets),
        )

        return new_count

    def backfill(self, days: int = 7) -> int:
        """Backfill tweets from the past N days.

        Args:
            days: Number of days to backfill (max 7 for free tier)

        Returns:
            Number of new tweets ingested
        """
        if days > 7:
            self.logger.warning("Free tier limited to 7 days, adjusting", requested=days, actual=7)
            days = 7

        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        self.logger.info("Starting backfill", days=days)

        return self.ingest_tweets(start_time=start_time, end_time=end_time)

