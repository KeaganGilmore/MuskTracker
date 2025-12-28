# Database Schema Documentation

## Overview

MuskTracker uses a normalized relational schema optimized for time-series analytics and statistical modeling. All timestamps are stored in UTC with timezone awareness.

## Tables

### raw_tweets

**Purpose**: Stores minimal metadata for each tweet from @elonmusk.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing surrogate key |
| `tweet_id` | VARCHAR(64) | UNIQUE, NOT NULL | X API tweet ID |
| `created_at` | TIMESTAMP WITH TZ | NOT NULL, INDEXED | Tweet creation time (UTC) |
| `source` | VARCHAR(32) | NOT NULL | Data source (e.g., 'x_api_v2') |
| `ingest_time` | TIMESTAMP WITH TZ | NOT NULL | When tweet was ingested |
| `is_deleted` | BOOLEAN | NOT NULL, DEFAULT FALSE | Soft delete flag |

**Indexes**:
- `idx_created_at_not_deleted` (created_at, is_deleted) - Optimizes time-range queries
- `ix_raw_tweets_tweet_id` (tweet_id) - Deduplication
- `ix_raw_tweets_created_at` (created_at) - Temporal queries

**Rationale**: 
- No tweet content stored (privacy, compliance, counts-only requirement)
- Soft deletes preserve historical integrity
- Timezone-aware timestamps prevent conversion errors

---

### time_buckets

**Purpose**: Pre-computed time-bucketed aggregates for efficient feature engineering.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing surrogate key |
| `bucket_start` | TIMESTAMP WITH TZ | NOT NULL | Bucket start time (UTC) |
| `bucket_end` | TIMESTAMP WITH TZ | NOT NULL | Bucket end time (UTC) |
| `granularity` | VARCHAR(16) | NOT NULL | 'hourly' or 'daily' |
| `tweet_count` | INTEGER | NOT NULL | Number of tweets in bucket |
| `computed_at` | TIMESTAMP WITH TZ | NOT NULL | When bucket was computed |

**Indexes**:
- `uq_bucket_granularity` UNIQUE (bucket_start, granularity) - Prevents duplicates
- `idx_bucket_start_granularity` (bucket_start, granularity) - Query optimization

**Rationale**:
- Materialized aggregates avoid repeated raw scans
- Support multiple granularities for multi-scale modeling
- `computed_at` enables incremental updates

---

### exogenous_events

**Purpose**: External events that may influence tweet volume (manually curated or API-sourced).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing surrogate key |
| `name` | VARCHAR(256) | NOT NULL | Event name |
| `description` | TEXT | NULLABLE | Event description |
| `category` | VARCHAR(64) | NULLABLE | Category (e.g., 'market', 'regulatory') |
| `event_start` | TIMESTAMP WITH TZ | NOT NULL, INDEXED | Event start time (UTC) |
| `event_end` | TIMESTAMP WITH TZ | NOT NULL, INDEXED | Event end time (UTC) |
| `intensity` | FLOAT | NOT NULL | Intensity score (0.0 to 1.0) |
| `source` | VARCHAR(64) | NOT NULL | Event source (e.g., 'manual', 'news_api') |
| `created_at` | TIMESTAMP WITH TZ | NOT NULL | When event was added |

**Indexes**:
- `idx_event_time_range` (event_start, event_end) - Range overlap queries

**Rationale**:
- Flexible schema supports various event types
- Intensity scoring enables weighted feature engineering
- Time windows allow partial overlap detection

---

### features

**Purpose**: Computed features for statistical modeling (lagged, rolling, calendar, event-based).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing surrogate key |
| `reference_time` | TIMESTAMP WITH TZ | NOT NULL, INDEXED | Time point for features |
| `lag_1h` | INTEGER | NULLABLE | Tweet count 1 hour ago |
| `lag_6h` | INTEGER | NULLABLE | Tweet count 6 hours ago |
| `lag_12h` | INTEGER | NULLABLE | Tweet count 12 hours ago |
| `lag_24h` | INTEGER | NULLABLE | Tweet count 24 hours ago |
| `lag_7d` | INTEGER | NULLABLE | Tweet count 7 days ago |
| `rolling_mean_24h` | FLOAT | NULLABLE | 24-hour rolling mean |
| `rolling_std_24h` | FLOAT | NULLABLE | 24-hour rolling std dev |
| `rolling_mean_7d` | FLOAT | NULLABLE | 7-day rolling mean |
| `rolling_std_7d` | FLOAT | NULLABLE | 7-day rolling std dev |
| `hour_of_day` | INTEGER | NOT NULL | Hour of day (0-23) |
| `day_of_week` | INTEGER | NOT NULL | Day of week (0=Monday, 6=Sunday) |
| `is_weekend` | BOOLEAN | NOT NULL | Weekend indicator |
| `event_intensity` | FLOAT | NOT NULL | Max event intensity in 24h window |
| `events_in_window` | INTEGER | NOT NULL | Count of events in 24h window |
| `computed_at` | TIMESTAMP WITH TZ | NOT NULL | When features were computed |

**Indexes**:
- `idx_reference_time` (reference_time) - Temporal joins

