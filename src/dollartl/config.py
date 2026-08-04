from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Dollar TL"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    telegram_bot_token: SecretStr = SecretStr("")
    telegram_webhook_secret: SecretStr = SecretStr("")
    telegram_webhook_base_url: str = ""
    admin_telegram_id: int = 2096975784

    database_url: str = "postgresql+asyncpg://dollartl:dollartl@localhost:5432/dollartl"
    database_url_sync: str = "postgresql+psycopg://dollartl:dollartl@localhost:5432/dollartl"
    postgres_dsn: SecretStr = SecretStr(
        "postgresql://dollartl:dollartl@localhost:5432/dollartl"
    )
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint_url: str | None = None
    s3_region: str = "auto"
    s3_access_key_id: SecretStr = SecretStr("")
    s3_secret_access_key: SecretStr = SecretStr("")
    s3_bucket: str = "dollartl"
    s3_backup_bucket: str = "dollartl-backups"
    s3_force_path_style: bool = True

    backup_encryption_key: SecretStr = SecretStr("")
    backup_cron: str = "0 4 * * 0"
    app_timezone: str = "Asia/Yerevan"

    adult_consent_version: int = 1
    ban_notice_interval_hours: int = 6
    maintenance_mode: bool = False

    @field_validator("app_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator("adult_consent_version", "ban_notice_interval_hours")
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value < 1:
            raise ValueError("value must be positive")
        return value

    @property
    def webhook_url(self) -> str:
        return f"{self.telegram_webhook_base_url.rstrip('/')}/telegram/webhook"


@lru_cache
def get_settings() -> Settings:
    return Settings()
