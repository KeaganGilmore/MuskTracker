"""Model training CLI."""

import json
from datetime import datetime, timedelta, timezone

import click

from musktracker.evaluation import ModelEvaluator
from musktracker.features import FeatureEngineer
from musktracker.logging_config import get_logger, setup_logging
from musktracker.models.hawkes import HawkesModel
from musktracker.models.negative_binomial import NegativeBinomialModel
from musktracker.models.sarimax import SARIMAXModel

logger = get_logger(__name__)


@click.command()
@click.option(
    "--model",
    type=click.Choice(["negative_binomial", "hawkes", "sarimax", "all"]),
    default="all",
    help="Model to train",
)
@click.option("--backtest-windows", type=int, default=12, help="Number of backtest windows")
@click.option("--train-days", type=int, default=30, help="Training days per window")
@click.option("--output", type=click.Path(), default="backtest_results.json", help="Output file")
def train(model: str, backtest_windows: int, train_days: int, output: str) -> None:
    """Train models with rolling backtest evaluation.

    Examples:
        python -m musktracker.cli.train --model hawkes --backtest-windows 12
        python -m musktracker.cli.train --model all
    """
    setup_logging()

    # Initialize feature engineer
    feature_engineer = FeatureEngineer()
    evaluator = ModelEvaluator()

    # Define evaluation period (last 60 days of data)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=60)

    # Ensure time buckets are computed
    logger.info("Computing time buckets")
    feature_engineer.compute_time_buckets(start_date, end_date, granularity="hourly")

    # Select models to train
    models = []
    if model == "all":
        models = [
            NegativeBinomialModel(),
            HawkesModel(),
            SARIMAXModel(),
        ]
    elif model == "negative_binomial":
        models = [NegativeBinomialModel()]
    elif model == "hawkes":
        models = [HawkesModel()]
    elif model == "sarimax":
        models = [SARIMAXModel()]

    # Train and evaluate each model
    results = {}

    for m in models:
        logger.info("Training model", model=m.name)
        click.echo(f"\nTraining {m.name}...")

        try:
            backtest_results = evaluator.rolling_backtest(
                model=m,
                start_date=start_date,
                end_date=end_date,
                n_windows=backtest_windows,
                train_days=train_days,
                test_hours=24,
            )

            results[m.name] = backtest_results

            click.echo(f"  RMSE: {backtest_results['mean_rmse']:.2f} ± {backtest_results['std_rmse']:.2f}")
            click.echo(f"  MAE:  {backtest_results['mean_mae']:.2f} ± {backtest_results['std_mae']:.2f}")
            click.echo(f"  MAPE: {backtest_results['mean_mape']:.2f}% ± {backtest_results['std_mape']:.2f}%")

        except Exception as e:
            logger.error("Model training failed", model=m.name, error=str(e))
            click.echo(f"  Error: {str(e)}", err=True)

    # Save results
    with open(output, "w") as f:
        json.dump(results, f, indent=2, default=str)

    logger.info("Training completed", output_file=output)
    click.echo(f"\nResults saved to {output}")


if __name__ == "__main__":
    train()

