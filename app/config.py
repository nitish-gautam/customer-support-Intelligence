"""
Application Configuration Management.

This module provides centralized configuration management for the Customer
Support Intelligence API using Pydantic Settings. It follows the 12-factor
app methodology for environment-based configuration, providing type validation,
environment variable parsing, and secure defaults.

Key Features:
- Environment variable-based configuration
- Type validation and conversion
- Secure defaults for production environments
- Database connection string management
- AI/ML service configuration
- Rate limiting and CORS settings

Author: Customer Support Intelligence Team
Version: 1.0.0
"""

from typing import List, Optional, Union
from functools import lru_cache

from pydantic import AnyHttpUrl, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings configuration class.

    This class defines all application configuration parameters with type
    validation, default values, and environment variable mapping. It uses
    Pydantic Settings for automatic validation and environment variable
    parsing.

    Configuration Sources (in order of precedence):
    1. Environment variables
    2. .env file
    3. Default values defined in this class

    Note:
        All environment variables are case-insensitive and automatically
        mapped to the corresponding field names.
    """

    # Pydantic model configuration for environment variable handling
    model_config = SettingsConfigDict(
        env_file=".env",  # Load variables from .env file
        env_file_encoding="utf-8",  # File encoding for .env file
        case_sensitive=False,  # Allow case-insensitive env vars
    )

    # Core application settings
    app_name: str = "Customer Support API"  # Application display name
    app_version: str = "1.0.0"  # Application version
    debug: bool = False  # Debug mode flag
    environment: str = "production"  # Deployment environment

    # API configuration
    api_v1_prefix: str = "/api/v1"  # API version prefix

    # Database configuration
    database_url: PostgresDsn  # PostgreSQL connection URL (required)
    db_pool_size: int = 20  # Connection pool size
    db_max_overflow: int = 0  # Maximum overflow connections
    db_echo: bool = False  # Enable SQL query logging

    # Security settings
    secret_key: str  # Secret key for cryptographic operations (required)
    access_token_expire_minutes: int = 30  # JWT token expiration time

    # Cross-Origin Resource Sharing (CORS) configuration
    cors_origins: List[AnyHttpUrl] = []  # Allowed CORS origins

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """
        Parse CORS origins from environment variable or list.

        Supports both comma-separated string format and list format for
        CORS origins. This allows flexible configuration via environment
        variables while maintaining type safety.

        Args:
            v: CORS origins as string (comma-separated) or list of strings.

        Returns:
            Processed CORS origins as list of strings.

        Raises:
            ValueError: If the input format is invalid.

        Examples:
            "http://localhost:3000,https://example.com" ->
                ["http://localhost:3000", "https://example.com"]
            ["http://localhost:3000"] -> ["http://localhost:3000"]
        """
        if isinstance(v, str) and not v.startswith("["):
            # Parse comma-separated string into list
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            # Return as-is if already in correct format
            return v
        raise ValueError(f"Invalid CORS origins format: {v}")

    # AI/ML service configuration
    openai_api_key: Optional[str] = None  # OpenAI API key (optional)
    # Hugging Face API key (optional)
    huggingface_api_key: Optional[str] = None
    ai_model: str = "gpt-4o"  # AI model identifier
    ai_temperature: float = 0.3  # AI response randomness (0.0-1.0)
    ai_max_tokens: int = 150  # Maximum AI response tokens

    # Dataset integration configuration
    # Hugging Face dataset
    dataset_name: str = "Tobi-Bueck/customer-support-tickets"
    dataset_cache_dir: str = "./data/cache"  # Local dataset cache

    # Logging configuration
    log_level: str = "INFO"  # Logging level
    log_format: str = "json"  # Log output format

    # Rate limiting configuration
    rate_limit_enabled: bool = True  # Enable rate limiting
    rate_limit_requests: int = 100  # Requests per period
    rate_limit_period: int = 60  # Period in seconds

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """
        Validate deployment environment setting.

        Ensures the environment is set to one of the supported values,
        which helps with environment-specific behavior and security settings.

        Args:
            v: Environment string value.

        Returns:
            Validated environment string.

        Raises:
            ValueError: If environment is not one of the allowed values.
        """
        allowed_environments = ["development", "staging", "production", "testing"]
        if v not in allowed_environments:
            raise ValueError(
                f"environment must be one of: " f"{', '.join(allowed_environments)}"
            )
        return v

    # Environment detection properties for conditional behavior

    @property
    def is_production(self) -> bool:
        """
        Check if running in production environment.

        Returns:
            bool: True if environment is production, False otherwise.

        Note:
            Used for enabling production-specific security features,
            disabling debug information, and optimizing performance.
        """
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """
        Check if running in development environment.

        Returns:
            bool: True if environment is development, False otherwise.

        Note:
            Used for enabling development features like auto-reload,
            debug information, and relaxed security settings.
        """
        return self.environment == "development"

    @property
    def database_url_async(self) -> str:
        """
        Convert synchronous PostgreSQL URL to async format.

        Transforms the standard PostgreSQL connection URL to use the
        asyncpg driver for async database operations with SQLAlchemy.

        Returns:
            str: Async-compatible database connection URL.

        Example:
            postgresql://... -> postgresql+asyncpg://...
        """
        return str(self.database_url).replace("postgresql://", "postgresql+asyncpg://")


@lru_cache()
def get_settings() -> Settings:
    """
    Create and cache application settings instance.

    Uses LRU cache to ensure only one Settings instance is created and
    reused throughout the application lifecycle. This prevents repeated
    environment variable parsing and validation.

    Returns:
        Settings: Cached settings instance with all configuration values.

    Note:
        The cache is cleared when the Python process restarts, ensuring
        fresh configuration is loaded on application startup.
    """
    return Settings()


# Global settings instance for application-wide access
# This provides a convenient way to access configuration throughout the app
settings = get_settings()
