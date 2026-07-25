"""
Unit tests for data models and validation.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from ingestion.models import (
    WeatherPayload, 
    RawWeatherRecord, 
    SilverWeatherRecord,
    IngestionMetrics
)


class TestWeatherPayload:
    """Test WeatherPayload model validation."""
    
    def test_valid_weather_payload(self):
        """Test creating valid weather payload."""
        payload = WeatherPayload(
            city="London",
            temperature=18.5,
            humidity=65,
            pressure=1012,
            wind_speed=4.2,
            weather_main="Clouds",
            weather_description="scattered clouds",
            timestamp=datetime.utcnow()
        )
        
        assert payload.city == "London"
        assert payload.temperature == 18.5
        assert payload.humidity == 65
        assert payload.pressure == 1012
        assert payload.wind_speed == 4.2
        assert payload.weather_main == "Clouds"
        assert payload.weather_description == "scattered clouds"
        assert isinstance(payload.timestamp, datetime)
    
    def test_weather_payload_temperature_validation(self):
        """Test temperature validation."""
        # Test valid temperatures
        valid_temps = [-10, 0, 15, 30, 45]
        for temp in valid_temps:
            payload = WeatherPayload(
                city="Test",
                temperature=temp,
                humidity=50,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clear",
                weather_description="clear sky",
                timestamp=datetime.utcnow()
            )
            assert payload.temperature == temp
        
        # Test invalid temperatures (too hot)
        with pytest.raises(ValidationError) as exc_info:
            WeatherPayload(
                city="Test",
                temperature=100,
                humidity=50,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clear",
                weather_description="clear sky",
                timestamp=datetime.utcnow()
            )
        assert "temperature" in str(exc_info.value).lower()
        
        # Test invalid temperatures (too cold)
        with pytest.raises(ValidationError) as exc_info:
            WeatherPayload(
                city="Test",
                temperature=-60,
                humidity=50,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clear",
                weather_description="clear sky",
                timestamp=datetime.utcnow()
            )
        assert "temperature" in str(exc_info.value).lower()
    
    def test_weather_payload_humidity_validation(self):
        """Test humidity validation."""
        # Test valid humidities
        valid_humidities = [0, 25, 50, 75, 100]
        for humidity in valid_humidities:
            payload = WeatherPayload(
                city="Test",
                temperature=20,
                humidity=humidity,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clear",
                weather_description="clear sky",
                timestamp=datetime.utcnow()
            )
            assert payload.humidity == humidity
        
        # Test invalid humidity (too high)
        with pytest.raises(ValidationError) as exc_info:
            WeatherPayload(
                city="Test",
                temperature=20,
                humidity=150,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clear",
                weather_description="clear sky",
                timestamp=datetime.utcnow()
            )
        assert "humidity" in str(exc_info.value).lower()
        
        # Test invalid humidity (negative)
        with pytest.raises(ValidationError) as exc_info:
            WeatherPayload(
                city="Test",
                temperature=20,
                humidity=-10,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clear",
                weather_description="clear sky",
                timestamp=datetime.utcnow()
            )
        assert "humidity" in str(exc_info.value).lower()
    
    def test_weather_payload_serialization(self):
        """Test JSON serialization."""
        payload = WeatherPayload(
            city="London",
            temperature=18.5,
            humidity=65,
            pressure=1012,
            wind_speed=4.2,
            weather_main="Clouds",
            weather_description="scattered clouds",
            timestamp=datetime.utcnow()
        )
        
        # Test dict serialization
        data = payload.model_dump()
        assert data["city"] == "London"
        assert data["temperature"] == 18.5
        assert "timestamp" in data
        
        # Test JSON serialization
        json_str = payload.model_dump_json()
        assert "London" in json_str
        assert "18.5" in json_str


class TestRawWeatherRecord:
    """Test RawWeatherRecord model."""
    
    def test_raw_weather_record_creation(self):
        """Test creating raw weather record."""
        record = RawWeatherRecord(
            source_city="London",
            raw_payload={"temperature": 18.5, "humidity": 65},
            api_response_time=0.5
        )
        
        assert record.ingestion_id is not None
        assert isinstance(record.ingestion_id, str)
        assert record.ingestion_time is not None
        assert isinstance(record.ingestion_time, datetime)
        assert record.source == "openweathermap"
        assert record.source_city == "London"
        assert record.raw_payload == {"temperature": 18.5, "humidity": 65}
        assert record.api_response_time == 0.5
    
    def test_raw_weather_record_serialization(self):
        """Test serialization of raw weather record."""
        record = RawWeatherRecord(
            source_city="London",
            raw_payload={"test": "data"},
            api_response_time=0.5
        )
        
        data = record.model_dump()
        assert "ingestion_id" in data
        assert "ingestion_time" in data
        assert data["source"] == "openweathermap"
        assert data["source_city"] == "London"
        assert data["raw_payload"] == {"test": "data"}
        assert data["api_response_time"] == 0.5


class TestSilverWeatherRecord:
    """Test SilverWeatherRecord model."""
    
    def test_silver_weather_record_creation(self):
        """Test creating silver weather record."""
        record = SilverWeatherRecord(
            city="London",
            temperature_celsius=18.5,
            humidity=65,
            pressure=1012,
            wind_speed=4.2,
            weather_main="Clouds",
            weather_description="scattered clouds",
            observation_time=datetime.utcnow(),
            ingestion_id="test-123"
        )
        
        assert record.city == "London"
        assert record.temperature_celsius == 18.5
        assert record.humidity == 65
        assert record.pressure == 1012
        assert record.wind_speed == 4.2
        assert record.weather_main == "Clouds"
        assert record.weather_description == "scattered clouds"
        assert isinstance(record.observation_time, datetime)
        assert record.ingestion_id == "test-123"
        assert record.processed_time is not None
        assert isinstance(record.processed_time, datetime)
        assert record.is_valid is True
        assert record.quality_checks_passed == 5
        assert record.quality_checks_total == 5
    
    def test_silver_weather_record_defaults(self):
        """Test default values in silver record."""
        record = SilverWeatherRecord(
            city="London",
            temperature_celsius=18.5,
            humidity=65,
            pressure=1012,
            wind_speed=4.2,
            weather_main="Clouds",
            weather_description="scattered clouds",
            observation_time=datetime.utcnow()
        )
        
        assert record.ingestion_id is not None
        assert record.processed_time is not None
        assert record.is_valid is True
        assert record.quality_checks_passed == 5
        assert record.quality_checks_total == 5
    
    def test_silver_weather_record_serialization(self):
        """Test serialization of silver record."""
        record = SilverWeatherRecord(
            city="London",
            temperature_celsius=18.5,
            humidity=65,
            pressure=1012,
            wind_speed=4.2,
            weather_main="Clouds",
            weather_description="scattered clouds",
            observation_time=datetime.utcnow()
        )
        
        data = record.model_dump()
        assert data["city"] == "London"
        assert data["temperature_celsius"] == 18.5
        assert data["humidity"] == 65
        assert data["pressure"] == 1012
        assert data["wind_speed"] == 4.2
        assert data["weather_main"] == "Clouds"
        assert data["weather_description"] == "scattered clouds"
        assert "observation_time" in data
        assert "processed_time" in data
        assert "quality_checks_passed" in data


class TestIngestionMetrics:
    """Test IngestionMetrics model."""
    
    def test_ingestion_metrics_creation(self):
        """Test creating ingestion metrics."""
        metrics = IngestionMetrics(
            city="London",
            status="success",
            duration_ms=450.5,
            api_response_time=350.0,
            rows_processed=1
        )
        
        assert metrics.city == "London"
        assert metrics.status == "success"
        assert metrics.duration_ms == 450.5
        assert metrics.api_response_time == 350.0
        assert metrics.rows_processed == 1
        assert metrics.error is None
    
    def test_ingestion_metrics_with_error(self):
        """Test ingestion metrics with error."""
        metrics = IngestionMetrics(
            city="London",
            status="failed",
            duration_ms=450.5,
            api_response_time=0,
            rows_processed=0,
            error="Connection timeout"
        )
        
        assert metrics.city == "London"
        assert metrics.status == "failed"
        assert metrics.error == "Connection timeout"
    
    def test_ingestion_metrics_serialization(self):
        """Test serialization of metrics."""
        metrics = IngestionMetrics(
            city="London",
            status="success",
            duration_ms=450.5,
            api_response_time=350.0,
            rows_processed=1
        )
        
        data = metrics.model_dump()
        assert data["city"] == "London"
        assert data["status"] == "success"
        assert data["duration_ms"] == 450.5
        assert data["api_response_time"] == 350.0
        assert data["rows_processed"] == 1
        assert data["error"] is None