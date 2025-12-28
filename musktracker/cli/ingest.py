"""Data ingestion CLI."""

import click

from musktracker.ingest.pipeline import TweetIngestor
from musktracker.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


@click.command()
@click.option("--backfill-days", type=int, default=0, help="Backfill N days of history")
def ingest(backfill_days: int) -> None:
    """Ingest tweet data from X API.

    Examples:
        python -m musktracker.cli.ingest
        python -m musktracker.cli.ingest --backfill-days 7
    """
    setup_logging()

    ingestor = TweetIngestor()

    try:
        if backfill_days > 0:
            logger.info("Starting backfill", days=backfill_days)
            count = ingestor.backfill(days=backfill_days)
        else:
            logger.info("Starting incremental ingestion")
            count = ingestor.ingest_tweets()

        logger.info("Ingestion completed", new_tweets=count)
        click.echo(f"Successfully ingested {count} new tweets")

    except Exception as e:
        logger.error("Ingestion failed", error=str(e))
        raise click.ClickException(str(e))


if __name__ == "__main__":
    ingest()

