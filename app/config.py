"""
Application configuration using pydantic-settings.
Settings are loaded from environment variables with validation.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Environment Variables:
        WEBHOOK_SECRET: Secret key for webhook authentication (REQUIRED)
        DATABASE_URL: Database connection string (optional, has default)
        LOG_LEVEL: Logging level (optional, defaults to INFO)
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # Required field - will raise ValidationError if missing or empty
    WEBHOOK_SECRET: str = Field(
        ...,
        min_length=1,
        description="Secret key for webhook authentication. Must not be empty."
    )
    
    # Optional fields with defaults
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/app.db",
        description="Database connection URL"
    )
    
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    
    @field_validator("WEBHOOK_SECRET")
    @classmethod
    def validate_webhook_secret(cls, v: str) -> str:
        """Ensure WEBHOOK_SECRET is not empty after stripping whitespace."""
        if not v or not v.strip():
            raise ValueError(
                "WEBHOOK_SECRET must not be empty. "
                "Please set the WEBHOOK_SECRET environment variable."
            )
        return v.strip()
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure LOG_LEVEL is a valid logging level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(
                f"LOG_LEVEL must be one of {valid_levels}, got '{v}'"
            )
        return v_upper


# Singleton instance to be imported throughout the application
settings = Settings()
