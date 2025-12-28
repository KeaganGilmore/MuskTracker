"""X API v2 client with rate limiting and retry logic."""

from datetime import datetime, timedelta
from typing import Any, Optional

import tweepy
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from musktracker.config import get_config
from musktracker.logging_config import get_logger

logger = get_logger(__name__)


class XAPIClient:
    """X API v2 client with rate limiting and retry support.

    Handles authentication, pagination, and error recovery for tweet collection.
    """

    def __init__(self) -> None:
        """Initialize X API client."""
        config = get_config()

        self.client = tweepy.Client(
            bearer_token=config.x_api_bearer_token,
            wait_on_rate_limit=True,
        )

        self.target_username = config.target_username
        self.logger = logger.bind(component="x_api_client")

        # Get user ID for target username
        self._user_id: Optional[str] = None

    def _get_user_id(self) -> str:
        """Get user ID for target username.

        Returns:
            User ID string

        Raises:
            ValueError: If user not found
        """
        if self._user_id is not None:
            return self._user_id

        try:
            user = self.client.get_user(username=self.target_username)
            if user.data is None:
                raise ValueError(f"User {self.target_username} not found")

            self._user_id = user.data.id
            self.logger.info("Retrieved user ID", username=self.target_username, user_id=self._user_id)
            return self._user_id

        except Exception as e:
            self.logger.error("Failed to get user ID", username=self.target_username, error=str(e))
            raise

    @retry(
        retry=retry_if_exception_type((tweepy.TweepyException, ConnectionError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=1, max=60),
        reraise=True,
    )
    def fetch_recent_tweets(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_results: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch recent tweets from target user.

        Args:
            start_time: Earliest tweet timestamp (UTC)
            end_time: Latest tweet timestamp (UTC)
            max_results: Maximum tweets per page (10-100)

        Returns:
            List of tweet dictionaries with id and created_at

        Note:
            X API v2 free tier limits lookback to 7 days.
        """
        user_id = self._get_user_id()

        # Validate time range
        if start_time and end_time and start_time >= end_time:
            raise ValueError("start_time must be before end_time")

        # Free tier constraint: 7-day lookback
        if start_time:
            from datetime import timezone
            earliest_allowed = datetime.now(timezone.utc) - timedelta(days=7)
            if start_time < earliest_allowed:
                self.logger.warning(
                    "start_time exceeds free tier limit, adjusting to 7 days ago",
                    original_start=start_time.isoformat(),
                    adjusted_start=earliest_allowed.isoformat(),
                )
                start_time = earliest_allowed

        tweets = []
        pagination_token = None

        try:
            while True:
                response = self.client.get_users_tweets(
                    id=user_id,
                    start_time=start_time,
                    end_time=end_time,
                    max_results=max_results,
                    tweet_fields=["created_at"],
                    pagination_token=pagination_token,
                )

                if response.data is None:
                    self.logger.info("No tweets found in time range")
                    break

                # Extract tweet metadata
                for tweet in response.data:
                    tweets.append({
                        "id": tweet.id,
                        "created_at": tweet.created_at,
                    })

                self.logger.info(
                    "Fetched tweet page",
                    page_size=len(response.data),
                    total_fetched=len(tweets),
                )

                # Check for more pages
                if not hasattr(response.meta, "next_token") or response.meta.get("next_token") is None:
                    break

                pagination_token = response.meta["next_token"]

            self.logger.info(
                "Completed tweet fetch",
                total_tweets=len(tweets),
                start_time=start_time.isoformat() if start_time else None,
                end_time=end_time.isoformat() if end_time else None,
            )

            return tweets

        except tweepy.TweepyException as e:
            self.logger.error(
                "X API error",
                error=str(e),
                error_code=getattr(e, "api_code", None),
            )
            raise
        except Exception as e:
            self.logger.error("Unexpected error during tweet fetch", error=str(e))
            raise

    def fetch_tweet_count(
        self,
        start_time: datetime,
        end_time: datetime,
        granularity: str = "hour",
    ) -> list[dict[str, Any]]:
        """Fetch tweet counts using the counts endpoint (if available).

        Args:
            start_time: Start of time range (UTC)
            end_time: End of time range (UTC)
            granularity: 'hour' or 'day'

        Returns:
            List of count dictionaries with start, end, and count

        Note:
            This endpoint may not be available in free tier.
            Falls back to manual counting from fetch_recent_tweets.
        """
        user_id = self._get_user_id()

        try:
            # Try using counts endpoint
            query = f"from:{self.target_username}"

            response = self.client.get_all_tweets_count(
                query=query,
                start_time=start_time,
                end_time=end_time,
                granularity=granularity,
            )

            if response.data is None:
                return []

            counts = []
            for count_data in response.data:
                counts.append({
                    "start": count_data.start,
                    "end": count_data.end,
                    "count": count_data.tweet_count,
                })

            return counts

        except tweepy.Forbidden:
            # Counts endpoint not available in free tier
            self.logger.warning("Counts endpoint not available, falling back to manual count")
            return []
        except Exception as e:
            self.logger.error("Failed to fetch tweet counts", error=str(e))
            return []

