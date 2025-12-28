"""Event enrichment CLI."""

import click
from datetime import datetime

from musktracker.enrich import EventEnricher
from musktracker.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


@click.group()
def enrich() -> None:
    """Manage exogenous events."""
    setup_logging()


@enrich.command()
@click.option("--name", required=True, help="Event name")
@click.option("--start", required=True, help="Event start time (ISO format)")
@click.option("--end", required=True, help="Event end time (ISO format)")
@click.option("--intensity", type=float, default=0.5, help="Event intensity (0.0-1.0)")
@click.option("--description", default=None, help="Event description")
@click.option("--category", default=None, help="Event category")
def add_event(
    name: str,
    start: str,
    end: str,
    intensity: float,
    description: str | None,
    category: str | None,
) -> None:
    """Add a new exogenous event.

    Example:
        python -m musktracker.cli.enrich add-event \\
            --name "Tesla Q4 Earnings" \\
            --start "2025-01-15T00:00:00Z" \\
            --end "2025-01-15T23:59:59Z" \\
            --intensity 0.8 \\
            --category "market"
    """
    try:
        event_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
        event_end = datetime.fromisoformat(end.replace("Z", "+00:00"))

        enricher = EventEnricher()
        event_id = enricher.add_event(
            name=name,
            event_start=event_start,
            event_end=event_end,
            intensity=intensity,
            description=description,
            category=category,
        )

        logger.info("Event added successfully", event_id=event_id)
        click.echo(f"Event added with ID: {event_id}")

    except Exception as e:
        logger.error("Failed to add event", error=str(e))
        raise click.ClickException(str(e))


if __name__ == "__main__":
    enrich()

