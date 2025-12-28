"""Database migration CLI."""

import click
from alembic import command
from alembic.config import Config

from musktracker.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


@click.command()
@click.argument("direction", type=click.Choice(["up", "down", "current"]))
@click.option("--revision", default="head", help="Target revision")
def migrate(direction: str, revision: str) -> None:
    """Run database migrations.

    Examples:
        python -m musktracker.cli.migrate up
        python -m musktracker.cli.migrate down --revision -1
        python -m musktracker.cli.migrate current
    """
    setup_logging()

    # Load Alembic config
    alembic_cfg = Config("alembic.ini")

    try:
        if direction == "up":
            logger.info("Running migrations", target=revision)
            command.upgrade(alembic_cfg, revision)
            logger.info("Migrations completed successfully")

        elif direction == "down":
            logger.info("Reverting migrations", target=revision)
            command.downgrade(alembic_cfg, revision)
            logger.info("Downgrade completed successfully")

        elif direction == "current":
            logger.info("Checking current migration status")
            command.current(alembic_cfg)

    except Exception as e:
        logger.error("Migration failed", error=str(e))
        raise click.ClickException(str(e))


if __name__ == "__main__":
    migrate()

