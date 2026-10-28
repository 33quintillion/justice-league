from alembic import context
from sqlalchemy import create_engine

from app.config import get_settings
from app.db import Base
from app import models  # noqa: F401  (registers tables)

target_metadata = Base.metadata


def run() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
