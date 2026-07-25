"""
Data loading utilities for Streamlit dashboard.
"""

import pandas as pd
import streamlit as st
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from duckdb.analytics import get_analytics


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_global_kpis() -> Dict[str, Any]:
    """
    Load global KPIs with caching.
    
    Returns:
        Dictionary with global KPIs
    """
    analytics = get_analytics()
    return analytics.get_global_kpis()


@st.cache_data(ttl=300)
def load_city_data(city: str, days: int = 30) -> pd.DataFrame:
    """
    Load city weather data with caching.
    
    Args:
        city: City name
        days: Number of days to load
        
    Returns:
        DataFrame with weather data
    """
    analytics = get_analytics()
    return analytics.get_forecast_data(city, days)


@st.cache_data(ttl=600)
def load_city_summary(city: str) -> pd.DataFrame:
    """
    Load city summary with caching.
    
    Args:
        city: City name
        
    Returns:
        DataFrame with city summary
    """
    analytics = get_analytics()
    return analytics.get_city_summary(city)


@st.cache_data(ttl=300)
def load_extreme_events(days: int = 7) -> pd.DataFrame:
    """
    Load extreme weather events with caching.
    
    Args:
        days: Number of days to look back
        
    Returns:
        DataFrame with extreme events
    """
    analytics = get_analytics()
    return analytics.get_extreme_weather_events(days)


@st.cache_data(ttl=300)
def load_quality_metrics() -> pd.DataFrame:
    """
    Load data quality metrics with caching.
    
    Returns:
        DataFrame with quality metrics
    """
    analytics = get_analytics()
    return analytics.get_quality_metrics()


@st.cache_data(ttl=600)
def load_weather_distribution() -> pd.DataFrame:
    """
    Load weather distribution data with caching.
    
    Returns:
        DataFrame with weather distribution
    """
    analytics = get_analytics()
    
    query = """
    SELECT 
        city,
        weather_main,
        COUNT(*) as count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY city), 2) as percentage
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY city, weather_main
    ORDER BY city, count DESC
    """
    
    return analytics.execute_query(query)


@st.cache_data(ttl=3600)
def load_table_stats() -> Dict[str, Any]:
    """
    Load table statistics with caching.
    
    Returns:
        Dictionary with table statistics
    """
    analytics = get_analytics()
    
    stats = {}
    
    try:
        # Get record counts
        count_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT city) as total_cities,
            MIN(observation_time) as earliest_record,
            MAX(observation_time) as latest_record
        FROM weather.weather_gold
        """
        
        result = analytics.execute_query(count_query)
        if not result.empty:
            stats = {
                "total_records": int(result.iloc[0]['total_records']),
                "total_cities": int(result.iloc[0]['total_cities']),
                "earliest_record": result.iloc[0]['earliest_record'],
                "latest_record": result.iloc[0]['latest_record']
            }
        
        # Get per-city stats
        city_query = """
        SELECT 
            city,
            COUNT(*) as record_count,
            MIN(observation_time) as first_record,
            MAX(observation_time) as last_record,
            AVG(temperature_celsius) as avg_temp
        FROM weather.weather_gold
        GROUP BY city
        ORDER BY record_count DESC
        """
        
        city_stats = analytics.execute_query(city_query)
        stats["city_stats"] = city_stats.to_dict('records')
        
    except Exception as e:
        stats["error"] = str(e)
    
    return stats


def clear_cache():
    """Clear all cached data."""
    st.cache_data.clear()
    st.cache_resource.clear()