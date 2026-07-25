"""
Integration tests for the complete data pipeline.
"""

import pytest
import json
from datetime import datetime, timedelta
import pandas as pd

from ingestion.service import WeatherService
from duckdb.analytics import DuckDBAnalytics


@pytest.mark.integration
class TestPipelineIntegration:
    """Integration tests for the complete pipeline."""
    
    @pytest.fixture
    def analytics(self):
        """Create DuckDB analytics instance."""
        return DuckDBAnalytics(":memory:")
    
    @pytest.fixture
    def sample_weather_data(self):
        """Generate sample weather data for testing."""
        cities = ["London", "New York", "Tokyo", "Sydney", "Berlin", "Mumbai", "Singapore", "Dubai"]
        data = []
        
        base_time = datetime.utcnow() - timedelta(hours=24)
        
        for i, city in enumerate(cities):
            data.append({
                "city": city,
                "temperature": 15 + i * 2,
                "humidity": 50 + i * 3,
                "pressure": 1010 + i,
                "wind_speed": 3 + i * 0.5,
                "weather_main": ["Clouds", "Sunny", "Rain", "Clouds"][i % 4],
                "weather_description": "scattered clouds",
                "timestamp": base_time + timedelta(hours=i)
            })
        
        return data
    
    def test_ingestion_to_silver_flow(self, sample_weather_data):
        """Test the flow from ingestion to silver layer."""
        # This is a mock test for the integration flow
        # In production, this would test against actual Databricks
        
        service = WeatherService()
        
        # Create records
        weather_payloads = []
        for data in sample_weather_data:
            # Simulate creating payloads
            weather_payloads.append(
                WeatherPayload(
                    city=data["city"],
                    temperature=data["temperature"],
                    humidity=data["humidity"],
                    pressure=data["pressure"],
                    wind_speed=data["wind_speed"],
                    weather_main=data["weather_main"],
                    weather_description=data["weather_description"],
                    timestamp=data["timestamp"]
                )
            )
        
        # Create bronze and silver records
        bronze_records = service.create_bronze_records(weather_payloads)
        silver_records = service.create_silver_records(weather_payloads)
        
        # Assertions
        assert len(bronze_records) == len(sample_weather_data)
        assert len(silver_records) == len(sample_weather_data)
        
        # Verify data quality checks
        for record in silver_records:
            assert record.quality_checks_passed == 5
            assert record.is_valid == True
    
    def test_silver_to_gold_transformations(self, analytics, sample_weather_data):
        """Test transformation from silver to gold layer."""
        # Create test data in DuckDB
        conn = analytics.conn
        
        # Create silver table with sample data
        conn.execute("CREATE SCHEMA IF NOT EXISTS weather")
        
        # Insert sample data
        for data in sample_weather_data:
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
        
        # Run analytics queries
        kpis = analytics.get_global_kpis()
        
        # Assertions
        assert kpis["total_cities"] == 8
        assert kpis["global_avg_temp"] > 0
        
        # Check city summary
        for city in ["London", "New York"]:
            df = analytics.get_city_summary(city)
            assert not df.empty
            assert "city" in df.columns
            assert "avg_temperature" in df.columns
            assert "avg_humidity" in df.columns
            assert "record_count" in df.columns
    
    def test_extreme_event_detection(self, analytics):
        """Test extreme weather event detection."""
        conn = analytics.conn
        
        # Insert extreme weather data
        extreme_data = [
            ("Dubai", datetime.utcnow(), 42.0, 20, 1005, 5.0, "Clear", "clear sky"),
            ("Mumbai", datetime.utcnow(), 38.0, 80, 1008, 8.0, "Rain", "heavy rain"),
            ("New York", datetime.utcnow(), 35.5, 65, 1010, 55.0, "Thunderstorm", "thunderstorm")
        ]
        
        for data in extreme_data:
            conn.execute("""
                INSERT INTO weather.weather_gold 
                (city, observation_time, temperature_celsius, humidity, 
                 pressure, wind_speed, weather_main, weather_description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, data)
        
        # Get extreme events
        events_df = analytics.get_extreme_weather_events(days=7)
        
        # Assertions
        assert not events_df.empty
        assert "event_type" in events_df.columns
        assert "Heatwave" in events_df["event_type"].values
        assert "Storm" in events_df["event_type"].values
        assert "Heavy Rain" in events_df["event_type"].values
    
    def test_data_quality_metrics(self, analytics, sample_weather_data):
        """Test data quality metrics generation."""
        conn = analytics.conn
        
        # Insert data for multiple days
        base_time = datetime.utcnow() - timedelta(hours=48)
        
        for i in range(48):  # 2 days of hourly data
            for city_data in sample_weather_data[:3]:  # Only 3 cities
                conn.execute("""
                    INSERT INTO weather.weather_gold 
                    (city, observation_time, temperature_celsius, humidity, 
                     pressure, wind_speed, weather_main, weather_description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    city_data["city"],
                    base_time + timedelta(hours=i),
                    city_data["temperature"] + (i % 5),
                    city_data["humidity"] + (i % 10),
                    city_data["pressure"] + (i % 3),
                    city_data["wind_speed"] + (i % 2),
                    city_data["weather_main"],
                    city_data["weather_description"]
                ])
        
        # Get quality metrics
        quality_df = analytics.get_quality_metrics()
        
        # Assertions
        assert not quality_df.empty
        assert "city" in quality_df.columns
        assert "days_analyzed" in quality_df.columns
        assert "complete_days" in quality_df.columns
        
        # Each city should have data for both days
        for city in ["London", "New York", "Tokyo"]:
            city_data = quality_df[quality_df["city"] == city]
            assert not city_data.empty
            assert city_data.iloc[0]["days_analyzed"] >= 1