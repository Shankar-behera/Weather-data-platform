"""
DuckDB integration for analytics and querying.
Provides local analytical capabilities on Gold layer data.
"""

import duckdb
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta
import json


class DuckDBAnalytics:
    """DuckDB analytics layer for weather data."""
    
    def __init__(self, db_path: str = "analytics.duckdb"):
        """
        Initialize DuckDB connection.
        
        Args:
            db_path: Path to DuckDB database file
        """
        self.db_path = db_path
        self.conn = None
        self.logger = logging.getLogger(__name__)
        
        # Connect to or create database
        self.connect()
        
        # Initialize tables and views
        self.initialize()
    
    def connect(self):
        """Connect to DuckDB database."""
        try:
            self.conn = duckdb.connect(self.db_path)
            self.logger.info(f"Connected to DuckDB: {self.db_path}")
        except Exception as e:
            self.logger.error(f"Failed to connect to DuckDB: {str(e)}")
            raise
    
    def initialize(self):
        """
        Initialize database with tables and views.
        Loads data from Delta Lake or Parquet files.
        """
        # Create schema if not exists
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS weather")
        
        # Note: In production, load from Delta Lake using Spark
        # For demo, we'll create sample tables
        self._create_analytics_views()
        
        self.logger.info("DuckDB analytics initialized")
    
    def _create_analytics_views(self):
        """Create analytics views for weather data."""
        
        # Create view for city weather summary
        self.conn.execute("""
        CREATE OR REPLACE VIEW weather.city_weather_summary AS
        SELECT 
            city,
            DATE(observation_time) as observation_date,
            AVG(temperature_celsius) as avg_temperature,
            MAX(temperature_celsius) as max_temperature,
            MIN(temperature_celsius) as min_temperature,
            AVG(humidity) as avg_humidity,
            AVG(wind_speed) as avg_wind_speed,
            COUNT(*) as record_count
        FROM weather.weather_gold
        GROUP BY city, DATE(observation_time)
        """)
        
        # Create view for trend analysis
        self.conn.execute("""
        CREATE OR REPLACE VIEW weather.weather_trends AS
        SELECT 
            city,
            observation_time,
            temperature_celsius,
            AVG(temperature_celsius) OVER (
                PARTITION BY city 
                ORDER BY observation_time 
                ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
            ) as rolling_24h_avg,
            AVG(temperature_celsius) OVER (
                PARTITION BY city 
                ORDER BY observation_time 
                ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
            ) as rolling_7d_avg,
            temperature_celsius - LAG(temperature_celsius) OVER (
                PARTITION BY city 
                ORDER BY observation_time
            ) as temp_change
        FROM weather.weather_gold
        """)
        
        # Create KPI view
        self.conn.execute("""
        CREATE OR REPLACE VIEW weather.kpi_dashboard AS
        SELECT 
            city,
            AVG(temperature_celsius) as avg_temp,
            MIN(temperature_celsius) as min_temp,
            MAX(temperature_celsius) as max_temp,
            COUNT(*) as total_readings,
            MAX(observation_time) as last_updated,
            COUNT(DISTINCT DATE(observation_time)) as days_of_data
        FROM weather.weather_gold
        GROUP BY city
        """)
    
    def execute_query(self, query: str) -> pd.DataFrame:
        """
        Execute SQL query and return results as DataFrame.
        
        Args:
            query: SQL query string
            
        Returns:
            pandas DataFrame with results
        """
        try:
            result = self.conn.execute(query).df()
            self.logger.info(f"Query executed successfully, returned {len(result)} rows")
            return result
        except Exception as e:
            self.logger.error(f"Query execution failed: {str(e)}")
            raise
    
    def get_city_summary(self, city: str) -> pd.DataFrame:
        """
        Get weather summary for a specific city.
        
        Args:
            city: City name
            
        Returns:
            DataFrame with city summary
        """
        query = f"""
        SELECT * 
        FROM weather.city_weather_summary 
        WHERE city = '{city}'
        ORDER BY observation_date DESC
        """
        return self.execute_query(query)
    
    def get_global_kpis(self) -> Dict:
        """
        Get global KPIs across all cities.
        
        Returns:
            Dictionary with global KPIs
        """
        query = """
        SELECT 
            AVG(avg_temp) as global_avg_temp,
            MAX(max_temp) as global_max_temp,
            MIN(min_temp) as global_min_temp,
            COUNT(DISTINCT city) as total_cities,
            SUM(record_count) as total_records
        FROM weather.kpi_dashboard
        """
        result = self.execute_query(query)
        
        # Also get hottest and coldest cities
        extremes_query = """
        SELECT 
            city,
            avg_temp
        FROM weather.kpi_dashboard
        ORDER BY avg_temp DESC
        LIMIT 1
        """
        
        hottest = self.execute_query(extremes_query)
        
        coldest_query = """
        SELECT 
            city,
            avg_temp
        FROM weather.kpi_dashboard
        ORDER BY avg_temp ASC
        LIMIT 1
        """
        
        coldest = self.execute_query(coldest_query)
        
        kpis = {
            "global_avg_temp": float(result.iloc[0]['global_avg_temp']) if not result.empty else 0,
            "global_max_temp": float(result.iloc[0]['global_max_temp']) if not result.empty else 0,
            "global_min_temp": float(result.iloc[0]['global_min_temp']) if not result.empty else 0,
            "total_cities": int(result.iloc[0]['total_cities']) if not result.empty else 0,
            "total_records": int(result.iloc[0]['total_records']) if not result.empty else 0,
            "hottest_city": hottest.iloc[0]['city'] if not hottest.empty else "N/A",
            "hottest_temp": float(hottest.iloc[0]['avg_temp']) if not hottest.empty else 0,
            "coldest_city": coldest.iloc[0]['city'] if not coldest.empty else "N/A",
            "coldest_temp": float(coldest.iloc[0]['avg_temp']) if not coldest.empty else 0
        }
        
        return kpis
    
    def get_extreme_weather_events(self, days: int = 7) -> pd.DataFrame:
        """
        Get recent extreme weather events.
        
        Args:
            days: Number of days to look back
            
        Returns:
            DataFrame with extreme events
        """
        query = f"""
        SELECT 
            city,
            observation_time,
            temperature_celsius,
            wind_speed,
            weather_main,
            weather_description,
            CASE 
                WHEN temperature_celsius > 35 THEN 'Heatwave'
                WHEN wind_speed > 50 THEN 'Storm'
                WHEN weather_main = 'Rain' THEN 'Heavy Rain'
                ELSE 'Other'
            END as event_type
        FROM weather.weather_gold
        WHERE observation_time >= CURRENT_DATE - INTERVAL {days} DAY
        AND (
            temperature_celsius > 35 
            OR wind_speed > 50 
            OR weather_main = 'Rain'
        )
        ORDER BY observation_time DESC
        """
        return self.execute_query(query)
    
    def get_quality_metrics(self) -> pd.DataFrame:
        """
        Get data quality metrics.
        
        Returns:
            DataFrame with quality metrics
        """
        query = """
        WITH daily_counts AS (
            SELECT 
                city,
                DATE(observation_time) as date,
                COUNT(*) as hourly_readings
            FROM weather.weather_gold
            WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY city, DATE(observation_time)
        ),
        expected_counts AS (
            SELECT 
                city,
                date,
                hourly_readings,
                CASE 
                    WHEN hourly_readings >= 20 THEN 'Complete'
                    WHEN hourly_readings >= 10 THEN 'Partial'
                    ELSE 'Incomplete'
                END as completeness_status
            FROM daily_counts
        )
        SELECT 
            city,
            COUNT(*) as days_analyzed,
            AVG(hourly_readings) as avg_hourly_readings,
            MIN(hourly_readings) as min_hourly_readings,
            MAX(hourly_readings) as max_hourly_readings,
            SUM(CASE WHEN completeness_status = 'Complete' THEN 1 ELSE 0 END) as complete_days,
            SUM(CASE WHEN completeness_status = 'Incomplete' THEN 1 ELSE 0 END) as incomplete_days
        FROM expected_counts
        GROUP BY city
        """
        return self.execute_query(query)
    
    def get_forecast_data(self, city: str, days: int = 7) -> pd.DataFrame:
        """
        Get historical and forecast data for a city.
        
        Args:
            city: City name
            days: Number of days to include
            
        Returns:
            DataFrame with time series data
        """
        query = f"""
        SELECT 
            observation_time,
            temperature_celsius,
            humidity,
            wind_speed,
            weather_main,
            weather_description,
            LAG(temperature_celsius, 1) OVER (
                ORDER BY observation_time
            ) as prev_temp,
            temperature_celsius - LAG(temperature_celsius, 1) OVER (
                ORDER BY observation_time
            ) as temp_change
        FROM weather.weather_gold
        WHERE city = '{city}'
        AND observation_time >= CURRENT_DATE - INTERVAL {days} DAY
        ORDER BY observation_time
        """
        return self.execute_query(query)
    
    def close(self):
        """Close DuckDB connection."""
        if self.conn:
            self.conn.close()
            self.logger.info("DuckDB connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Singleton instance
_analytics_instance = None


def get_analytics() -> DuckDBAnalytics:
    """Get or create singleton analytics instance."""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = DuckDBAnalytics()
    return _analytics_instance