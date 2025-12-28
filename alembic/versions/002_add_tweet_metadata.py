"""Add missing tweet metadata columns

Revision ID: 002_add_tweet_metadata
Revises: 001_initial_schema
Create Date: 2025-12-28 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_tweet_metadata'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to raw_tweets table."""
    # SQLite has limited ALTER TABLE support, so we add columns with defaults
    # Add author_id column with default
    op.add_column('raw_tweets', sa.Column('author_id', sa.String(length=32), nullable=False, server_default='44196397'))

    # Add tweet type columns with defaults
    op.add_column('raw_tweets', sa.Column('is_retweet', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('raw_tweets', sa.Column('is_reply', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('raw_tweets', sa.Column('is_quote', sa.Boolean(), nullable=False, server_default='0'))

    # Add optional metadata columns
    op.add_column('raw_tweets', sa.Column('language', sa.String(length=8), nullable=True))
    op.add_column('raw_tweets', sa.Column('possibly_sensitive', sa.Boolean(), nullable=False, server_default='0'))

    # Update time_buckets table with missing columns
    op.add_column('time_buckets', sa.Column('retweet_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('time_buckets', sa.Column('reply_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('time_buckets', sa.Column('quote_count', sa.Integer(), nullable=False, server_default='0'))

    # Add is_active column to exogenous_events
    op.add_column('exogenous_events', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))


def downgrade() -> None:
    """Remove added columns from raw_tweets table."""
    op.drop_column('raw_tweets', 'possibly_sensitive')
    op.drop_column('raw_tweets', 'language')
    op.drop_column('raw_tweets', 'is_quote')
    op.drop_column('raw_tweets', 'is_reply')
    op.drop_column('raw_tweets', 'is_retweet')
    op.drop_column('raw_tweets', 'author_id')

    op.drop_column('time_buckets', 'quote_count')
    op.drop_column('time_buckets', 'reply_count')
    op.drop_column('time_buckets', 'retweet_count')

    op.drop_column('exogenous_events', 'is_active')

