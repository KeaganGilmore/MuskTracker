"""Logging configuration for MuskTracker."""

import logging
import sys
from typing import Any, Optional


# Global logging configuration
_logging_configured = False


class StructuredLogger:
    """Logger wrapper for structured logging."""

    def __init__(self, name: str):
        """Initialize structured logger.

        Args:
            name: Logger name (usually __name__)
        """
        self.logger = logging.getLogger(name)
        self._context = {}

    def bind(self, **kwargs: Any) -> "StructuredLogger":
        """Create a new logger with bound context variables.

        Args:
            **kwargs: Context key-value pairs

        Returns:
            New logger instance with context
        """
        new_logger = StructuredLogger(self.logger.name)
        new_logger._context = {**self._context, **kwargs}
        return new_logger

    def _format_message(self, msg: str, **kwargs: Any) -> str:
        """Format message with context.

        Args:
            msg: Log message
            **kwargs: Additional context

        Returns:
            Formatted message string
        """
        all_context = {**self._context, **kwargs}
        if all_context:
            context_str = " ".join(f"{k}={v}" for k, v in all_context.items())
            return f"{msg} | {context_str}"
        return msg

    def debug(self, msg: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(self._format_message(msg, **kwargs))

    def info(self, msg: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(self._format_message(msg, **kwargs))

    def warning(self, msg: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(self._format_message(msg, **kwargs))

    def error(self, msg: str, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(self._format_message(msg, **kwargs))

    def critical(self, msg: str, **kwargs: Any) -> None:
        """Log critical message."""
        self.logger.critical(self._format_message(msg, **kwargs))

    def exception(self, msg: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self.logger.exception(self._format_message(msg, **kwargs))


def setup_logging(level: Optional[str] = None) -> None:
    """Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
              Defaults to INFO
    """
    global _logging_configured

    if _logging_configured:
        return

    log_level = level or "INFO"
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Reduce noise from libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)

    _logging_configured = True


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)

