"""
MuskTracker - Production-Grade Tweet Volume Modeling System
============================================================

A backend-only Python application for modeling and forecasting @elonmusk tweet volume
using advanced statistical methods (Negative Binomial, Hawkes Process, SARIMAX).

Quick Start:
-----------
1. Install dependencies: pip install -r requirements.txt
2. Setup database: python -m musktracker.cli.migrate up
3. Ingest data: python -m musktracker.cli.ingest --backfill-days 7
4. Train models: python -m musktracker.cli.train --model all
5. Forecast: python -m musktracker.cli.forecast --horizon 24h

For detailed documentation, see README.md and docs/ folder.
"""

__version__ = "1.0.0"
__author__ = "MuskTracker Team"
__license__ = "CC BY-NC-ND 4.0"

import click
from musktracker.cli import migrate, ingest, enrich, train, forecast


@click.group()
@click.version_option(version=__version__)
def main():
    """MuskTracker - Advanced Tweet Volume Modeling System"""
    pass


# Register all CLI commands
main.add_command(migrate.migrate)
main.add_command(ingest.ingest)
main.add_command(enrich.enrich)
main.add_command(train.train)
main.add_command(forecast.forecast)


if __name__ == "__main__":
    main()
