import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from logging.config import fileConfig

from alembic import context

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

from sqlalchemy import create_engine, text

from app.config import Config

target_metadata = None


def _db_path() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url and url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    return Config.DB_PATH


def _db_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return f"sqlite:///{Config.DB_PATH}"


def run_migrations_offline():
    context.configure(url=_db_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(_db_url())
    with engine.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
        connection.execute(text("PRAGMA foreign_keys=ON"))
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
