"""SARIMAX baseline model for seasonal time series."""

from typing import Any, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

from musktracker.models.base import BaseModel


class SARIMAXModel(BaseModel):
    """Seasonal ARIMA with exogenous regressors.

    Baseline model capturing trend, seasonality, and external variables.
    Good for comparison against more sophisticated count models.
    """

    def __init__(
        self,
        order: tuple[int, int, int] = (2, 0, 2),
        seasonal_order: tuple[int, int, int, int] = (1, 0, 1, 24),
    ) -> None:
        """Initialize SARIMAX model.

        Args:
            order: (p, d, q) for ARIMA
            seasonal_order: (P, D, Q, s) for seasonal component
        """
        super().__init__(name="sarimax")
        self.order = order
        self.seasonal_order = seasonal_order
        self.model: Optional[Any] = None
        self.result: Optional[Any] = None

    def fit(
        self,
        timestamps: np.ndarray,
        counts: np.ndarray,
        exog: Optional[pd.DataFrame] = None,
    ) -> None:
        """Fit SARIMAX model.

        Args:
            timestamps: Array of datetime objects
            counts: Array of tweet counts
            exog: Optional exogenous features DataFrame
        """
        # Create time series
        ts = pd.Series(counts, index=pd.DatetimeIndex(timestamps))

        # Fit model
        self.model = SARIMAX(
            ts,
            exog=exog,
            order=self.order,
            seasonal_order=self.seasonal_order,
            enforce_stationarity=False,
            enforce_invertibility=False,
        )

        self.result = self.model.fit(disp=False, maxiter=100)

        self.is_fitted = True

        # Store hyperparameters
        self.hyperparameters = {
            "order": self.order,
            "seasonal_order": self.seasonal_order,
            "aic": float(self.result.aic),
            "bic": float(self.result.bic),
            "log_likelihood": float(self.result.llf),
        }

    def predict(
        self,
        timestamps: np.ndarray,
        exog: Optional[pd.DataFrame] = None,
    ) -> tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """Generate predictions with confidence intervals.

        Args:
            timestamps: Array of future datetime objects
            exog: Optional exogenous features DataFrame

        Returns:
            Tuple of (predictions, lower_bounds, upper_bounds)
        """
        if not self.is_fitted or self.result is None:
            raise RuntimeError("Model must be fitted before prediction")

        # Get forecast
        steps = len(timestamps)
        forecast = self.result.get_forecast(steps=steps, exog=exog)

        predictions = forecast.predicted_mean.values

        # Get confidence intervals
        conf_int = forecast.conf_int(alpha=0.05)
        lower = conf_int.iloc[:, 0].values
        upper = conf_int.iloc[:, 1].values

        # Ensure non-negative (counts)
        predictions = np.maximum(predictions, 0)
        lower = np.maximum(lower, 0)
        upper = np.maximum(upper, 0)

        return predictions, lower, upper

    def get_hyperparameters(self) -> dict[str, Any]:
        """Get model hyperparameters."""
        return self.hyperparameters

