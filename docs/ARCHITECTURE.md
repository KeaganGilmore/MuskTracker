# MuskTracker Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MuskTracker Backend System                    │
│                   Production-Grade Tweet Volume Modeling             │
└─────────────────────────────────────────────────────────────────────┘

External APIs          Data Layer              Feature Layer           Model Layer
═══════════════        ═══════════             ═══════════════         ═══════════

┌─────────────┐        ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
│  X API v2   │───────▶│ raw_tweets  │───────▶│ time_buckets│───────▶│  Negative   │
│ (tweepy)    │        │             │        │             │        │  Binomial   │
└─────────────┘        └─────────────┘        └─────────────┘        └─────────────┘
                                │                     │                      │
                                │                     │                      │
┌─────────────┐                 │                     ▼                      │
│   Manual    │                 │              ┌─────────────┐              │
│   Events    │────────────────▶│              │  features   │◀─────────────┤
│  (CLI)      │                 │              │             │              │
└─────────────┘                 │              └─────────────┘              │
                                │                     │                      │
                                ▼                     │                      ▼
                         ┌─────────────┐             │               ┌─────────────┐
                         │  exogenous  │─────────────┘               │   Hawkes    │
                         │   _events   │                             │   Process   │
                         └─────────────┘                             └─────────────┘
                                                                             │
                                                                             │
                                                                             ▼
                                                                      ┌─────────────┐
                                                                      │   SARIMAX   │
                                                                      │             │
                                                                      └─────────────┘
                                                                             │
                                                                             │
Persistence Layer                                                            ▼
═════════════════                                                     ┌─────────────┐
                                                                      │   model_    │
┌─────────────────────────────────────────────┐                      │  metadata   │
│         PostgreSQL / SQLite                 │                      └─────────────┘
│                                             │                             │
│  Tables:                                    │                             │
│  • raw_tweets (tweet_id, created_at)       │                             ▼
│  • time_buckets (bucket_start, count)      │                      ┌─────────────┐
│  • exogenous_events (name, intensity)      │                      │  forecasts  │
│  • features (lags, rolling, calendar)      │                      │             │
│  • model_metadata (hyperparams, metrics)   │                      └─────────────┘
│  • forecasts (predictions, CI bounds)      │
│                                             │
│  Migrations: Alembic                        │
│  Indexing: B-tree on timestamps            │
└─────────────────────────────────────────────┘


CLI Interface                    Evaluation Layer
═════════════                    ════════════════

┌─────────────┐                  ┌─────────────────────────────┐
│   migrate   │                  │   Rolling Backtests         │
│   ingest    │                  │   • 12 windows              │
│   enrich    │                  │   • 30-day training         │
│   train     │                  │   • 24-hour forecast        │
│   forecast  │                  │   • RMSE, MAE, MAPE         │
└─────────────┘                  └─────────────────────────────┘
                                           │
                                           │
                                           ▼
                                 ┌─────────────────────────────┐
                                 │   Regime Detection          │
                                 │   • Rolling variance        │
                                 │   • 2σ threshold            │
                                 │   • Shift alerts            │
                                 └─────────────────────────────┘
```

## Data Flow Pipeline

```
Step 1: Ingestion                Step 2: Aggregation            Step 3: Feature Engineering
═══════════════                  ═══════════════════            ═══════════════════════════

X API v2                         Raw Tweets                     Time Buckets
   │                                │                               │
   │ fetch_recent_tweets()          │ compute_time_buckets()        │
   ▼                                ▼                               ▼
┌────────┐                      ┌────────┐                     ┌────────┐
│ Tweet  │─────────────────────▶│Hourly  │────────────────────▶│ Lagged │
│Metadata│  tweet_id            │ Counts │  bucket aggregation │Features│
│        │  created_at          │        │                     │        │
└────────┘  ingest_time         └────────┘                     └────────┘
                                                                    │
                                                                    │ compute_features()
