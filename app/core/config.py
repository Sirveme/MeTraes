"""
Metraes.com — Application Settings
Simplificado para arranque inmediato.
"""

import os
from pathlib import Path

# Cargar .env manualmente (sin depender de pydantic-settings)
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


class Settings:
    APP_NAME: str = "Metraes.com"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://localhost/metraes")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "metraes_dev_secret_2026")
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    FACTURALO_API_URL: str = os.getenv("FACTURALO_API_URL", "https://facturalo.pro")
    WS_HEARTBEAT_SECONDS: int = 30


settings = Settings()