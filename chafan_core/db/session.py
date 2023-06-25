from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from chafan_core.app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_SESSION_POOL_SIZE,
    max_overflow=settings.DB_SESSION_POOL_MAX_OVERFLOW_SIZE,
)

read_engine = engine
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
ReadSessionLocal = SessionLocal
