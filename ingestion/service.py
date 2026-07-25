
"""
Weather data extraction service with retry logic and error handling.
"""

import logging
import json
import time
import uuid
from typing import List, Optional
from datetime import datetime, timedelta
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from pydantic import ValidationError

from .config import config
from .models import WeatherPayload, RawWeatherRecord, SilverWeatherRecord, IngestionMetrics


class WeatherService:
    """Service for extracting weather data from OpenWeatherMap API."""
    
    def __init__(self):
        """Initialize weather service with configuration."""
        self.api_key = config.OPENWEATHER_API_KEY
        self.base_url = str(config.OPENWEATHER_BASE_URL)
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
    
    def setup_logging(self):
        """Configure structured logging."""
        handler = logging.StreamHandler()
        
        if config.LOG_FORMAT == "json":
            handler.setFormatter(logging.Formatter(
                '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
            ))
        else:
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    @retry(
        stop=stop_after_attempt(config.MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=config.RETRY_DELAY, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError))
    )
    def fetch_weather_data(self, city: str) -> Optional[WeatherPayload]:
        """
        Fetch weather data for a city with retry logic.
        
        Args:
            city: City name to fetch weather for
            
        Returns:
            WeatherPayload object or None if failed
        """
        start_time = time.time()
        
        try:
            # Build API request
            params = {
                "q": city,
                "appid": self.api_key,
                "units": "metric"  # Celsius
            }
            
            self.logger.info(f"Fetching weather data for {city}")
            
            response = requests.get(
                f"{self.base_url}/weather",
                params=params,
                timeout=10
            )
            
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Extract required fields
            weather_data = WeatherPayload(
                city=city,
                temperature=data["main"]["temp"],
                humidity=data["main"]["humidity"],
                pressure=data["main"]["pressure"],
                wind_speed=data["wind"]["speed"],
                weather_main=data["weather"][0]["main"],
                weather_description=data["weather"][0]["description"],
                timestamp=datetime.fromtimestamp(data["dt"])
            )
            
            elapsed_time = (time.time() - start_time) * 1000
            
            # Log success metrics
            metrics = IngestionMetrics(
                city=city,
                status="success",
                duration_ms=elapsed_time,
                api_response_time=data.get("response_time", elapsed_time),
                rows_processed=1
            )
            
            self.logger.info(
                f"Successfully fetched weather for {city}",
                extra={"metrics": metrics.model_dump()}
            )
            
            return weather_data
            
        except requests.RequestException as e:
            elapsed_time = (time.time() - start_time) * 1000
            
            self.logger.error(
                f"Failed to fetch weather for {city}: {str(e)}",
                extra={
                    "city": city,
                    "error": str(e),
                    "duration_ms": elapsed_time
                }
            )
            raise
            
        except ValidationError as e:
            self.logger.error(
                f"Validation error for {city}: {str(e)}",
                extra={"city": city, "errors": e.errors()}
            )
            return None
    
    def fetch_all_cities(self) -> List[WeatherPayload]:
        """
        Fetch weather data for all configured cities.
        
        Returns:
            List of WeatherPayload objects
        """
        results = []
        
        for city in config.CITIES:
            try:
                weather_data = self.fetch_weather_data(city)
                if weather_data:
                    results.append(weather_data)
                    
            except Exception as e:
                self.logger.error(f"Error processing {city}: {str(e)}")
                continue
        
        self.logger.info(
            f"Completed weather fetch: {len(results)}/{len(config.CITIES)} cities successful"
        )
        
        return results
    
    def create_bronze_records(self, weather_data: List[WeatherPayload]) -> List[RawWeatherRecord]:
        """
        Create bronze layer records from weather data.
        
        Args:
            weather_data: List of WeatherPayload objects
            
        Returns:
            List of RawWeatherRecord objects
        """
        records = []
        
        for data in weather_data:
            record = RawWeatherRecord(
                city = data.city,
                source_city=data.city,
                raw_payload=data.model_dump(mode="json"),
                api_response_time=0.0  # Will be set by fetch function
            )
            records.append(record)
        
        return records
    
    def create_silver_records(self, weather_data: List[WeatherPayload]) -> List[SilverWeatherRecord]:
        """
        Create silver layer records from weather data.
        
        Args:
            weather_data: List of WeatherPayload objects
            
        Returns:
            List of SilverWeatherRecord objects
        """
        records = []
        
        for data in weather_data:
            record = SilverWeatherRecord(
                city=data.city,
                temperature_celsius=data.temperature,
                humidity=data.humidity,
                pressure=data.pressure,
                wind_speed=data.wind_speed,
                weather_main=data.weather_main,
                weather_description=data.weather_description,
                observation_time=data.timestamp,
                ingestion_id=str(uuid.uuid4()),
                quality_checks_passed=5
            )
            records.append(record)
        
        return records