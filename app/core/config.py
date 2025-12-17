from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    PROJECT_NAME: str = "CAPS Job Portal API"
    ENVIRONMENT: str = "local"
    DEBUG: bool = True

    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_SERVER: str = "database-1.cmdw6osie4vg.us-east-1.rds.amazonaws.com"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres_mybizai"
    POSTGRES_PASSWORD: str = "MYqiEQVO7TmEfsNB7faj"
    POSTGRES_DB: str = "capsjobportal"

    SQLALCHEMY_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_PRE_PING: bool = True

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Security
    SECRET_KEY: str = "change-this-secret-key"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    JWT_ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = ["http://localhost:3000/"]

    # File storage
    MEDIA_ROOT: str = "media"

    # Initial superuser (bootstrap admin)
    FIRST_SUPERUSER_EMAIL: Optional[str] = "ojusoni@gmail.com"
    FIRST_SUPERUSER_PASSWORD: Optional[str] = "holamigo"
    FIRST_SUPERUSER_FULL_NAME: Optional[str] = "ojus soni"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
