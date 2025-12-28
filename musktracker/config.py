"""Application configuration."""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class Config:
    """Application configuration from environment variables."""

    # Database configuration
    database_url: str

    # X API credentials
    x_api_bearer_token: Optional[str]
    x_api_consumer_key: Optional[str]
    x_api_consumer_secret: Optional[str]
    x_api_access_token: Optional[str]
    x_api_access_token_secret: Optional[str]

    # Target user
    target_user_id: str = "44196397"  # @elonmusk
    target_username: str = "elonmusk"

    # Application settings
    log_level: str = "INFO"
    environment: str = "development"


def get_config() -> Config:
    """Get application configuration from environment.

    Returns:
        Config instance

    Raises:
        ValueError: If required configuration is missing
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Default to SQLite for local development
        database_url = "sqlite:///./musktracker.db"

    return Config(
        database_url=database_url,
        x_api_bearer_token=os.getenv("X_API_BEARER_TOKEN"),
        x_api_consumer_key=os.getenv("X_API_CONSUMER_KEY"),
        x_api_consumer_secret=os.getenv("X_API_CONSUMER_SECRET"),
        x_api_access_token=os.getenv("X_API_ACCESS_TOKEN"),
        x_api_access_token_secret=os.getenv("X_API_ACCESS_TOKEN_SECRET"),
        target_user_id=os.getenv("TARGET_USER_ID", "44196397"),
        target_username=os.getenv("TARGET_USERNAME", "elonmusk"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        environment=os.getenv("ENVIRONMENT", "development"),
    )

