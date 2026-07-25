"""
Unit tests for ingestion service.
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch
import requests

from ingestion.service import WeatherService
from ingestion.models import WeatherPayload, RawWeatherRecord, SilverWeatherRecord
from ingestion.config import config


class TestWeatherService:
    """Test cases for WeatherService."""
    
    @pytest.fixture
    def weather_service(self):
        """Create WeatherService instance for testing."""
        return WeatherService()
    
    @pytest.fixture
    def sample_weather_data(self):
        """Sample weather data from API."""
        return {
            "main": {
                "temp": 18.5,
                "humidity": 65,
                "pressure": 1012
            },
            "wind": {
                "speed": 4.2
            },
            "weather": [
                {
                    "main": "Clouds",
                    "description": "scattered clouds"
                }
            ],
            "dt": 1718899200  # 2024-06-20 12:00:00
        }
    
    @patch('ingestion.service.requests.get')
    def test_fetch_weather_data_success(self, mock_get, weather_service, sample_weather_data):
        """Test successful weather data fetch."""
        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_weather_data
        mock_get.return_value = mock_response
        
        # Fetch weather
        result = weather_service.fetch_weather_data("London")
        
        # Assertions
        assert result is not None
        assert result.city == "London"
        assert result.temperature == 18.5
        assert result.humidity == 65
        assert result.pressure == 1012
        assert result.wind_speed == 4.2
        assert result.weather_main == "Clouds"
        assert result.weather_description == "scattered clouds"
        
        # Verify API call
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert "London" in str(args)
        assert kwargs.get("params", {}).get("units") == "metric"
    
    @patch('ingestion.service.requests.get')
    def test_fetch_weather_data_api_error(self, mock_get, weather_service):
        """Test API error handling."""
        # Mock API error
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.HTTPError("Not Found")
        mock_get.return_value = mock_response
        
        # Fetch weather should raise exception
        with pytest.raises(requests.HTTPError):
            weather_service.fetch_weather_data("InvalidCity")
    
    @patch('ingestion.service.requests.get')
    def test_fetch_weather_data_validation_error(self, mock_get, weather_service):
        """Test validation error handling."""
        # Mock invalid data (temperature out of range)
        invalid_data = {
            "main": {
                "temp": 100,  # Invalid temperature
                "humidity": 65,
                "pressure": 1012
            },
            "wind": {
                "speed": 4.2
            },
            "weather": [
                {
                    "main": "Clouds",
                    "description": "scattered clouds"
                }
            ],
            "dt": 1718899200
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = invalid_data
        mock_get.return_value = mock_response
        
        # Should return None due to validation error
        result = weather_service.fetch_weather_data("London")
        assert result is None
    
    def test_create_bronze_records(self, weather_service):
        """Test bronze record creation."""
        # Create sample weather data
        weather_data = [
            WeatherPayload(
                city="London",
                temperature=18.5,
                humidity=65,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clouds",
                weather_description="scattered clouds",
                timestamp=datetime.utcnow()
            )
        ]
        
        # Create bronze records
        records = weather_service.create_bronze_records(weather_data)
        
        # Assertions
        assert len(records) == 1
        record = records[0]
        assert record.source_city == "London"
        assert record.source == "openweathermap"
        assert isinstance(record.raw_payload, dict)
        assert record.raw_payload["city"] == "London"
        assert record.raw_payload["temperature"] == 18.5
    
    def test_create_silver_records(self, weather_service):
        """Test silver record creation."""
        # Create sample weather data
        weather_data = [
            WeatherPayload(
                city="London",
                temperature=18.5,
                humidity=65,
                pressure=1012,
                wind_speed=4.2,
                weather_main="Clouds",
                weather_description="scattered clouds",
                timestamp=datetime.utcnow()
            )
        ]
        
        # Create silver records
        records = weather_service.create_silver_records(weather_data)
        
        # Assertions
        assert len(records) == 1
        record = records[0]
        assert record.city == "London"
        assert record.temperature_celsius == 18.5
        assert record.humidity == 65
        assert record.pressure == 1012
        assert record.wind_speed == 4.2
        assert record.weather_main == "Clouds"
        assert record.quality_checks_passed == 5
        assert record.is_valid == True


class TestWeatherModels:
    """Test Pydantic models."""
    
    def test_weather_payload_validation(self):
        """Test WeatherPayload validation."""
        # Valid data
        valid_data = {
            "city": "London",
            "temperature": 18.5,
            "humidity": 65,
            "pressure": 1012,
            "wind_speed": 4.2,
            "weather_main": "Clouds",
            "weather_description": "scattered clouds",
            "timestamp": datetime.utcnow()
        }
        
        payload = WeatherPayload(**valid_data)
        assert payload.city == "London"
        
        # Invalid temperature (too hot)
        invalid_data = valid_data.copy()
        invalid_data["temperature"] = 100
        with pytest.raises(ValueError, match="temperature.*outside reasonable range"):
            WeatherPayload(**invalid_data)
        
        # Invalid temperature (too cold)
        invalid_data["temperature"] = -60
        with pytest.raises(ValueError, match="temperature.*outside reasonable range"):
            WeatherPayload(**invalid_data)
        
        # Invalid humidity
        invalid_data = valid_data.copy()
        invalid_data["humidity"] = 150
        with pytest.raises(ValueError, match="Humidity.*outside"):
            WeatherPayload(**invalid_data)
        
        invalid_data["humidity"] = -10
        with pytest.raises(ValueError, match="Humidity.*outside"):
            WeatherPayload(**invalid_data)
    
    def test_raw_weather_record(self):
        """Test RawWeatherRecord creation."""
        record = RawWeatherRecord(
            source_city="London",
            raw_payload={"test": "data"},
            api_response_time=0.5
        )
        
        assert record.ingestion_id is not None
        assert record.ingestion_time is not None
        assert record.source == "openweathermap"
        assert record.source_city == "London"
        assert record.raw_payload == {"test": "data"}
        assert record.api_response_time == 0.5
    
    def test_silver_weather_record(self):
        """Test SilverWeatherRecord creation."""
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
        assert record.quality_checks_passed == 5
        assert record.quality_checks_total == 5
        assert record.is_valid == True