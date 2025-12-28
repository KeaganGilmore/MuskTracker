"""Import historical tweets from CSV file."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
import pandas as pd
from sqlalchemy import select

from musktracker.db.models import RawTweet
from musktracker.db.session import get_db_session
from musktracker.logging_config import get_logger

logger = get_logger(__name__)


def extract_tweet_id_from_url(url: str) -> Optional[str]:
    """Extract tweet ID from Twitter/X URL.

    Args:
        url: Twitter or X URL

    Returns:
        Tweet ID or None if not found
    """
    if pd.isna(url) or not url:
        return None

    # Match pattern like https://twitter.com/username/status/1234567890
    match = re.search(r'/status/(\d+)', str(url))
    if match:
        return match.group(1)
    return None


def parse_boolean(value) -> bool:
    """Parse boolean value from CSV.

    Args:
        value: Value from CSV (could be string, bool, or NaN)

    Returns:
        Boolean value
    """
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return bool(value)


def import_tweets_from_csv(csv_path: Path, batch_size: int = 1000) -> dict:
    """Import tweets from CSV file into database.

    Args:
        csv_path: Path to CSV file
        batch_size: Number of tweets to process in each batch

    Returns:
        Dictionary with import statistics
    """
    logger.info("Starting CSV import", csv_path=str(csv_path))

    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Read CSV file
    logger.info("Reading CSV file")
    df = pd.read_csv(csv_path)

    logger.info("CSV loaded", total_rows=len(df), columns=list(df.columns))

    # Statistics
    stats = {
        "total_rows": len(df),
        "imported": 0,
        "duplicates": 0,
        "errors": 0,
        "skipped_no_id": 0,
    }

    # Process in batches
    for batch_start in range(0, len(df), batch_size):
        batch_end = min(batch_start + batch_size, len(df))
        batch_df = df.iloc[batch_start:batch_end]

        logger.info("Processing batch", start=batch_start, end=batch_end)

        with get_db_session() as session:
            for idx, row in batch_df.iterrows():
                try:
                    # Extract tweet ID from URL
                    tweet_id = extract_tweet_id_from_url(row.get('twitterUrl'))

                    if not tweet_id:
                        stats["skipped_no_id"] += 1
                        logger.warning("No tweet ID found", row_index=idx, url=row.get('twitterUrl'))
                        continue

                    # Check if tweet already exists
                    existing = session.execute(
                        select(RawTweet).where(RawTweet.tweet_id == tweet_id)
                    ).scalar_one_or_none()

                    if existing:
                        stats["duplicates"] += 1
                        continue

                    # Parse created_at timestamp
                    created_at_str = row.get('createdAt')
                    if pd.isna(created_at_str):
                        stats["errors"] += 1
                        logger.warning("Missing createdAt", tweet_id=tweet_id, row_index=idx)
                        continue

                    # Parse timestamp - handle timezone
                    created_at = pd.to_datetime(created_at_str, utc=True)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)

                    # Extract other fields
                    is_retweet = parse_boolean(row.get('isRetweet'))
                    is_reply = parse_boolean(row.get('isReply'))
                    is_quote = parse_boolean(row.get('isQuote'))
                    possibly_sensitive = parse_boolean(row.get('possiblySensitive'))

                    # Language field (if available)
                    language = row.get('language')
                    if pd.isna(language):
                        language = None

                    # Create tweet record
                    tweet = RawTweet(
                        tweet_id=tweet_id,
                        created_at=created_at.to_pydatetime(),
                        author_id="44196397",  # Elon Musk's user ID
                        is_retweet=is_retweet,
                        is_reply=is_reply,
                        is_quote=is_quote,
                        language=language,
                        possibly_sensitive=possibly_sensitive,
                        source="csv_import",
                        ingest_time=datetime.now(timezone.utc),
                        is_deleted=False,
                    )

                    session.add(tweet)
                    stats["imported"] += 1

                except Exception as e:
                    stats["errors"] += 1
                    logger.error("Error processing row", row_index=idx, error=str(e))
                    continue

            # Commit batch
            session.commit()
            logger.info(
                "Batch committed",
                imported_in_batch=stats["imported"] - (batch_start // batch_size) * batch_size,
                total_imported=stats["imported"],
            )

    logger.info("CSV import completed", **stats)
    return stats


@click.command()
@click.option(
    "--csv-path",
    type=click.Path(exists=True, path_type=Path),
    default="data/all_musk_posts.csv",
    help="Path to CSV file",
)
@click.option(
    "--batch-size",
    type=int,
    default=1000,
    help="Number of tweets to process in each batch",
)
def main(csv_path: Path, batch_size: int) -> None:
    """Import historical tweets from CSV file.

    This command imports tweets from a CSV file containing historical Elon Musk tweets.
    The CSV should have columns: twitterUrl, createdAt, isRetweet, isReply, isQuote, etc.
    """
    try:
        stats = import_tweets_from_csv(csv_path, batch_size)

        click.echo("\n" + "=" * 60)
        click.echo("CSV IMPORT SUMMARY")
        click.echo("=" * 60)
        click.echo(f"Total rows in CSV:     {stats['total_rows']:,}")
        click.echo(f"Successfully imported: {stats['imported']:,}")
        click.echo(f"Duplicates (skipped):  {stats['duplicates']:,}")
        click.echo(f"No tweet ID (skipped): {stats['skipped_no_id']:,}")
        click.echo(f"Errors:                {stats['errors']:,}")
        click.echo("=" * 60)

        if stats['imported'] > 0:
            click.echo(f"\n✓ Successfully imported {stats['imported']:,} tweets!")
        else:
            click.echo("\n⚠ No new tweets were imported.")

    except Exception as e:
        logger.error("CSV import failed", error=str(e))
        click.echo(f"\n✗ Error: {e}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    main()