Exogenous Events                                                    │
   │                                                                ▼
   │ add_event()                                              ┌────────┐
   ▼                                                          │Rolling │
┌────────┐                                                    │  Stats │
│ Event  │───────────────────────────────────────────────────▶│Calendar│
│  Data  │  name, intensity, time_window                      │ Events │
└────────┘                                                     └────────┘


Step 4: Model Training            Step 5: Forecasting           Step 6: Evaluation
═══════════════════                ═══════════════               ═══════════════

Features                           Trained Models                Predictions
   │                                  │                              │
   │ fit(timestamps, counts)          │ predict(future_times)        │
   ▼                                  ▼                              ▼
┌────────┐                        ┌────────┐                    ┌────────┐
│ Model  │───────────────────────▶│Forecast│───────────────────▶│Metrics │
│Training│  learn parameters      │ Points │  compare actuals   │  RMSE  │
│        │                        │ + CIs  │                    │  MAE   │
└────────┘                        └────────┘                    └────────┘
                                       │
                                       │ store_forecast()
                                       ▼
                                  ┌────────┐
                                  │Database│
                                  │Storage │
                                  └────────┘
```

## Module Boundaries

```
musktracker/
│
├── config.py                  # ──────────────────────────────────┐
│   • Pydantic settings                                            │
│   • Environment variables                                        │
│   • Validation                                                   │
│                                                                  │
├── logging_config.py          # ──────────────────────────────────┤
│   • Structured logging (structlog)                               │
│   • JSON (prod) / Console (dev)                                 │
│                                                                  │
├── db/                        # ──────────────────────────────────┤
│   ├── models.py                                                  │
│   │   • SQLAlchemy ORM models                                   │
│   │   • Table definitions                                        │ Core
│   │   • Indexes, constraints                                     │ Infrastructure
│   │                                                              │
│   └── session.py                                                 │
│       • Session management                                       │
│       • Connection pooling                                       │
│       • Transaction handling                                     │
│                                                                  │
├── ingest/                    # ──────────────────────────────────┤
│   ├── x_client.py                                                │
│   │   • X API v2 wrapper                                        │
│   │   • Rate limiting                                            │
│   │   • Retry logic                                              │
│   │                                                              │
│   └── pipeline.py                                                │
│       • Ingestion orchestration                                  │
│       • Idempotency                                             │
│       • Backfill logic                   ────────────────────────┘
│
├── enrich/                    # ──────────────────────────────────┐
│   └── __init__.py                                                │
│       • Event enrichment                                         │
│       • Intensity computation                                    │
│                                                                  │
├── features/                  # ──────────────────────────────────┤
│   └── __init__.py                                                │
│       • Time bucketing                                           │
│       • Lagged features                                          │ Business
│       • Rolling aggregates                                       │ Logic
│       • Calendar features                                        │
│       • Event features                                           │
│                                                                  │
├── models/                    # ──────────────────────────────────┤
│   ├── base.py                                                    │
│   │   • Abstract model interface                                │
│   │   • Metric computation                                      │
│   │                                                              │
│   ├── negative_binomial.py                                       │
│   │   • NB GLM implementation                                   │
│   │                                                              │
│   ├── hawkes.py                                                  │
│   │   • Hawkes process (tick)                                   │
│   │                                                              │
│   └── sarimax.py                                                 │
│       • SARIMAX (statsmodels)                                   │
│                                                                  │
├── evaluation/                # ──────────────────────────────────┤
│   └── __init__.py                                                │
│       • Rolling backtests                                        │
│       • Regime detection                                         │
│       • Performance metrics             ────────────────────────┘
│
└── cli/                       # ──────────────────────────────────┐
    ├── migrate.py                                                 │
    │   • Database migrations                                      │
    │                                                              │
    ├── ingest.py                                                  │
    │   • Data collection                                          │
    │                                                              │
    ├── enrich.py                                                  │
    │   • Event management                                         │ User
    │                                                              │ Interface
    ├── train.py                                                   │
    │   • Model training                                           │
    │   • Backtesting                                              │
    │                                                              │
    └── forecast.py                                                │
        • Forecast generation                                      │
        • Result display                 ────────────────────────┘
