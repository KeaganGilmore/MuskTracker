"""Model evaluation and backtesting."""

from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

from musktracker.features import FeatureEngineer
from musktracker.logging_config import get_logger
from musktracker.models.base import BaseModel

logger = get_logger(__name__)


class ModelEvaluator:
    """Rolling backtest and evaluation for time-series models."""

    def __init__(self) -> None:
        """Initialize model evaluator."""
        self.feature_engineer = FeatureEngineer()
        self.logger = logger.bind(component="model_evaluator")

    def rolling_backtest(
        self,
        model: BaseModel,
        start_date: datetime,
        end_date: datetime,
        n_windows: int = 12,
        train_days: int = 30,
        test_hours: int = 24,
    ) -> dict[str, Any]:
        """Perform rolling window backtesting.

        Args:
            model: Model instance to evaluate
            start_date: Start of evaluation period (UTC)
            end_date: End of evaluation period (UTC)
            n_windows: Number of rolling windows
            train_days: Days of training data per window
            test_hours: Hours to forecast ahead

        Returns:
            Dictionary with evaluation results
        """
        self.logger.info(
            "Starting rolling backtest",
            model=model.name,
            n_windows=n_windows,
            train_days=train_days,
            test_hours=test_hours,
        )

        # Compute window size
        total_period = (end_date - start_date).total_seconds() / 3600  # hours
        window_step = int(total_period / n_windows)

        results = []

        for i in range(n_windows):
            # Define window
            test_start = start_date + timedelta(hours=i * window_step)
            train_start = test_start - timedelta(days=train_days)
            test_end = test_start + timedelta(hours=test_hours)

            if test_end > end_date:
                break

            self.logger.info(
                "Processing backtest window",
                window=i + 1,
                train_start=train_start.isoformat(),
                test_start=test_start.isoformat(),
            )

            # Get training data
            train_df = self.feature_engineer.get_bucket_counts(
                train_start, test_start, granularity="hourly"
            )

            if train_df.empty or len(train_df) < 24:
                self.logger.warning("Insufficient training data", window=i + 1)
                continue

            # Get test data
            test_df = self.feature_engineer.get_bucket_counts(
                test_start, test_end, granularity="hourly"
            )

            if test_df.empty:
                self.logger.warning("No test data", window=i + 1)
                continue

            try:
                # Fit model
                model.fit(
                    timestamps=train_df["timestamp"].values,
                    counts=train_df["count"].values,
                )

                # Predict
                predictions, lower, upper = model.predict(
                    timestamps=test_df["timestamp"].values,
                )

                # Compute metrics
                metrics = model.compute_metrics(
                    y_true=test_df["count"].values,
                    y_pred=predictions,
                )

                results.append({
                    "window": i + 1,
                    "train_start": train_start,
                    "test_start": test_start,
                    "test_end": test_end,
                    "rmse": metrics["rmse"],
                    "mae": metrics["mae"],
                    "mape": metrics["mape"],
                })

            except Exception as e:
                self.logger.error("Error in backtest window", window=i + 1, error=str(e))
                continue

        if not results:
            self.logger.error("No successful backtest windows")
            return {
                "model": model.name,
                "n_windows_completed": 0,
                "mean_rmse": np.nan,
                "mean_mae": np.nan,
                "mean_mape": np.nan,
            }

        # Aggregate results
        df_results = pd.DataFrame(results)

        summary = {
            "model": model.name,
            "n_windows_completed": len(results),
            "mean_rmse": float(df_results["rmse"].mean()),
            "std_rmse": float(df_results["rmse"].std()),
            "mean_mae": float(df_results["mae"].mean()),
            "std_mae": float(df_results["mae"].std()),
            "mean_mape": float(df_results["mape"].mean()),
            "std_mape": float(df_results["mape"].std()),
            "window_results": results,
        }

        self.logger.info(
            "Completed rolling backtest",
            model=model.name,
            windows=len(results),
            mean_rmse=summary["mean_rmse"],
            mean_mae=summary["mean_mae"],
        )

        return summary

    def detect_regime_shift(
        self,
        start_date: datetime,
        end_date: datetime,
        window_hours: int = 168,  # 1 week
        threshold_std: float = 2.0,
    ) -> list[dict[str, Any]]:
        """Detect regime shifts via rolling variance.

        Args:
            start_date: Start of analysis period (UTC)
            end_date: End of analysis period (UTC)
            window_hours: Rolling window size in hours
            threshold_std: Std deviations for shift detection

        Returns:
            List of detected regime shifts
        """
        # Get hourly counts
        df = self.feature_engineer.get_bucket_counts(
            start_date, end_date, granularity="hourly"
        )

        if df.empty or len(df) < window_hours:
            return []

        # Compute rolling statistics
        df = df.set_index("timestamp").sort_index()
        df["rolling_mean"] = df["count"].rolling(window=window_hours, min_periods=24).mean()
        df["rolling_std"] = df["count"].rolling(window=window_hours, min_periods=24).std()

        # Detect shifts: when variance changes significantly
        df["variance_ratio"] = df["rolling_std"] / df["rolling_std"].shift(window_hours)

        shifts = []
        for idx, row in df.iterrows():
            if pd.notna(row["variance_ratio"]):
                if row["variance_ratio"] > (1 + threshold_std) or row["variance_ratio"] < (1 / (1 + threshold_std)):
                    shifts.append({
                        "timestamp": idx,
                        "variance_ratio": float(row["variance_ratio"]),
                        "rolling_mean": float(row["rolling_mean"]),
                        "rolling_std": float(row["rolling_std"]),
                    })

        self.logger.info("Detected regime shifts", count=len(shifts))
        return shifts

