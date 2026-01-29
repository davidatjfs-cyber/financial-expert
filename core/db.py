from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def get_app_data_dir() -> Path:
    override = (os.environ.get("APP_DATA_DIR") or "").strip()
    if override:
        data_dir = Path(override)
    else:
        base = Path(__file__).resolve().parent.parent
        data_dir = base / ".data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    return get_app_data_dir() / "financial_reports.db"


_db_url = (os.environ.get("DATABASE_URL") or "").strip()
if _db_url:
    # Some providers return "postgres://" but SQLAlchemy expects "postgresql://"
    if _db_url.startswith("postgres://"):
        _db_url = "postgresql://" + _db_url[len("postgres://"):]
    _engine = create_engine(_db_url)
else:
    _engine = create_engine(
        f"sqlite:///{get_db_path().as_posix()}",
        connect_args={"check_same_thread": False},
    )
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope():
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