```

## Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    Python 3.11+                             │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Data       │   │  Statistical │   │ Infrastructure│
│  Engineering │   │   Modeling   │   │   & Tools    │
└──────────────┘   └──────────────┘   └──────────────┘
        │                   │                   │
        │                   │                   │
  ┌─────┴─────┐       ┌─────┴─────┐       ┌─────┴─────┐
  │           │       │           │       │           │
  ▼           ▼       ▼           ▼       ▼           ▼
pandas    SQLAlchemy statsmodels  tick  pydantic   structlog
numpy     Alembic    scipy        sklearn tweepy   click
                                          tenacity mypy/ruff
```

## Deployment Architecture

```
Development                     Production
═══════════                     ══════════

┌─────────────┐                ┌─────────────────────────────┐
│   SQLite    │                │      PostgreSQL             │
│  (local)    │                │  • Connection pooling       │
└─────────────┘                │  • Partitioned tables       │
                               └─────────────────────────────┘

┌─────────────┐                ┌─────────────────────────────┐
│   Console   │                │      JSON Logs              │
│    Logs     │                │  • Ship to ELK/Splunk       │
└─────────────┘                │  • Structured queries       │
                               └─────────────────────────────┘

┌─────────────┐                ┌─────────────────────────────┐
│   Manual    │                │   Scheduled Tasks           │
│ CLI Execution│               │  • Cron / Windows Scheduler │
└─────────────┘                │  • Daily ingestion 2 AM     │
                               │  • Weekly training Sunday   │
                               └─────────────────────────────┘

┌─────────────┐                ┌─────────────────────────────┐
│  Single     │                │   Multi-Instance            │
│  Process    │                │  • Load balancer (optional) │
└─────────────┘                │  • Read replicas (optional) │
                               └─────────────────────────────┘
```

## Security & Compliance

```
Configuration               Data Privacy                Authentication
═════════════               ════════════                ══════════════

• .env file (gitignored)   • No tweet content          • X API Bearer Token
• No secrets in code       • Counts only               • Environment variables
• Environment variables    • Public data only          • No hardcoded credentials
• Pydantic validation     • No PII                    • Token rotation support


Licensing                   Audit Trail                 Error Handling
═════════                  ═══════════                 ══════════════

• CC BY-NC-ND 4.0         • Ingest timestamps         • Retry with backoff
• Non-commercial          • Soft deletes              • Structured logging
• No derivatives          • Versioned migrations      • Graceful degradation
• Attribution required    • Model metadata tracking   • Rate limit awareness
```

## Performance Characteristics

```
Operation               Latency         Throughput      Scalability
═════════               ═══════         ══════════      ═══════════

Ingestion (7 days)      ~10 min         Rate-limited    Parallelizable
Time bucketing          ~5 sec          168 hours       O(n)
Feature computation     ~10 sec         168 features    O(n)
NB model training       <1 sec          100 samples     O(n*k)
Hawkes fitting          ~10 sec         1000 events     O(n²)
SARIMAX training        ~30 sec         1000 samples    O(n³)
Forecasting (24h)       <1 sec          24 predictions  O(h)
Backtest (12 windows)   ~5 min          12 folds        Parallelizable


Database Growth         Storage         Queries/sec     Indexing
═══════════════         ═══════         ═══════════     ════════

50 tweets/day           ~100 MB/year    100+ (SQLite)   B-tree on timestamps
Hourly buckets          Negligible      1000+ (Postgres) Composite indexes
Features table          ~10 MB/year     Fast lookups    Timestamp indexes
Forecasts table         ~50 MB/year     Batch inserts   Target time index
```

---

**Document Version**: 1.0.0  
**Last Updated**: December 28, 2025  
**Author**: MuskTracker Team

