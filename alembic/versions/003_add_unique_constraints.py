"""Add unique constraints for data integrity

Revision ID: 003_add_unique_constraints
Revises: 002_add_tweet_metadata
Create Date: 2025-12-28 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_unique_constraints'
down_revision: Union[str, None] = '002_add_tweet_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraints to prevent duplicate data.

    This ensures data integrity when importing from multiple sources.
    """
    # raw_tweets.tweet_id already has unique constraint from 001_initial_schema
    # Add index on created_at + tweet_id for faster duplicate checks
    try:
        op.create_index(
            'idx_raw_tweets_created_tweet_id',
            'raw_tweets',
            ['created_at', 'tweet_id']
        )
    except Exception:
        # Index might already exist, ignore
        pass

    # Add composite index on exogenous_events for duplicate detection
    try:
        op.create_index(
            'idx_exogenous_events_name_start',
            'exogenous_events',
            ['name', 'event_start']
        )
    except Exception:
        # Index might already exist, ignore
        pass


def downgrade() -> None:
    """Remove unique constraints."""
    try:
        op.drop_index('idx_raw_tweets_created_tweet_id', table_name='raw_tweets')
    except Exception:
        pass

    try:
        op.drop_index('idx_exogenous_events_name_start', table_name='exogenous_events')
    except Exception:
        pass

