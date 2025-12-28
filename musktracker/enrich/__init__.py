"""Exogenous event enrichment module."""

from datetime import datetime, timezone
from typing import Optional

from musktracker.db.models import ExogenousEvent
from musktracker.db.session import get_db_session
from musktracker.logging_config import get_logger

logger = get_logger(__name__)


class EventEnricher:
    """Manages exogenous events for model enrichment."""

    def __init__(self) -> None:
        """Initialize event enricher."""
        self.logger = logger.bind(component="event_enricher")

    def add_event(
        self,
        name: str,
        event_start: datetime,
        event_end: datetime,
        intensity: float = 0.5,
        description: Optional[str] = None,
        category: Optional[str] = None,
        source: str = "manual",
    ) -> int:
        """Add a new exogenous event.

        Args:
            name: Event name
            event_start: Event start time (UTC)
            event_end: Event end time (UTC)
            intensity: Event intensity score (0.0 to 1.0)
            description: Optional event description
            category: Optional category (e.g., 'market', 'regulatory', 'product')
            source: Event source (default 'manual')

        Returns:
            Event ID

        Raises:
            ValueError: If intensity out of range or times invalid
        """
        # Validate inputs
        if not 0.0 <= intensity <= 1.0:
            raise ValueError(f"Intensity must be between 0.0 and 1.0, got {intensity}")

        if event_start >= event_end:
            raise ValueError("event_start must be before event_end")

        # Ensure UTC timezone
        if event_start.tzinfo is None:
            event_start = event_start.replace(tzinfo=timezone.utc)
        if event_end.tzinfo is None:
            event_end = event_end.replace(tzinfo=timezone.utc)

        with get_db_session() as session:
            event = ExogenousEvent(
                name=name,
                description=description,
                category=category,
                event_start=event_start,
                event_end=event_end,
                intensity=intensity,
                source=source,
                created_at=datetime.now(timezone.utc),
            )

            session.add(event)
            session.flush()

            event_id = event.id

            self.logger.info(
                "Added exogenous event",
                event_id=event_id,
                name=name,
                start=event_start.isoformat(),
                end=event_end.isoformat(),
                intensity=intensity,
            )

            return event_id

    def get_events_in_window(
        self,
        window_start: datetime,
        window_end: datetime,
    ) -> list[ExogenousEvent]:
        """Get all events overlapping with time window.

        Args:
            window_start: Window start time (UTC)
            window_end: Window end time (UTC)

        Returns:
            List of ExogenousEvent objects
        """
        with get_db_session() as session:
            # Events overlap if:
            # event_start < window_end AND event_end > window_start
            events = session.query(ExogenousEvent).filter(
                ExogenousEvent.event_start < window_end,
                ExogenousEvent.event_end > window_start,
            ).all()

            # Detach from session
            session.expunge_all()

            return events

    def compute_window_intensity(
        self,
        window_start: datetime,
        window_end: datetime,
    ) -> tuple[float, int]:
        """Compute aggregate event intensity for a time window.

        Args:
            window_start: Window start time (UTC)
            window_end: Window end time (UTC)

        Returns:
            Tuple of (max_intensity, event_count)
        """
        events = self.get_events_in_window(window_start, window_end)

        if not events:
            return 0.0, 0

        # Use max intensity across overlapping events
        max_intensity = max(event.intensity for event in events)

        return max_intensity, len(events)

