"""Basic smoke tests for MuskTracker components."""

import pytest
from datetime import datetime, timedelta, timezone


def test_config_loads():
    """Test configuration loading."""
    from musktracker.config import get_settings

    settings = get_settings()
    assert settings is not None
    assert settings.timezone == "UTC"
    assert settings.x_target_username == "elonmusk"


def test_database_models():
    """Test database model definitions."""
    from musktracker.db.models import RawTweet, TimeBucket, ExogenousEvent, Feature

    # Test model instantiation
    now = datetime.now(timezone.utc)

    tweet = RawTweet(
        tweet_id="123456789",
        created_at=now,
        source="test",
        ingest_time=now,
    )
    assert tweet.tweet_id == "123456789"

    bucket = TimeBucket(
        bucket_start=now,
        bucket_end=now + timedelta(hours=1),
        granularity="hourly",
        tweet_count=10,
    )
    assert bucket.granularity == "hourly"

    event = ExogenousEvent(
        name="Test Event",
        event_start=now,
        event_end=now + timedelta(hours=1),
        intensity=0.5,
        source="test",
    )
    assert event.intensity == 0.5


def test_feature_engineer_imports():
    """Test feature engineer can be imported."""
    from musktracker.features import FeatureEngineer

    fe = FeatureEngineer()
    assert fe is not None


def test_models_import():
    """Test models can be imported."""
    from musktracker.models.negative_binomial import NegativeBinomialModel
    from musktracker.models.hawkes import HawkesModel
    from musktracker.models.sarimax import SARIMAXModel

    nb = NegativeBinomialModel()
    assert nb.name == "negative_binomial"

    hawkes = HawkesModel()
    assert hawkes.name == "hawkes"

    sarimax = SARIMAXModel()
    assert sarimax.name == "sarimax"


def test_evaluator_import():
    """Test evaluator can be imported."""
    from musktracker.evaluation import ModelEvaluator

    evaluator = ModelEvaluator()
    assert evaluator is not None


def test_event_enricher():
    """Test event enricher basic functionality."""
    from musktracker.enrich import EventEnricher

    enricher = EventEnricher()

    # Test intensity computation with no events
    now = datetime.now(timezone.utc)
    intensity, count = enricher.compute_window_intensity(
        now - timedelta(hours=1),
        now,
    )
    assert intensity == 0.0
    assert count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

