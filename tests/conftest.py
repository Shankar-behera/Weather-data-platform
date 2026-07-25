"""
Pytest configuration and fixtures for testing.
"""

import pytest
import json
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Any
from pathlib import Path
import pandas as pd
import duckdb

from ingestion.config import config
from ingestion.models import WeatherPayload, SilverWeatherRecord
from duckdb.analytics import DuckDBAnalytics


@pytest.fixture(scope="session")
def sample_weather_data() -> List[Dict[str, Any]]:
    """
    Generate sample weather data for testing.
    
    Returns:
        List of weather data dictionaries
    """
    cities = ["London", "New York", "Tokyo", "Sydney", "Berlin", "Mumbai", "Singapore", "Dubai"]
    weather_conditions = ["Clear", "Clouds", "Rain", "Snow", "Thunderstorm", "Drizzle", "Mist"]
    
    data = []
    base_time = datetime.utcnow() - timedelta(hours=24)
    
    for i, city in enumerate(cities):
        for hour in range(24):
            data.append({
                "city": city,
                "temperature": 15 + (i % 10) + (hour % 5),
                "humidity": 50 + (i * 3) % 40,
                "pressure": 1010 + (i % 20),
                "wind_speed": 3 + (i % 8) + (hour % 3),
                "weather_main": weather_conditions[i % len(weather_conditions)],
                "weather_description": f"{weather_conditions[i % len(weather_conditions)]} description",
                "timestamp": base_time + timedelta(hours=hour),
                "api_response_time": 0.5 + (i * 0.1)
            })
    
    return data


@pytest.fixture
def sample_weather_payloads(sample_weather_data) -> List[WeatherPayload]:
    """
    Create WeatherPayload objects from sample data.
    
    Args:
        sample_weather_data: Sample weather data
        
    Returns:
        List of WeatherPayload objects
    """
    payloads = []
    for data in sample_weather_data[:10]:  # Use first 10 for testing
        payload = WeatherPayload(
            city=data["city"],
            temperature=data["temperature"],
            humidity=data["humidity"],
            pressure=data["pressure"],
            wind_speed=data["wind_speed"],
            weather_main=data["weather_main"],
            weather_description=data["weather_description"],
            timestamp=data["timestamp"]
        )
        payloads.append(payload)
    return payloads


@pytest.fixture
def sample_silver_records(sample_weather_payloads) -> List[SilverWeatherRecord]:
    """
    Create SilverWeatherRecord objects from payloads.
    
    Args:
        sample_weather_payloads: Sample weather payloads
        
    Returns:
        List of SilverWeatherRecord objects
    """
    records = []
    for payload in sample_weather_payloads:
        record = SilverWeatherRecord(
            city=payload.city,
            temperature_celsius=payload.temperature,
            humidity=payload.humidity,
            pressure=payload.pressure,
            wind_speed=payload.wind_speed,
            weather_main=payload.weather_main,
            weather_description=payload.weather_description,
            observation_time=payload.timestamp,
            ingestion_id=f"test-{payload.city}-{datetime.utcnow().timestamp()}",
            quality_checks_passed=5,
            quality_checks_total=5
        )
        records.append(record)
    return records


@pytest.fixture
def temp_duckdb_db():
    """
    Create a temporary DuckDB database for testing.
    
    Yields:
        DuckDBAnalytics instance
    """
    # Create temporary file for database
    with tempfile.NamedTemporaryFile(suffix='.duckdb', delete=False) as tmp:
        db_path = tmp.name
    
    # Create analytics instance
    analytics = DuckDBAnalytics(db_path)
    
    # Create test tables
    conn = analytics.conn
    
    # Create weather_gold table
    conn.execute("""
        CREATE TABLE weather.weather_gold (
            city VARCHAR,
            observation_time TIMESTAMP,
            temperature_celsius DOUBLE,
            humidity INTEGER,
            pressure INTEGER,
            wind_speed DOUBLE,
            weather_main VARCHAR,
            weather_description VARCHAR
        )
    """)
    
    yield analytics
    
    # Cleanup
    analytics.close()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def populated_duckdb(temp_duckdb_db, sample_weather_data):
    """
    Populate DuckDB with sample data.
    
    Args:
        temp_duckdb_db: Temporary DuckDB instance
        sample_weather_data: Sample weather data
        
    Returns:
        DuckDBAnalytics instance with populated data
    """
    conn = temp_duckdb_db.conn
    
    # Insert sample data
    for data in sample_weather_data[:50]:  # Use 50 records
        conn.execute("""
            INSERT INTO weather.weather_gold 
            (city, observation_time, temperature_celsius, humidity, 
             pressure, wind_speed, weather_main, weather_description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            data["city"],
            data["timestamp"],
            data["temperature"],
            data["humidity"],
            data["pressure"],
            data["wind_speed"],
            data["weather_main"],
            data["weather_description"]
        ])
    
    # Create views
    temp_duckdb_db._create_analytics_views()
    
    return temp_duckdb_db


@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Mock environment variables for testing.
    
    Args:
        monkeypatch: Pytest monkeypatch fixture
    """
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test_api_key")
    monkeypatch.setenv("DATABRICKS_HOST", "test.databricks.com")
    monkeypatch.setenv("DATABRICKS_TOKEN", "test_token")
    monkeypatch.setenv("DATABRICKS_CATALOG", "test_catalog")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "text")


@pytest.fixture
def test_data_path():
    """
    Get path to test data directory.
    
    Returns:
        Path to test data directory
    """
    return Path(__file__).parent / "data"


@pytest.fixture
def create_test_data_file(test_data_path):
    """
    Create a test data file.
    
    Args:
        test_data_path: Path to test data directory
        
    Returns:
        Function to create test data files
    """
    test_data_path.mkdir(exist_ok=True)
    
    def _create_file(filename: str, data: Dict) -> Path:
        file_path = test_data_path / filename
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return file_path
    
    return _create_file


@pytest.fixture(autouse=True)
def setup_test_logging():
    """
    Setup logging for tests.
    """
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger("ingestion").setLevel(logging.DEBUG)
    logging.getLogger("duckdb").setLevel(logging.DEBUG)


@pytest.fixture
def mock_databricks_response():
    """
    Mock Databricks API response.
    
    Returns:
        Sample Databricks query response
    """
    return [
        {
            "city": "London",
            "avg_temp": 18.5,
            "max_temp": 22.0,
            "min_temp": 15.0,
            "record_count": 24
        },
        {
            "city": "New York",
            "avg_temp": 20.0,
            "max_temp": 25.0,
            "min_temp": 18.0,
            "record_count": 24
        }
    ]


def pytest_configure(config):
    """
    Pytest configuration hook.
    """
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )