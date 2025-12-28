"""Forecasting CLI."""

from datetime import datetime, timedelta, timezone

import click

from musktracker.features import FeatureEngineer
from musktracker.logging_config import get_logger, setup_logging
from musktracker.models.hawkes import HawkesModel
from musktracker.models.negative_binomial import NegativeBinomialModel
from musktracker.models.sarimax import SARIMAXModel

logger = get_logger(__name__)


@click.command()
@click.option(
    "--model",
    type=click.Choice(["negative_binomial", "hawkes", "sarimax"]),
    default="hawkes",
    help="Model to use for forecasting",
)
@click.option(
    "--horizon",
    type=str,
    default="24h",
    help="Forecast horizon (e.g., '24h', '7d')",
)
@click.option("--train-days", type=int, default=30, help="Days of training data")
def forecast(model: str, horizon: str, train_days: int) -> None:
    """Generate forecasts for future tweet volume.

    Examples:
        python -m musktracker.cli.forecast --horizon 24h
        python -m musktracker.cli.forecast --model negative_binomial --horizon 7d
    """
    setup_logging()

    # Parse horizon
    horizon_hours = parse_horizon(horizon)

    # Initialize feature engineer
    feature_engineer = FeatureEngineer()

    # Define training period
    end_train = datetime.now(timezone.utc)
    start_train = end_train - timedelta(days=train_days)

    # Ensure time buckets exist
    logger.info("Computing time buckets for training data")
    feature_engineer.compute_time_buckets(start_train, end_train, granularity="hourly")

    # Get training data
    train_df = feature_engineer.get_bucket_counts(start_train, end_train, granularity="hourly")

    if train_df.empty:
        logger.error("No training data available")
        raise click.ClickException("No training data available. Run ingestion first.")

    # Initialize model
    if model == "negative_binomial":
        m = NegativeBinomialModel()
    elif model == "hawkes":
        m = HawkesModel()
    elif model == "sarimax":
        m = SARIMAXModel()
    else:
        raise click.ClickException(f"Unknown model: {model}")

    logger.info("Training model", model=m.name, train_samples=len(train_df))
    click.echo(f"Training {m.name} on {len(train_df)} hours of data...")

    # Train model
    try:
        m.fit(
            timestamps=train_df["timestamp"].values,
            counts=train_df["count"].values,
        )
        click.echo("Model trained successfully")
    except Exception as e:
        logger.error("Model training failed", error=str(e))
        raise click.ClickException(f"Training failed: {str(e)}")

    # Generate forecast timestamps
    forecast_times = [
        end_train + timedelta(hours=i) for i in range(1, horizon_hours + 1)
    ]

    logger.info("Generating forecast", horizon_hours=horizon_hours)
    click.echo(f"\nGenerating {horizon_hours}-hour forecast...")

    # Generate predictions
    try:
        predictions, lower, upper = m.predict(timestamps=forecast_times)

        # Display results
        click.echo("\nForecast Results:")
        click.echo("=" * 80)
        click.echo(f"{'Time':^25} | {'Predicted':^12} | {'95% CI Lower':^12} | {'95% CI Upper':^12}")
        click.echo("-" * 80)

        for i, (time, pred, lo, hi) in enumerate(zip(forecast_times, predictions, lower, upper)):
            if i < 24 or i % 24 == 0:  # Show first 24 hours, then daily
                click.echo(
                    f"{time.strftime('%Y-%m-%d %H:%M'):^25} | "
                    f"{pred:^12.2f} | "
                    f"{lo:^12.2f} | "
                    f"{hi:^12.2f}"
                )

        # Summary statistics
        click.echo("=" * 80)
        click.echo(f"\nSummary:")
        click.echo(f"  Total predicted tweets: {predictions.sum():.0f}")
        click.echo(f"  Average per hour: {predictions.mean():.2f}")
        click.echo(f"  Peak hour: {predictions.max():.0f} tweets")
        click.echo(f"  Minimum hour: {predictions.min():.0f} tweets")

        logger.info("Forecast completed successfully")

    except Exception as e:
        logger.error("Forecast generation failed", error=str(e))
        raise click.ClickException(f"Forecast failed: {str(e)}")


def parse_horizon(horizon: str) -> int:
    """Parse horizon string to hours.

    Args:
        horizon: String like '24h', '7d', '168h'

    Returns:
        Number of hours
    """
    horizon = horizon.lower()

    if horizon.endswith("h"):
        return int(horizon[:-1])
    elif horizon.endswith("d"):
        return int(horizon[:-1]) * 24
    else:
        raise ValueError(f"Invalid horizon format: {horizon}. Use '24h' or '7d'")


if __name__ == "__main__":
    forecast()

