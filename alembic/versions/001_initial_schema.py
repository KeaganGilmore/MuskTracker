"""Initial schema creation

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-12-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial schema."""
    # Create raw_tweets table
    op.create_table(
        'raw_tweets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tweet_id', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source', sa.String(length=32), nullable=False),
        sa.Column('ingest_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tweet_id')
    )
    op.create_index('idx_created_at_not_deleted', 'raw_tweets', ['created_at', 'is_deleted'])
    op.create_index(op.f('ix_raw_tweets_created_at'), 'raw_tweets', ['created_at'])
    op.create_index(op.f('ix_raw_tweets_tweet_id'), 'raw_tweets', ['tweet_id'])

    # Create time_buckets table
    op.create_table(
        'time_buckets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bucket_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('bucket_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('granularity', sa.String(length=16), nullable=False),
        sa.Column('tweet_count', sa.Integer(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bucket_start', 'granularity', name='uq_bucket_granularity')
    )
    op.create_index('idx_bucket_start_granularity', 'time_buckets', ['bucket_start', 'granularity'])

    # Create exogenous_events table
    op.create_table(
        'exogenous_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('event_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('intensity', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_event_time_range', 'exogenous_events', ['event_start', 'event_end'])
    op.create_index(op.f('ix_exogenous_events_event_end'), 'exogenous_events', ['event_end'])
    op.create_index(op.f('ix_exogenous_events_event_start'), 'exogenous_events', ['event_start'])

    # Create features table
    op.create_table(
        'features',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('reference_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('lag_1h', sa.Integer(), nullable=True),
        sa.Column('lag_6h', sa.Integer(), nullable=True),
        sa.Column('lag_12h', sa.Integer(), nullable=True),
        sa.Column('lag_24h', sa.Integer(), nullable=True),
        sa.Column('lag_7d', sa.Integer(), nullable=True),
        sa.Column('rolling_mean_24h', sa.Float(), nullable=True),
        sa.Column('rolling_std_24h', sa.Float(), nullable=True),
        sa.Column('rolling_mean_7d', sa.Float(), nullable=True),
        sa.Column('rolling_std_7d', sa.Float(), nullable=True),
        sa.Column('hour_of_day', sa.Integer(), nullable=False),
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('is_weekend', sa.Boolean(), nullable=False),
        sa.Column('event_intensity', sa.Float(), nullable=False),
        sa.Column('events_in_window', sa.Integer(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_reference_time', 'features', ['reference_time'])
    op.create_index(op.f('ix_features_reference_time'), 'features', ['reference_time'])

    # Create model_metadata table
    op.create_table(
        'model_metadata',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_name', sa.String(length=64), nullable=False),
        sa.Column('model_version', sa.String(length=32), nullable=False),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('training_start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('training_end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hyperparameters', sa.Text(), nullable=True),
        sa.Column('rmse', sa.Float(), nullable=True),
        sa.Column('mae', sa.Float(), nullable=True),
        sa.Column('mape', sa.Float(), nullable=True),
        sa.Column('log_likelihood', sa.Float(), nullable=True),
        sa.Column('artifact_path', sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_model_name_version', 'model_metadata', ['model_name', 'model_version'])
    op.create_index(op.f('ix_model_metadata_model_name'), 'model_metadata', ['model_name'])

    # Create forecasts table
    op.create_table(
        'forecasts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_metadata_id', sa.Integer(), nullable=False),
        sa.Column('forecast_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('target_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('predicted_count', sa.Float(), nullable=False),
        sa.Column('lower_bound_95', sa.Float(), nullable=True),
        sa.Column('upper_bound_95', sa.Float(), nullable=True),
        sa.Column('actual_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_forecast_target', 'forecasts', ['forecast_time', 'target_time'])
    op.create_index(op.f('ix_forecasts_model_metadata_id'), 'forecasts', ['model_metadata_id'])
    op.create_index(op.f('ix_forecasts_target_time'), 'forecasts', ['target_time'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_index(op.f('ix_forecasts_target_time'), table_name='forecasts')
    op.drop_index(op.f('ix_forecasts_model_metadata_id'), table_name='forecasts')
    op.drop_index('idx_forecast_target', table_name='forecasts')
    op.drop_table('forecasts')

    op.drop_index(op.f('ix_model_metadata_model_name'), table_name='model_metadata')
    op.drop_index('idx_model_name_version', table_name='model_metadata')
    op.drop_table('model_metadata')

    op.drop_index(op.f('ix_features_reference_time'), table_name='features')
    op.drop_index('idx_reference_time', table_name='features')
    op.drop_table('features')

    op.drop_index(op.f('ix_exogenous_events_event_start'), table_name='exogenous_events')
    op.drop_index(op.f('ix_exogenous_events_event_end'), table_name='exogenous_events')
    op.drop_index('idx_event_time_range', table_name='exogenous_events')
    op.drop_table('exogenous_events')

    op.drop_index('idx_bucket_start_granularity', table_name='time_buckets')
    op.drop_table('time_buckets')

    op.drop_index(op.f('ix_raw_tweets_tweet_id'), table_name='raw_tweets')
    op.drop_index(op.f('ix_raw_tweets_created_at'), table_name='raw_tweets')
    op.drop_index('idx_created_at_not_deleted', table_name='raw_tweets')
    op.drop_table('raw_tweets')

