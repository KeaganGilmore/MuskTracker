# Quick Start Guide

## Setup Instructions

### 1. Install Dependencies

```powershell
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

The `.env` file is already configured with your X API credentials. Verify settings:

```powershell
# View current configuration
Get-Content .env
```

### 3. Initialize Database

```powershell
# Run migrations to create schema
python -m musktracker.cli.migrate up
```

### 4. Ingest Initial Data

```powershell
# Backfill last 7 days of tweets
python -m musktracker.cli.ingest --backfill-days 7
```

This will take 5-10 minutes depending on API rate limits.

### 5. Train Models

```powershell
# Train all models with backtesting
python -m musktracker.cli.train --model all --backtest-windows 12
```

Results will be saved to `backtest_results.json`.

### 6. Generate Forecasts

```powershell
# 24-hour forecast using Hawkes model (default)
python -m musktracker.cli.forecast --horizon 24h

# 7-day forecast using Negative Binomial
python -m musktracker.cli.forecast --model negative_binomial --horizon 7d
```

## Daily Operations

### Incremental Ingestion (Daily)

```powershell
# Ingest new tweets since last run
python -m musktracker.cli.ingest
```

Add to Windows Task Scheduler:
```powershell
# Create scheduled task (run daily at 2 AM)
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m musktracker.cli.ingest" -WorkingDirectory "C:\Users\keagan\Careers\CoreAxisDevelopment\Organizations\Polymarket\MuskTracker"
$trigger = New-ScheduledTaskTrigger -Daily -At 2am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "MuskTracker-Daily-Ingest" -Description "Ingest daily tweets"
```

### Model Retraining (Weekly)

```powershell
# Retrain models on latest data
python -m musktracker.cli.train --model all --backtest-windows 12
```

### Add Exogenous Events

```powershell
# Example: Tesla earnings call
python -m musktracker.cli.enrich add-event `
  --name "Tesla Q4 2024 Earnings Call" `
  --start "2025-01-29T21:00:00Z" `
  --end "2025-01-29T23:00:00Z" `
  --intensity 0.9 `
  --category "market" `
  --description "Quarterly earnings announcement"
```

## Troubleshooting

### X API Rate Limit Errors

If you see `429 Too Many Requests`:
- Wait 15 minutes for rate limit reset
- Retry logic will handle automatically
- Consider upgrading to X API Pro for higher limits

### Database Locked (SQLite)

If you see `database is locked`:
- Ensure no other processes are accessing the database
- Close any database browsers/viewers
- Consider switching to PostgreSQL for concurrent access

### Insufficient Training Data

If models fail with "insufficient data":
- Run ingestion first: `python -m musktracker.cli.ingest --backfill-days 7`
- Wait 24-48 hours to accumulate data
- SARIMAX needs at least 2 days of hourly data

### Module Import Errors

If you see `ModuleNotFoundError`:
```powershell
# Ensure virtual environment is activated
.\venv\Scripts\activate

# Reinstall dependencies
pip install -r requirements.txt
```

## Performance Tips

### Use PostgreSQL for Production

1. Install PostgreSQL:
```powershell
# Download from https://www.postgresql.org/download/windows/
# Or use Docker
docker run --name musktracker-postgres -e POSTGRES_PASSWORD=mypassword -p 5432:5432 -d postgres
```

2. Update `.env`:
```env
DATABASE_URL=postgresql://postgres:mypassword@localhost:5432/musktracker
```

3. Run migrations:
```powershell
python -m musktracker.cli.migrate up
```

### Speed Up Backtesting

```powershell
# Reduce backtest windows for faster evaluation
python -m musktracker.cli.train --backtest-windows 6
```

### Monitor Database Size

```powershell
# Check SQLite database size
Get-Item musktracker.db | Select-Object Name, Length

# For PostgreSQL
# SELECT pg_size_pretty(pg_database_size('musktracker'));
```

## Next Steps

1. **Explore Data**:
   - Use DB Browser for SQLite to query `musktracker.db`
   - Check `time_buckets` table for aggregated counts
   - View `forecasts` table for historical predictions

2. **Customize Models**:
   - Edit hyperparameters in `musktracker/models/*.py`
   - Adjust training window in `cli/train.py`

3. **Automate Workflows**:
   - Set up scheduled tasks for daily ingestion
   - Weekly model retraining
   - Daily forecast generation

4. **Extend Functionality**:
   - Add more exogenous data sources (news APIs)
   - Implement model ensembling
   - Build visualization dashboard (not included in MVP)

## Support

For issues or questions:
1. Check documentation in `docs/` folder
2. Review code comments for implementation details
3. Enable debug logging: Set `LOG_LEVEL=DEBUG` in `.env`

---

**Project Status**: ✅ Production-ready backend  
**Version**: 1.0.0  
**Last Updated**: December 28, 2025

