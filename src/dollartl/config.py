from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Dollar TL"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    telegram_bot_token: SecretStr = SecretStr("")
    telegram_webhook_secret: SecretStr = SecretStr("")
    telegram_webhook_base_url: str = ""
    telegram_bot_username: str = ""
    telegram_channel_username: str = "@dollartranslate"
    telegram_api_base_url: str = ""
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
    catalogue_page_size: int = 8
    channel_posts_enabled: bool = True
    worker_poll_seconds: int = 5
    user_upload_max_bytes: int = 20 * 1024 * 1024

    boosty_enabled: bool = False
    boosty_api_base_url: str = "https://api.boosty.to"
    boosty_blog_name: str = "domnekromanta"
    boosty_tier_id: str = "4041120"
    boosty_membership_url: str = (
        "https://boosty.to/domnekromanta/purchase/4041120?ssource=DIRECT&share=subscription_link"
    )
    boosty_messages_url: str = "https://boosty.to/app/messages"
    boosty_donate_url: str = (
        "https://boosty.to/domnekromanta/single-payment/donation/818248/target?share=target_link"
    )
    boosty_access_token: SecretStr = SecretStr("")
    boosty_refresh_token: SecretStr = SecretStr("")
    boosty_device_id: SecretStr = SecretStr("")
    boosty_credential_key: SecretStr = SecretStr("")
    boosty_code_ttl_minutes: int = 30
    boosty_verification_poll_seconds: int = 30
    boosty_membership_sync_seconds: int = 900
    boosty_grace_days: int = 7
    boosty_request_timeout_seconds: int = 20
    boosty_contacts_limit: int = 100
    boosty_subscribers_page_size: int = 100
    boosty_max_subscriber_pages: int = 100
    boosty_circuit_breaker_failures: int = 3
    boosty_circuit_breaker_seconds: int = 300

    suggestion_rules_version: int = 1
    suggestion_standard_monthly_limit: int = 1
    suggestion_vip_monthly_limit: int = 5
    suggestion_standard_chapter_limit: int = 200
    suggestion_source_max: int = 10
    suggestion_archive_max_entries: int = 500
    suggestion_archive_max_unpacked_bytes: int = 200 * 1024 * 1024
    suggestion_antivirus_command: str = ""

    maintenance_mode: bool = False

    @field_validator("app_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @field_validator(
        "adult_consent_version",
        "ban_notice_interval_hours",
        "catalogue_page_size",
        "worker_poll_seconds",
        "user_upload_max_bytes",
        "boosty_code_ttl_minutes",
        "boosty_verification_poll_seconds",
        "boosty_membership_sync_seconds",
        "boosty_grace_days",
        "boosty_request_timeout_seconds",
        "boosty_contacts_limit",
        "boosty_subscribers_page_size",
        "boosty_max_subscriber_pages",
        "boosty_circuit_breaker_failures",
        "boosty_circuit_breaker_seconds",
        "suggestion_rules_version",
        "suggestion_standard_monthly_limit",
        "suggestion_vip_monthly_limit",
        "suggestion_standard_chapter_limit",
        "suggestion_source_max",
        "suggestion_archive_max_entries",
        "suggestion_archive_max_unpacked_bytes",
    )
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        if value < 1:
            raise ValueError("value must be positive")
        return value

    @property
    def webhook_url(self) -> str:
        return f"{self.telegram_webhook_base_url.rstrip('/')}/telegram/webhook"

    @property
    def normalized_bot_username(self) -> str:
        return self.telegram_bot_username.lstrip("@")


@lru_cache
def get_settings() -> Settings:
    return Settings()
