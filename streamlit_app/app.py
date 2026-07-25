"""
Main Streamlit dashboard for weather data platform.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from duckdb.analytics import get_analytics


# Page configuration
st.set_page_config(
    page_title="Weather Data Platform",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1f77b4;
        text-align: center;
        padding: 1rem 0;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
    }
    .alert-card {
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        margin: 0.2rem 0;
    }
    .alert-high {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
    }
    .alert-medium {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
    }
    .alert-low {
        background-color: #e8f5e9;
        border-left: 4px solid #4caf50;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if 'analytics' not in st.session_state:
        st.session_state.analytics = get_analytics()
    
    if 'refreshed' not in st.session_state:
        st.session_state.refreshed = datetime.now()


def display_header():
    """Display dashboard header."""
    st.markdown('<div class="main-header">🌤️ Global Weather Analytics Platform</div>', unsafe_allow_html=True)
    st.markdown(f"*Last Updated: {st.session_state.refreshed.strftime('%Y-%m-%d %H:%M:%S')}*")
    st.markdown("---")


def display_kpi_metrics():
    """Display KPI metrics row."""
    analytics = st.session_state.analytics
    
    try:
        kpis = analytics.get_global_kpis()
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{kpis['global_avg_temp']:.1f}°C</div>
                <div class="metric-label">Global Average Temperature</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{kpis['hottest_city']}</div>
                <div class="metric-label">Hottest City ({kpis['hottest_temp']:.1f}°C)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{kpis['coldest_city']}</div>
                <div class="metric-label">Coldest City ({kpis['coldest_temp']:.1f}°C)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{kpis['total_cities']}</div>
                <div class="metric-label">Cities Monitored</div>
            </div>
            """, unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"Failed to load KPIs: {str(e)}")


def display_temperature_trends():
    """Display temperature trends chart."""
    analytics = st.session_state.analytics
    
    try:
        # Get data for all cities
        cities = ["London", "New York", "Tokyo", "Sydney", "Berlin", "Mumbai", "Singapore", "Dubai"]
        
        dfs = []
        for city in cities:
            df = analytics.get_forecast_data(city, days=30)
            if not df.empty:
                df['city'] = city
                dfs.append(df)
        
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # Create temperature trend chart
            fig = px.line(
                combined_df,
                x='observation_time',
                y='temperature_celsius',
                color='city',
                title='Temperature Trends by City (Last 30 Days)',
                labels={
                    'observation_time': 'Date',
                    'temperature_celsius': 'Temperature (°C)',
                    'city': 'City'
                }
            )
            
            fig.update_layout(
                height=500,
                hovermode='x unified',
                legend=dict(
                    orientation='h',
                    yanchor='bottom',
                    y=1.02,
                    xanchor='right',
                    x=1
                )
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"Failed to load temperature trends: {str(e)}")


def display_humidity_analysis():
    """Display humidity analysis chart."""
    analytics = st.session_state.analytics
    
    try:
        # Get city summaries
        cities = ["London", "New York", "Tokyo", "Sydney", "Berlin", "Mumbai", "Singapore", "Dubai"]
        
        dfs = []
        for city in cities:
            df = analytics.get_city_summary(city)
            if not df.empty:
                dfs.append(df)
        
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # Create humidity scatter plot
            fig = px.scatter(
                combined_df,
                x='avg_temperature',
                y='avg_humidity',
                size='record_count',
                color='city',
                text='city',
                title='Temperature vs Humidity Analysis',
                labels={
                    'avg_temperature': 'Average Temperature (°C)',
                    'avg_humidity': 'Average Humidity (%)',
                    'record_count': 'Number of Records'
                },
                size_max=30
            )
            
            fig.update_traces(textposition='top center')
            fig.update_layout(height=500)
            
            st.plotly_chart(fig, use_container_width=True)
    
    except Exception as e:
        st.error(f"Failed to load humidity analysis: {str(e)}")


def display_extreme_events():
    """Display extreme weather events."""
    analytics = st.session_state.analytics
    
    try:
        events_df = analytics.get_extreme_weather_events(days=7)
        
        if not events_df.empty:
            st.subheader("⚠️ Extreme Weather Events (Last 7 Days)")
            
            # Group by event type and city
            event_summary = events_df.groupby(['event_type', 'city']).size().reset_index(name='count')
            
            # Create bar chart
            fig = px.bar(
                event_summary,
                x='city',
                y='count',
                color='event_type',
                title='Extreme Weather Events by City',
                labels={
                    'city': 'City',
                    'count': 'Number of Events',
                    'event_type': 'Event Type'
                },
                barmode='group'
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Display recent events table
            st.subheader("Recent Events")
            display_df = events_df.head(10)[['city', 'observation_time', 'event_type', 'temperature_celsius', 'weather_main']]
            display_df['observation_time'] = display_df['observation_time'].dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(display_df)
        else:
            st.info("No extreme weather events detected in the last 7 days")
    
    except Exception as e:
        st.error(f"Failed to load extreme events: {str(e)}")


def display_sidebar():
    """Display sidebar with controls."""
    with st.sidebar:
        st.image("https://raw.githubusercontent.com/your-repo/weather-platform/main/docs/logo.png", use_column_width=True)
        
        st.markdown("## 🎛️ Controls")
        
        # Refresh button
        if st.button("🔄 Refresh Data"):
            st.session_state.refreshed = datetime.now()
            st.rerun()
        
        st.markdown("---")
        
        st.markdown("## 📊 Data Quality")
        
        analytics = st.session_state.analytics
        try:
            quality_df = analytics.get_quality_metrics()
            if not quality_df.empty:
                for _, row in quality_df.iterrows():
                    status = "✅" if row['complete_days'] >= 5 else "⚠️"
                    st.markdown(f"{status} **{row['city']}**: {row['complete_days']}/{row['days_analyzed']} complete days")
        except Exception as e:
            st.error(f"Failed to load quality metrics: {str(e)}")
        
        st.markdown("---")
        
        st.markdown("## ℹ️ About")
        st.markdown("""
        Built with:
        - Python
        - Databricks Delta Lake
        - dbt
        - DuckDB
        - Streamlit
        """)
        
        st.markdown("[View Source Code](https://github.com/your-repo/weather-platform)")


def main():
    """Main dashboard function."""
    init_session_state()
    
    # Display sidebar
    display_sidebar()
    
    # Main content
    display_header()
    
    # KPIs row
    display_kpi_metrics()
    
    st.markdown("---")
    
    # Charts row
    col1, col2 = st.columns(2)
    
    with col1:
        display_temperature_trends()
    
    with col2:
        display_humidity_analysis()
    
    st.markdown("---")
    
    # Extreme events
    display_extreme_events()


if __name__ == "__main__":
    main()