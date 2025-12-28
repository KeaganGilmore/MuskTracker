"""Negative Binomial regression model for count data."""

from typing import Any, Optional

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.discrete.discrete_model import NegativeBinomial

from musktracker.models.base import BaseModel


class NegativeBinomialModel(BaseModel):
    """Negative Binomial GLM for overdispersed count data.

    Handles high variance in tweet counts via gamma-Poisson mixture.
    Uses log link function and supports exogenous predictors.
    """

    def __init__(self) -> None:
        """Initialize Negative Binomial model."""
        super().__init__(name="negative_binomial")
        self.model: Optional[NegativeBinomial] = None
        self.result: Optional[Any] = None
        self.alpha: float = 1.0  # Dispersion parameter

    def fit(
        self,
        timestamps: np.ndarray,
        counts: np.ndarray,
        exog: Optional[pd.DataFrame] = None,
    ) -> None:
        """Fit Negative Binomial model.

        Args:
            timestamps: Array of datetime objects
            counts: Array of tweet counts
            exog: Optional exogenous features DataFrame
        """
        # Prepare exogenous features
        if exog is None:
            # Use time-based features only
            X = self._create_time_features(timestamps)
        else:
            X = exog.copy()

        # Add constant
        X = sm.add_constant(X)

        # Fit model
        self.model = sm.NegativeBinomial(counts, X)
        self.result = self.model.fit(disp=False)

        # Store dispersion parameter
        self.alpha = self.result.params.get("alpha", 1.0)

        self.is_fitted = True

        # Store hyperparameters
        self.hyperparameters = {
            "alpha": float(self.alpha),
            "n_features": X.shape[1],
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

        # Prepare features
        if exog is None:
            X = self._create_time_features(timestamps)
        else:
            X = exog.copy()

        # Add constant
        X = sm.add_constant(X)

        # Get predictions
        predictions = self.result.predict(X)

        # Compute 95% confidence intervals
        # For NB, variance = mu + alpha * mu^2
        variance = predictions + self.alpha * (predictions ** 2)
        std_error = np.sqrt(variance)

        lower = predictions - 1.96 * std_error
        upper = predictions + 1.96 * std_error

        # Ensure non-negative
        lower = np.maximum(lower, 0)

        return predictions, lower, upper

    def get_hyperparameters(self) -> dict[str, Any]:
        """Get model hyperparameters."""
        return self.hyperparameters

    def _create_time_features(self, timestamps: np.ndarray) -> pd.DataFrame:
        """Create time-based features from timestamps.

        Args:
            timestamps: Array of datetime objects

        Returns:
            DataFrame with time features
        """
        df = pd.DataFrame()

        # Hour of day (cyclical encoding)
        hours = np.array([ts.hour for ts in timestamps])
        df["hour_sin"] = np.sin(2 * np.pi * hours / 24)
        df["hour_cos"] = np.cos(2 * np.pi * hours / 24)

        # Day of week (cyclical encoding)
        days = np.array([ts.weekday() for ts in timestamps])
        df["day_sin"] = np.sin(2 * np.pi * days / 7)
        df["day_cos"] = np.cos(2 * np.pi * days / 7)

        # Weekend indicator
        df["is_weekend"] = (days >= 5).astype(int)

        # Linear time trend
        df["time_index"] = np.arange(len(timestamps))

        return df

