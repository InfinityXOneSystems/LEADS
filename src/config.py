"""Application configuration."""
import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite:///./leads.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_email: str = "noreply@xps-intelligence.com"
    from_name: str = "XPS Intelligence Team"

    # External APIs
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    hunter_io_api_key: str = ""
    clearbit_api_key: str = ""
    google_maps_api_key: str = ""

    # JWT
    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # App
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True

    # Frontend
    frontend_url: str = "https://xps-intelligence.com"

    # Slack
    slack_webhook_url: str = ""

    # Scoring thresholds
    hot_score_threshold: int = 75
    warm_score_threshold: int = 50

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
