"""
Configuration management for weather data ingestion.
Uses Pydantic v2 Settings.
"""

from typing import List, Optional

from pydantic import BaseModel, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class WeatherConfig(BaseSettings):
    """Weather data ingestion configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # API Configuration
    OPENWEATHER_API_KEY: str
    OPENWEATHER_BASE_URL: HttpUrl = "https://api.openweathermap.org/data/2.5"

    # Cities
    CITIES: List[str] = [
        "London",
        "New York",
        "Tokyo",
        "Sydney",
        "Berlin",
        "Mumbai",
        "Singapore",
        "Dubai",
    ]

    # Databricks
    DATABRICKS_HOST: str
    DATABRICKS_TOKEN: str
    DATABRICKS_HTTP_PATH: str
    DATABRICKS_CATALOG: str = "weather"
    DATABRICKS_SCHEMA: str = "bronze"

    # Delta Tables
    BRONZE_TABLE: str = "weather_bronze"
    SILVER_TABLE: str = "weather_silver"
    GOLD_TABLE: str = "weather_gold"

    # Processing
    MAX_RETRIES: int = 3
    RETRY_DELAY: int = 5
    BATCH_SIZE: int = 100

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"


class IngestionMetrics(BaseModel):
    """Metrics tracking for ingestion pipeline."""

    city: str
    status: str
    duration_ms: float
    api_response_time: float
    rows_processed: int = 0
    error: Optional[str] = None


# Singleton configuration instance
config = WeatherConfig()