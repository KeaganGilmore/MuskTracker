"""Fetch events from GDELT and add them to the database.

This CLI command fetches both Musk-specific events and general major events
from GDELT that may correlate with tweet volume changes.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import click
import pandas as pd

from musktracker.db.models import RawTweet
from musktracker.db.session import get_db_session
from musktracker.enrich import EventEnricher
from musktracker.enrich.gdelt_client import GDELTClient
from musktracker.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def get_tweet_date_range():
    """Get the date range of tweets in the database."""
    with get_db_session() as session:
        from sqlalchemy import func, select
        result = session.execute(
            select(
                func.min(RawTweet.created_at).label('min_date'),
                func.max(RawTweet.created_at).label('max_date')
            )
        ).first()

        return result.min_date, result.max_date


@click.command()
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD). Defaults to earliest tweet date."
)
@click.option(
    "--end-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD). Defaults to latest tweet date."
)
@click.option(
    "--event-type",
    type=click.Choice(["musk_specific", "general", "both"]),
    default="both",
    help="Type of events to fetch"
)
@click.option(
    "--chunk-days",
    type=int,
    default=30,
    help="Days per request chunk (GDELT works better with smaller chunks)"
)
@click.option(
    "--intensity-threshold",
    type=float,
    default=0.5,
    help="Minimum intensity (0-1) to include events"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Fetch events but don't add to database"
)
@click.option(
    "--export-csv",
    type=click.Path(path_type=Path),
    help="Export events to CSV file"
)
def main(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    event_type: str,
    chunk_days: int,
    intensity_threshold: float,
    dry_run: bool,
    export_csv: Optional[Path]
):
    """Fetch events from GDELT and add them to the database.

    This command fetches events from GDELT (Global Database of Events, Language, and Tone)
    that may correlate with Elon Musk's tweeting patterns:

    \b
    - Musk-specific: Tesla, SpaceX, Twitter/X, Neuralink, etc.
    - General: Major world events (politics, markets, tech, climate, etc.)
    - Both: All of the above

    The events are analyzed for significance based on article volume, tone,
    and source diversity, then added to the database for model enrichment.

    Examples:
        # Fetch last 90 days of both Musk and general events
        python -m musktracker.cli.fetch-gdelt --end-date 2024-12-28 --chunk-days 30

        # Fetch only Musk-specific events
        python -m musktracker.cli.fetch-gdelt --event-type musk_specific

        # Preview without adding to database
        python -m musktracker.cli.fetch-gdelt --dry-run --export-csv events.csv
    """
    setup_logging()

    click.echo("\n" + "=" * 80)
    click.echo("GDELT EVENT FETCHER")
    click.echo("=" * 80)

    # Get date range from tweet data if not specified
    if start_date is None or end_date is None:
        min_tweet_date, max_tweet_date = get_tweet_date_range()

        if not start_date:
            # Default to last 90 days from latest tweet
            start_date = (max_tweet_date - timedelta(days=90)) if max_tweet_date else datetime.now(timezone.utc) - timedelta(days=90)

        if not end_date:
            end_date = max_tweet_date if max_tweet_date else datetime.now(timezone.utc)

        click.echo(f"\nUsing tweet date range:")
        click.echo(f"  Start: {start_date.date()}")
        click.echo(f"  End: {end_date.date()}")

    # Ensure timezone
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    click.echo(f"\nEvent Type: {event_type}")
    click.echo(f"Intensity Threshold: {intensity_threshold}")
    click.echo(f"Chunk Days: {chunk_days}")

    if dry_run:
        click.echo("\n⚠ DRY RUN MODE - Events will NOT be added to database\n")

    # Initialize GDELT client
    gdelt = GDELTClient()

    # Fetch events
    click.echo(f"\nFetching events from GDELT...")
    click.echo(f"This may take several minutes depending on date range...\n")

    try:
        with click.progressbar(
            length=100,
            label="Fetching GDELT data"
        ) as bar:
            events = gdelt.fetch_events_for_date_range(
                start_date=start_date,
                end_date=end_date,
                chunk_days=chunk_days,
                event_type=event_type
            )
            bar.update(100)

        if not events:
            click.echo("\n⚠ No events found matching criteria.")
            return

        # Filter by intensity
        filtered_events = [e for e in events if e["intensity"] >= intensity_threshold]

        click.echo(f"\n✓ Found {len(events)} events")
        click.echo(f"  After filtering (intensity >= {intensity_threshold}): {len(filtered_events)}")

        if not filtered_events:
            click.echo("\n⚠ No events passed intensity threshold.")
            return

        # Export to CSV if requested
        if export_csv:
            df = pd.DataFrame(filtered_events)
            df.to_csv(export_csv, index=False)
            click.echo(f"\n✓ Exported to: {export_csv}")

        # Display sample events
        click.echo("\n" + "=" * 80)
        click.echo("SAMPLE EVENTS (Top 10 by intensity)")
        click.echo("=" * 80)

        sorted_events = sorted(filtered_events, key=lambda x: x["intensity"], reverse=True)[:10]
        for i, event in enumerate(sorted_events, 1):
            click.echo(f"\n{i}. {event['name']}")
            click.echo(f"   Date: {event['date']} | Category: {event['category']}")
            click.echo(f"   Intensity: {event['intensity']:.2f} | Articles: {event['article_count']} | Tone: {event['avg_tone']:.2f}")

        # Add to database
        if not dry_run:
            click.echo("\n" + "=" * 80)
            click.echo("ADDING EVENTS TO DATABASE")
            click.echo("=" * 80)

            enricher = EventEnricher()
            added = 0
            duplicates = 0
            errors = 0

            with click.progressbar(
                filtered_events,
                label="Adding events",
                show_percent=True
            ) as bar:
                for event in bar:
                    try:
                        # Convert date to datetime
                        event_date = datetime.combine(
                            event['date'],
                            datetime.min.time()
                        ).replace(tzinfo=timezone.utc)

                        event_id = enricher.add_event(
                            name=event['name'],
                            event_start=event_date,
                            event_end=event_date + timedelta(hours=23, minutes=59, seconds=59),
                            intensity=event['intensity'],
                            category=event['category'],
                            description=f"GDELT: {event['article_count']} articles, avg tone: {event['avg_tone']:.2f}",
                            source="gdelt"
                        )
                        added += 1

                    except ValueError as e:
                        if "already exists" in str(e).lower():
                            duplicates += 1
                        else:
                            errors += 1
                            logger.error("Error adding event", event=event['name'], error=str(e))
                    except Exception as e:
                        errors += 1
                        logger.error("Unexpected error", event=event['name'], error=str(e))

            click.echo("\n" + "=" * 80)
            click.echo("IMPORT SUMMARY")
            click.echo("=" * 80)
            click.echo(f"Added:      {added}")
            click.echo(f"Duplicates: {duplicates}")
            click.echo(f"Errors:     {errors}")
            click.echo(f"Total:      {len(filtered_events)}")
            click.echo("=" * 80)

            if added > 0:
                click.echo(f"\n✓ Successfully added {added} events to database!")

    except Exception as e:
        logger.error("GDELT fetch failed", error=str(e))
        click.echo(f"\n✗ Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()

