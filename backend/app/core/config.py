from __future__ import annotations

from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    project_name: str = "Potilastieto Backend"
    database_url: str = Field(
        default="sqlite:///./potilastieto.db",
        description="SQLModel compatible database URI",
    )
    jwt_secret_key: str = Field(default="change-me", description="JWT signing secret")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    background_cleanup_interval_seconds: int = 60 * 30  # every 30 minutes
    first_superuser: str = "admin"
    first_superuser_password: str = "admin123"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
