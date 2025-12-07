import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# -----------------------------------------------------------
# 加入專案根目錄到 sys.path
# 這樣才 import 得到 core.db
# -----------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# -----------------------------------------------------------
# Import 你的 Models 和 Config
# 注意：一定要 Import 具體的 Model (如 PaymentEvent)，
# 不然 SQLModel.metadata 會是空的！
# -----------------------------------------------------------
from sqlmodel import SQLModel  # noqa: E402

from core.database import DATABASE_URL  # noqa: E402

# -----------------------------------------------------------
# 設定 Metadata
# 告訴 Alembic 去哪裡比對資料庫結構
# -----------------------------------------------------------
target_metadata = SQLModel.metadata

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# -----------------------------------------------------------
# 覆蓋 sqlalchemy.url
# 用我們 Python 裡設定好的 DATABASE_URL，而不是 ini 裡的死字串
# -----------------------------------------------------------
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    # 這裡建立 engine
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,  # 記得這裡也要傳
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
