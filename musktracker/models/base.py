"""Base interface for statistical models."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

import numpy as np
import pandas as pd


class BaseModel(ABC):
    """Abstract base class for tweet volume models."""

    def __init__(self, name: str) -> None:
        """Initialize base model.

        Args:
            name: Model name identifier
        """
        self.name = name
        self.is_fitted = False
        self.hyperparameters: dict[str, Any] = {}

    @abstractmethod
    def fit(
        self,
        timestamps: np.ndarray,
        counts: np.ndarray,
        exog: Optional[pd.DataFrame] = None,
    ) -> None:
        """Fit the model to historical data.

        Args:
            timestamps: Array of datetime objects
            counts: Array of tweet counts
            exog: Optional exogenous features DataFrame
        """
        pass

    @abstractmethod
    def predict(
        self,
        timestamps: np.ndarray,
        exog: Optional[pd.DataFrame] = None,
    ) -> tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray]]:
        """Generate predictions for future timestamps.

        Args:
            timestamps: Array of future datetime objects
            exog: Optional exogenous features DataFrame

        Returns:
            Tuple of (predictions, lower_bounds, upper_bounds)
        """
        pass

    @abstractmethod
    def get_hyperparameters(self) -> dict[str, Any]:
        """Get model hyperparameters.

        Returns:
            Dictionary of hyperparameter names and values
        """
        pass

    def compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> dict[str, float]:
        """Compute evaluation metrics.

        Args:
            y_true: True counts
            y_pred: Predicted counts

        Returns:
            Dictionary of metric names and values
        """
        from sklearn.metrics import mean_absolute_error, mean_squared_error

        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = mean_absolute_error(y_true, y_pred)

        # Mean Absolute Percentage Error (avoid division by zero)
        mask = y_true > 0
        if mask.sum() > 0:
            mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100
        else:
            mape = np.nan

        return {
            "rmse": float(rmse),
            "mae": float(mae),
            "mape": float(mape),
        }

