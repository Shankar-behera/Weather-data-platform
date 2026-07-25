"""
Overview page for the weather dashboard.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from duckdb.analytics import get_analytics


def load_weather_distribution(analytics):
    """Load weather distribution data."""
    query = """
    SELECT 
        city,
        weather_main,
        COUNT(*) as count
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY city, weather_main
    """
    return analytics.execute_query(query)


def display():
    """Render overview page."""
    st.title("📊 Weather Overview")
    
    analytics = get_analytics()
    
    # Get global KPIs
    kpis = analytics.get_global_kpis()
    
    # Display KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "🌡️ Global Average Temperature",
            f"{kpis['global_avg_temp']:.1f}°C",
            delta=f"±{kpis['global_max_temp'] - kpis['global_min_temp']:.1f}°C"
        )
    
    with col2:
        st.metric(
            "🔥 Hottest City",
            f"{kpis['hottest_city']}",
            delta=f"{kpis['hottest_temp']:.1f}°C"
        )
    
    with col3:
        st.metric(
            "❄️ Coldest City",
            f"{kpis['coldest_city']}",
            delta=f"{kpis['coldest_temp']:.1f}°C"
        )
    
    with col4:
        st.metric(
            "🏙️ Cities Monitored",
            kpis['total_cities'],
            delta=f"{kpis['total_records']:,} records"
        )
    
    st.markdown("---")
    
    # Weather distribution chart
    st.subheader("🌤️ Weather Distribution (Last 7 Days)")
    
    try:
        weather_dist = load_weather_distribution(analytics)
        
        if not weather_dist.empty:
            fig = px.sunburst(
                weather_dist,
                path=['city', 'weather_main'],
                values='count',
                title='Weather Distribution by City',
                color='weather_main',
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No weather distribution data available")
    
    except Exception as e:
        st.error(f"Failed to load weather distribution: {str(e)}")
    
    # Recent weather summary
    st.subheader("🕐 Recent Weather Summary")
    
    try:
        recent_query = """
        SELECT 
            city,
            observation_time,
            temperature_celsius,
            weather_main,
            humidity
        FROM weather.weather_gold
        WHERE observation_time >= CURRENT_TIMESTAMP - INTERVAL '6 hours'
        ORDER BY observation_time DESC
        LIMIT 20
        """
        
        recent_df = analytics.execute_query(recent_query)
        
        if not recent_df.empty:
            # Format the dataframe
            display_df = recent_df.copy()
            display_df['observation_time'] = display_df['observation_time'].dt.strftime('%Y-%m-%d %H:%M')
            display_df['temperature_celsius'] = display_df['temperature_celsius'].round(1)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "city": "City",
                    "observation_time": "Time",
                    "temperature_celsius": "Temperature (°C)",
                    "weather_main": "Weather",
                    "humidity": "Humidity (%)"
                }
            )
        else:
            st.info("No recent weather data available")
    
    except Exception as e:
        st.error(f"Failed to load recent data: {str(e)}")