**Rationale**:
- Denormalized for model training efficiency
- NULL lags handle insufficient history gracefully
- Event features bridge to exogenous data

---

### model_metadata

**Purpose**: Tracks model versions, training history, and performance metrics.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing surrogate key |
| `model_name` | VARCHAR(64) | NOT NULL, INDEXED | Model name ('hawkes', 'negative_binomial', etc.) |
| `model_version` | VARCHAR(32) | NOT NULL | Version identifier |
| `trained_at` | TIMESTAMP WITH TZ | NOT NULL | Training timestamp |
| `training_start_date` | TIMESTAMP WITH TZ | NOT NULL | Training data start |
| `training_end_date` | TIMESTAMP WITH TZ | NOT NULL | Training data end |
| `hyperparameters` | TEXT | NULLABLE | JSON-serialized hyperparameters |
| `rmse` | FLOAT | NULLABLE | Root mean squared error |
| `mae` | FLOAT | NULLABLE | Mean absolute error |
| `mape` | FLOAT | NULLABLE | Mean absolute percentage error |
| `log_likelihood` | FLOAT | NULLABLE | Log-likelihood (if applicable) |
| `artifact_path` | VARCHAR(512) | NULLABLE | Path to saved model artifact |

**Indexes**:
- `idx_model_name_version` (model_name, model_version) - Version lookup

**Rationale**:
- Enables model reproducibility and A/B testing
- Performance metrics support model selection
- Artifact paths for production deployment

---

### forecasts

**Purpose**: Stores model predictions with confidence intervals and actuals.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY | Auto-incrementing surrogate key |
| `model_metadata_id` | INTEGER | NOT NULL, INDEXED | Reference to model_metadata |
| `forecast_time` | TIMESTAMP WITH TZ | NOT NULL | When forecast was generated |
| `target_time` | TIMESTAMP WITH TZ | NOT NULL, INDEXED | Target prediction time |
| `predicted_count` | FLOAT | NOT NULL | Point prediction |
| `lower_bound_95` | FLOAT | NULLABLE | 95% CI lower bound |
| `upper_bound_95` | FLOAT | NULLABLE | 95% CI upper bound |
| `actual_count` | INTEGER | NULLABLE | Actual observed count (filled later) |
| `created_at` | TIMESTAMP WITH TZ | NOT NULL | Record creation time |

**Indexes**:
- `idx_forecast_target` (forecast_time, target_time) - Forecast analysis
- `ix_forecasts_target_time` (target_time) - Actuals backfill

**Rationale**:
- Separates forecast metadata from model metadata
- `actual_count` enables online model monitoring
- Confidence intervals for uncertainty quantification

---

## Migration Strategy

**Versioned Migrations**: Alembic handles schema evolution with forward/backward compatibility.

**Migration Files**:
- `001_initial_schema.py` - Creates all tables and indexes

**Running Migrations**:
```bash
# Apply migrations
python -m musktracker.cli.migrate up

# Rollback
python -m musktracker.cli.migrate down --revision -1

# Check status
python -m musktracker.cli.migrate current
```

---

## Data Flow

```
X API → raw_tweets → time_buckets → features → models → forecasts
                         ↓
                  exogenous_events (manual)
```

1. **Ingestion**: X API v2 → `raw_tweets`
2. **Aggregation**: `raw_tweets` → `time_buckets` (hourly/daily)
3. **Enrichment**: Manual/API → `exogenous_events`
4. **Feature Engineering**: `time_buckets` + `exogenous_events` → `features`
5. **Training**: `features` → `model_metadata`
6. **Forecasting**: `model_metadata` → `forecasts`

---

## Data Integrity

**Constraints**:
- Primary keys on all tables
- Unique constraints prevent duplicates (tweet_id, bucket combinations)
- Foreign key relationships enforced via `model_metadata_id`

**Timezone Discipline**:
- All `TIMESTAMP WITH TIMEZONE` columns store UTC
- Application layer enforces UTC conversion
- No implicit timezone conversions

**Idempotency**:
- `raw_tweets.tweet_id` UNIQUE enables safe re-ingestion
- `time_buckets.uq_bucket_granularity` allows recomputation
- Soft deletes preserve audit trail

---

## Performance Considerations

**Indexing Strategy**:
- B-tree indexes on timestamp ranges (most common query pattern)
- Composite indexes for multi-column filters
- Unique indexes enforce constraints and optimize lookups

**Partitioning** (Future):
- Partition `raw_tweets` by month for archival
- Partition `forecasts` by target_time for efficient pruning

**Vacuum/Analyze**:
- Postgres: Regular VACUUM ANALYZE on high-write tables
- SQLite: Periodic VACUUM for space reclamation

---

## Schema Evolution

**Adding Columns**:
```python
# Example migration
def upgrade():
    op.add_column('features', sa.Column('new_feature', sa.Float(), nullable=True))
```

**Backward Compatibility**:
- New columns default to NULL
- Deprecated columns soft-deleted (rename to `_deprecated_colname`)

**Data Migrations**:
- Separate data migrations from schema changes
- Use batch updates for large tables

