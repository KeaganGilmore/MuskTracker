"""GDELT API client for fetching events related to Elon Musk.

GDELT (Global Database of Events, Language, and Tone) is a free, open platform
for research and analysis of global society. This module uses GDELT's API to fetch
news events mentioning Elon Musk and related entities (Tesla, SpaceX, Twitter/X).
"""

import time
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import quote

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from musktracker.logging_config import get_logger

logger = get_logger(__name__)


class GDELTClient:
    """Client for GDELT API to fetch events and news mentions."""

    # GDELT API endpoints
    GEG_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
    TV_API_URL = "https://api.gdeltproject.org/api/v2/tv/tv"

    # Search terms for Elon Musk and related entities
    MUSK_SPECIFIC_TERMS = [
        "Elon Musk",
        "Tesla",
        "SpaceX",
        "Neuralink",
        "Boring Company",
        "Twitter Musk",
        "X Corp Musk",
    ]

    # General major event categories that Musk may react to
    GENERAL_EVENT_TERMS = [
        # Technology & Innovation
        "AI breakthrough",
        "artificial intelligence",
        "tech regulation",
        "cryptocurrency",
        "Bitcoin",
        "Dogecoin",

        # Space & Science
        "NASA announcement",
        "space exploration",
        "Mars mission",
        "rocket launch",

        # Politics & Policy (US & Global)
        "US President",
        "Federal Reserve",
        "inflation rate",
        "interest rates",
        "government shutdown",

        # Business & Markets
        "stock market crash",
        "economic crisis",
        "S&P 500",
        "tech stock",
        "IPO announcement",

        # Social & Cultural
        "free speech",
        "social media regulation",
        "misinformation",
        "content moderation",

        # Energy & Climate
        "climate change",
        "renewable energy",
        "oil prices",
        "electric vehicle",

        # Tech Industry
        "Silicon Valley",
        "tech layoffs",
        "Google",
        "Apple",
        "Microsoft",
        "Amazon",
        "Meta",
    ]

    def __init__(self):
        """Initialize GDELT client."""
        self.logger = logger.bind(component="gdelt_client")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MuskTracker/1.0 (Research Project)'
        })

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def _make_request(self, url: str, params: dict) -> requests.Response:
        """Make HTTP request with retry logic.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            Response object

        Raises:
            requests.RequestException: On request failure
        """
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            # GDELT rate limiting - be nice to the API
            time.sleep(1)

            return response
        except requests.RequestException as e:
            self.logger.error("GDELT API request failed", url=url, error=str(e))
            raise

    def fetch_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_records: int = 250,
        mode: str = "artlist",
        search_terms: Optional[List[str]] = None,
        event_type: str = "musk_specific",
    ) -> pd.DataFrame:
        """Fetch events from GDELT GEG API.

        Args:
            start_date: Start date for event search (UTC)
            end_date: End date for event search (UTC)
            max_records: Maximum number of records to return (default 250, max 250)
            mode: API mode - 'artlist' for article list or 'timeline' for timeline
            search_terms: Custom search terms, or None to use defaults
            event_type: Type of events - 'musk_specific', 'general', or 'both'

        Returns:
            DataFrame with event data
        """
        if search_terms is None:
            if event_type == "musk_specific":
                search_terms = self.MUSK_SPECIFIC_TERMS
            elif event_type == "general":
                search_terms = self.GENERAL_EVENT_TERMS
            elif event_type == "both":
                search_terms = self.MUSK_SPECIFIC_TERMS + self.GENERAL_EVENT_TERMS
            else:
                raise ValueError(f"Invalid event_type: {event_type}. Must be 'musk_specific', 'general', or 'both'")

        # GDELT accepts date format YYYYMMDDHHMMSS
        start_str = start_date.strftime("%Y%m%d%H%M%S")
        end_str = end_date.strftime("%Y%m%d%H%M%S")

        # Combine search terms with OR
        query = " OR ".join([f'"{term}"' for term in search_terms])

        self.logger.info(
            "Fetching GDELT events",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            event_type=event_type,
            query_terms=len(search_terms)
        )

        params = {
            "query": query,
            "mode": mode,
            "format": "json",
            "maxrecords": min(max_records, 250),  # GDELT max is 250
            "startdatetime": start_str,
            "enddatetime": end_str,
            "sort": "datedesc",
        }

        try:
            response = self._make_request(self.GEG_API_URL, params)
            data = response.json()

            if "articles" not in data:
                self.logger.warning("No articles found in GDELT response")
                return pd.DataFrame()

            df = pd.DataFrame(data["articles"])
            self.logger.info("Fetched GDELT events", count=len(df))

            return df

        except Exception as e:
            self.logger.error("Failed to fetch GDELT events", error=str(e))
            return pd.DataFrame()

    def fetch_tone_timeline(
        self,
        start_date: datetime,
        end_date: datetime,
        search_terms: Optional[List[str]] = None,
        event_type: str = "musk_specific",
    ) -> pd.DataFrame:
        """Fetch tone timeline from GDELT.

        This provides aggregated sentiment/tone data over time.

        Args:
            start_date: Start date (UTC)
            end_date: End date (UTC)
            search_terms: Custom search terms, or None to use defaults
            event_type: Type of events - 'musk_specific', 'general', or 'both'

        Returns:
            DataFrame with timeline data
        """
        if search_terms is None:
            if event_type == "musk_specific":
                search_terms = self.MUSK_SPECIFIC_TERMS
            elif event_type == "general":
                search_terms = self.GENERAL_EVENT_TERMS
            elif event_type == "both":
                search_terms = self.MUSK_SPECIFIC_TERMS + self.GENERAL_EVENT_TERMS
            else:
                raise ValueError(f"Invalid event_type: {event_type}")

        start_str = start_date.strftime("%Y%m%d%H%M%S")
        end_str = end_date.strftime("%Y%m%d%H%M%S")

        # Combine search terms with OR
        query = " OR ".join([f'"{term}"' for term in search_terms])

        self.logger.info("Fetching GDELT tone timeline", event_type=event_type)

        params = {
            "query": query,
            "mode": "timelinetone",
            "format": "json",
            "startdatetime": start_str,
            "enddatetime": end_str,
        }

        try:
            response = self._make_request(self.GEG_API_URL, params)
            data = response.json()

            if "timeline" not in data:
                self.logger.warning("No timeline data found")
                return pd.DataFrame()

            df = pd.DataFrame(data["timeline"])
            self.logger.info("Fetched tone timeline", points=len(df))

            return df

        except Exception as e:
            self.logger.error("Failed to fetch tone timeline", error=str(e))
            return pd.DataFrame()

    def extract_events_from_articles(
        self,
        articles_df: pd.DataFrame,
        tone_threshold: float = 5.0,
        intensity_threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """Extract significant events from article data.

        Groups articles by date and identifies significant events based on:
        - Volume of coverage (number of articles)
        - Tone/sentiment scores
        - Source diversity

        Args:
            articles_df: DataFrame with GDELT article data
            tone_threshold: Minimum absolute tone score to consider significant
            intensity_threshold: Minimum intensity score (0-1) to include

        Returns:
            List of event dictionaries
        """
        if articles_df.empty:
            return []

        events = []

        try:
            # Parse dates
            articles_df['date'] = pd.to_datetime(articles_df['seendate'], format='%Y%m%dT%H%M%SZ')

            # Group by day
            daily_groups = articles_df.groupby(articles_df['date'].dt.date)

            for date, group in daily_groups:
                # Calculate metrics
                article_count = len(group)

                # Extract tone if available
                avg_tone = 0.0
                if 'tone' in group.columns:
                    avg_tone = group['tone'].astype(float).mean()

                # Calculate intensity based on article volume
                # Normalize by expected baseline (adjust based on your data)
                baseline_articles_per_day = 10
                intensity = min(1.0, article_count / (baseline_articles_per_day * 3))

                # Also boost intensity if tone is extreme
                if abs(avg_tone) > tone_threshold:
                    intensity = min(1.0, intensity * 1.5)

                if intensity < intensity_threshold:
                    continue

                # Get representative title
                titles = group['title'].tolist() if 'title' in group.columns else []
                title = titles[0] if titles else f"Events on {date}"

                # Categorize based on title keywords
                category = self._categorize_event(title, group)

                event = {
                    "name": f"{title[:100]}..." if len(title) > 100 else title,
                    "date": date,
                    "intensity": round(intensity, 2),
                    "category": category,
                    "article_count": article_count,
                    "avg_tone": round(avg_tone, 2),
                    "sources": group['domain'].nunique() if 'domain' in group.columns else 1,
                }

                events.append(event)

            self.logger.info("Extracted events from articles", event_count=len(events))

        except Exception as e:
            self.logger.error("Failed to extract events", error=str(e))

        return events

    def _categorize_event(self, title: str, articles: pd.DataFrame) -> str:
        """Categorize an event based on keywords.

        Args:
            title: Event title
            articles: DataFrame of articles for this event

        Returns:
            Category string
        """
        title_lower = title.lower()

        # Check all article titles for better categorization
        all_text = " ".join(articles['title'].tolist() if 'title' in articles.columns else [])
        all_text_lower = all_text.lower()

        if any(word in all_text_lower for word in ['stock', 'market', 'shares', 'trading', 'ipo', 'earnings']):
            return "market"
        elif any(word in all_text_lower for word in ['sec', 'lawsuit', 'court', 'regulatory', 'legal']):
            return "regulatory"
        elif any(word in all_text_lower for word in ['launch', 'unveil', 'release', 'product', 'feature']):
            return "product"
        elif any(word in all_text_lower for word in ['acquisition', 'merger', 'deal', 'buy']):
            return "business"
        elif any(word in all_text_lower for word in ['tweet', 'twitter', 'social media', 'post']):
            return "social"
        else:
            return "general"

    def fetch_events_for_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        chunk_days: int = 30,
        event_type: str = "both",
    ) -> List[Dict[str, Any]]:
        """Fetch events for a date range, chunking into smaller requests.

        GDELT works best with shorter time ranges, so this splits long ranges
        into chunks.

        Args:
            start_date: Start date (UTC)
            end_date: End date (UTC)
            chunk_days: Number of days per request chunk
            event_type: Type of events - 'musk_specific', 'general', or 'both'

        Returns:
            List of event dictionaries
        """
        all_events = []
        current_start = start_date

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=chunk_days), end_date)

            self.logger.info(
                "Fetching chunk",
                start=current_start.date(),
                end=current_end.date(),
                event_type=event_type
            )

            # Fetch articles
            articles_df = self.fetch_events(current_start, current_end, event_type=event_type)

            if not articles_df.empty:
                # Extract events
                events = self.extract_events_from_articles(articles_df)
                all_events.extend(events)

            current_start = current_end

            # Be nice to the API
            time.sleep(2)

        self.logger.info("Completed date range fetch", total_events=len(all_events))
        return all_events

