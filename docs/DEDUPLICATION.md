# Data Deduplication Strategy

## Overview

MuskTracker implements comprehensive deduplication to ensure data integrity when importing from multiple sources (CSV files, X API, GDELT, etc.).

## Deduplication Mechanisms

### 1. Tweets (raw_tweets table)

**Primary Key**: `tweet_id` (unique constraint at database level)

**Deduplication Strategy**:
- Database enforces uniqueness on `tweet_id` column
- Import scripts check for existing tweet_id before insertion
- If duplicate found, import skips and logs as "duplicate"
- Prevents same tweet from appearing twice even if imported from multiple CSVs

**Code Example**:
```python
# In import_csv.py and ingest pipeline
existing = session.execute(
    select(RawTweet).where(RawTweet.tweet_id == tweet_id)
).scalar_one_or_none()

if existing:
    stats["duplicates"] += 1
    continue
```

### 2. Events (exogenous_events table)

**Deduplication Strategy**:
- Events are considered duplicates if they have:
  - Same name
  - Start date within ±1 day window
- EventEnricher.add_event() has `skip_duplicates=True` by default
- Returns `None` when duplicate is skipped
- Prevents duplicate events from GDELT or manual entry

**Code Example**:
```python
# In EventEnricher.add_event()
existing = session.query(ExogenousEvent).filter(
    and_(
        ExogenousEvent.name == name,
        ExogenousEvent.event_start >= event_start - timedelta(days=1),
        ExogenousEvent.event_start <= event_start + timedelta(days=1)
    )
).first()

if existing and skip_duplicates:
    return None  # Skip duplicate
```

### 3. GDELT Articles

**Deduplication Strategy**:
- Batched queries may return overlapping articles
- GDELTClient deduplicates by URL before returning
- Ensures each unique article appears only once per fetch

**Code Example**:
```python
# In GDELTClient.fetch_events()
if 'url' in combined_df.columns:
    combined_df = combined_df.drop_duplicates(subset=['url'], keep='first')
```

### 4. Time Buckets

**Deduplication Strategy**:
- Unique constraint on (bucket_start, granularity)
- FeatureEngineer checks for existing bucket before creating
- If bucket exists, it's updated rather than creating duplicate

## Multi-Source Import Scenarios

### Scenario 1: Importing Multiple CSV Files

```python
# First CSV import
python -m musktracker.cli.import_csv --csv-path data/tweets_2010_2020.csv

# Second CSV import (may have overlapping tweets)
python -m musktracker.cli.import_csv --csv-path data/tweets_2020_2025.csv

# Result: Only unique tweets are added, duplicates are skipped
```

**Output**:
```
Total rows:     60,000
Imported:       5,000 (new tweets)
Duplicates:     55,000 (already in database)
```

### Scenario 2: GDELT Event Fetching (Multiple Runs)

```python
# First fetch: January 2024
python -m musktracker.cli.fetch_gdelt --start-date 2024-01-01 --end-date 2024-01-31

# Second fetch: Overlapping period
python -m musktracker.cli.fetch_gdelt --start-date 2024-01-15 --end-date 2024-02-15

# Result: Events from Jan 15-31 are automatically deduplicated
```

### Scenario 3: API Ingestion + CSV Import

```python
# Import historical CSV
python -m musktracker.cli.import_csv

# Later, fetch recent tweets from API
python -m musktracker.cli.ingest --backfill-days 7

# Result: If CSV had recent tweets, API won't duplicate them
```

## Database Indexes for Performance

Indexes are created to make duplicate checks fast:

1. `raw_tweets.tweet_id` - Unique index (enforced)
2. `idx_raw_tweets_created_tweet_id` - Composite index for faster lookups
3. `idx_exogenous_events_name_start` - For event duplicate detection
4. `uq_bucket_granularity` - Prevents duplicate time buckets

## Best Practices

### When Importing Data

✅ **DO**:
- Always run imports even if data may overlap - deduplication is automatic
- Check import statistics to see how many duplicates were skipped
- Use `--dry-run` for GDELT fetches to preview before adding

❌ **DON'T**:
- Manually filter data before import - let the system handle it
- Worry about running the same import twice - it's idempotent
- Delete and re-import data - just import, duplicates will be skipped

### Monitoring Duplicates

Check logs for duplicate statistics:

```
CSV IMPORT SUMMARY
Total rows in CSV:     55,099
Successfully imported: 50,000
Duplicates (skipped):  5,099
```

```
GDELT IMPORT SUMMARY
Added:      250
Duplicates: 45
Errors:     0
```

## Data Lineage Tracking

Each data source is tracked via the `source` column:

**Tweets**:
- `csv_import` - From CSV file
- `x_api_v2` - From X API
- `manual` - Manually added

**Events**:
- `gdelt` - From GDELT API
- `manual` - Manually added
- `preset` - From predefined event list

Query by source:
```sql
-- See how many tweets from each source
SELECT source, COUNT(*) FROM raw_tweets GROUP BY source;

-- See events by source
SELECT source, COUNT(*) FROM exogenous_events GROUP BY source;
```

## Handling Edge Cases

### Same Event, Different Names

If GDELT returns the same event with slightly different titles:
- Deduplication matches on name + date window (±1 day)
- First version is kept
- Can manually merge if needed

### Tweet Retweets

Retweets have different tweet_ids, so they're NOT duplicates:
- Original tweet: `tweet_id=123`, `is_retweet=False`
- Retweet: `tweet_id=456`, `is_retweet=True`
- Both are stored (intentional - models may care about retweet behavior)

## Migration

Run the migration to add indexes:

```powershell
python -m musktracker.cli.migrate up
```

This creates the necessary indexes for efficient deduplication.

## Summary

🎯 **Goal**: Scalable, multi-source data system with automatic deduplication

✅ **Tweets**: Deduplicated by `tweet_id` (database constraint)
✅ **Events**: Deduplicated by name + date (application logic)
✅ **GDELT**: Deduplicated by URL (per-fetch)
✅ **Time Buckets**: Deduplicated by bucket_start + granularity (database constraint)

📊 **Result**: You can safely import data from multiple sources without worrying about duplicates!

