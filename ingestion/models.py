"""
Data models for weather data using Pydantic v2 for validation.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, Field, field_validator
from pydantic import ConfigDict


class WeatherPayload(BaseModel):
    """Raw weather data model from OpenWeatherMap API."""

    city: str
    temperature: float
    humidity: int
    pressure: int
    wind_speed: float
    weather_main: str
    weather_description: str
    timestamp: datetime

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float):
        """Validate temperature is within reasonable range."""
        if not -50 <= v <= 60:
            raise ValueError(f"Temperature {v}°C is outside reasonable range")
        return v

    @field_validator("humidity")
    @classmethod
    def validate_humidity(cls, v: int):
        """Validate humidity is within 0-100 range."""
        if not 0 <= v <= 100:
            raise ValueError(f"Humidity {v}% is outside 0-100 range")
        return v

    

    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )


class RawWeatherRecord(BaseModel):
    """Bronze layer record model."""

    ingestion_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ingestion_time: datetime = Field(
        
        default_factory=lambda: datetime.now(timezone.utc)
    )
    city :str
    source: str = "openweathermap"
    raw_payload: dict
    api_response_time: float
    source_city: str

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class SilverWeatherRecord(BaseModel):
    """Silver layer cleaned weather model."""

    city: str
    temperature_celsius: float
    humidity: int
    pressure: int
    wind_speed: float
    weather_main: str
    weather_description: str
    observation_time: datetime
    ingestion_id: str
    processed_time: datetime = Field(
        
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Data quality flags
    is_valid: bool = True
    quality_checks_passed: int = 0
    quality_checks_total: int = 5

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }


class IngestionMetrics(BaseModel):
    """Metrics tracking for ingestion pipeline."""

    city: str
    status: str
    duration_ms: float
    api_response_time: float
    rows_processed: int = 0
    error: Optional[str] = None

    model_config = {
        "json_encoders": {
            datetime: lambda v: v.isoformat()
        }
    }