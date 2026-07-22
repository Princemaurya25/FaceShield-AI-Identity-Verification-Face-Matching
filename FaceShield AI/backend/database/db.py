import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from backend.config import settings

logger = logging.getLogger(__name__)

# Parse database URL
db_url = settings.DATABASE_URL
if db_url.startswith("postgresql+asyncpg"):
    # Since we are using synchronous SQLAlchemy for simplicity and reliability,
    # convert postgresql+asyncpg:// to postgresql:// if needed.
    db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
elif db_url.startswith("sqlite+aiosqlite"):
    db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")

# SQLite specific config
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(db_url, connect_args=connect_args)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info(f"Database connected using: {db_url.split('@')[-1] if '@' in db_url else db_url}")
except Exception as e:
    logger.error(f"Failed to connect to database URL {db_url}: {e}. Falling back to SQLite.")
    fallback_url = "sqlite:///./faceshield.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
