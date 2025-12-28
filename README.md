# MuskTracker

A production-grade backend system for modeling Elon Musk tweet volume using advanced statistical methods.

## Overview

MuskTracker collects tweet metadata from @elonmusk via X API v2 and applies sophisticated time-series models (Negative Binomial, Hawkes processes, SARIMAX) to forecast future tweet volumes with regime-shift awareness and rigorous backtesting.

**Backend-only**: No UI/frontend—focus on data engineering, statistical rigor, and extensibility.

## Features

- **X API v2 Integration**: Idempotent ingestion with rate-limit awareness and retry logic
- **Relational Storage**: Postgres-backed (SQLite for local dev) with versioned migrations
- **Advanced Modeling**: Negative Binomial, Hawkes (self-exciting), and SARIMAX baseline
- **Feature Engineering**: Lagged features, rolling windows, calendar effects, exogenous event intensity
- **Rigorous Evaluation**: Rolling backtests, regime detection, statistical performance metrics
- **Production-Ready**: Type hints, logging, config via env vars, clean module boundaries

## Architecture

```
musktracker/
├── ingest/          # X API v2 data collection
├── enrich/          # Exogenous event integration
├── features/        # Feature engineering & aggregation
├── models/          # Statistical models (NB, Hawkes, SARIMAX)
├── evaluation/      # Backtesting & metrics
├── db/              # Database layer & migrations
└── cli/             # Command-line entrypoints
```

## Requirements

- Python 3.11+
- PostgreSQL 14+ (or SQLite for local development)
- X API v2 credentials (Bearer Token)

## Installation

```bash
# Create virtual environment
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your X API credentials and database URL
```

## Configuration

All configuration via environment variables (see `.env.example`):

- `X_BEARER_TOKEN`: X API v2 Bearer Token
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:pass@localhost/musktracker`)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `TIMEZONE`: UTC (enforced)

## Database Setup

```bash
# Run migrations to create schema
python -m musktracker.cli.migrate up
```

See [SCHEMA.md](docs/SCHEMA.md) for detailed schema documentation.

## Usage

### 1. Ingest Tweet Data

```bash
# Backfill historical data (last 7 days)
python -m musktracker.cli.ingest --backfill-days 7

# Incremental ingestion (new tweets since last run)
python -m musktracker.cli.ingest
```

### 2. Enrich with Exogenous Events (Optional)

```bash
# Manually add event (e.g., product launch, regulatory news)
python -m musktracker.cli.enrich add-event \
  --name "Tesla Q4 Earnings" \
  --start "2025-01-15T00:00:00Z" \
  --end "2025-01-15T23:59:59Z" \
  --intensity 0.8
```

### 3. Train Models

```bash
# Train all models with rolling backtest
python -m musktracker.cli.train --backtest-windows 12

# Train specific model
python -m musktracker.cli.train --model hawkes --backtest-windows 12
```

### 4. Generate Forecasts

```bash
# 24-hour forecast
python -m musktracker.cli.forecast --horizon 24h

# 7-day forecast
python -m musktracker.cli.forecast --horizon 7d

# Specify model
python -m musktracker.cli.forecast --model negative_binomial --horizon 24h
```

## Models

### Negative Binomial Regression
- Handles overdispersion in count data
- GLM with log link, exogenous features
- Robust to high-variance regimes

### Hawkes Process (Self-Exciting)
- Captures temporal clustering and self-reinforcement
- Exponential kernel for decay
- Ideal for bursty behavior patterns

### SARIMAX (Baseline)
- Seasonal ARIMA with exogenous regressors
- Handles trend, seasonality, external events
- Baseline for model comparison

See [MODELS.md](docs/MODELS.md) for mathematical details and assumptions.

## Data Limitations & Assumptions

- **API Access**: X API v2 free tier has rate limits; managed via exponential backoff
- **Location Uncertainty**: No location/timezone data in tweets; all timestamps normalized to UTC
- **Historical Depth**: Free tier limited to 7-day lookback; upgrade for more history
- **Exogenous Events**: Manually curated; no automated news scraping in v1
- **Regime Shifts**: Detected via rolling variance; assumes stationary behavior within windows

See [ASSUMPTIONS.md](docs/ASSUMPTIONS.md) for full details.

## Development

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Type checking
mypy musktracker/

# Linting
ruff check musktracker/
```

## Project Status

**Version**: 1.0.0  
**Status**: Production-ready backend  
**License**: MIT

## Roadmap

- [ ] Automated event detection via news APIs
- [ ] Multi-user tracking (beyond @elonmusk)
- [ ] GPU-accelerated Hawkes process fitting
- [ ] Real-time streaming ingestion
- [ ] Model ensembling & stacking

## Support

For issues, feature requests, or questions, open an issue on the project repository.

