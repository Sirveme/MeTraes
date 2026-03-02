"""
Metraes.com — Database Configuration
Base declarativa, engine y session para PostgreSQL en Railway.
DB PROPIA de Metraes — NO comparte con QueVendi ni otros SaaS.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos de Metraes."""
    pass


engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,           # Restaurantes de alto volumen = muchas conexiones
    max_overflow=30,        # Picos en horas punta (200+ comensales)
    pool_pre_ping=True,     # Reconexión automática si Railway reinicia DB
    pool_recycle=300,       # Reciclar conexiones cada 5 min (internet Iquitos)
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency de FastAPI para obtener sesión de DB."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()