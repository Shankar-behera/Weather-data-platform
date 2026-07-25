"""
Trends analysis page for the weather dashboard.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from duckdb.analytics import get_analytics


def display():
    """Render trends page."""
    st.title("📈 Weather Trends & Analysis")
    
    analytics = get_analytics()
    
    # City selection
    cities = ["London", "New York", "Tokyo", "Sydney", "Berlin", "Mumbai", "Singapore", "Dubai"]
    selected_cities = st.multiselect(
        "Select Cities for Analysis",
        cities,
        default=["London", "New York", "Tokyo"]
    )
    
    # Date range selection
    col1, col2 = st.columns(2)
    
    with col1:
        days = st.slider("Days to Analyze", 7, 90, 30)
    
    with col2:
        metrics = st.multiselect(
            "Select Metrics",
            ["Temperature", "Humidity", "Wind Speed"],
            default=["Temperature", "Humidity"]
        )
    
    if selected_cities and metrics:
        st.markdown("---")
        
        # Temperature trends
        if "Temperature" in metrics:
            st.subheader("🌡️ Temperature Trends")
            
            try:
                # Get temperature data
                temp_data = []
                for city in selected_cities:
                    df = analytics.get_forecast_data(city, days)
                    if not df.empty:
                        df['city'] = city
                        temp_data.append(df)
                
                if temp_data:
                    temp_df = pd.concat(temp_data, ignore_index=True)
                    
                    # Create line chart
                    fig = px.line(
                        temp_df,
                        x='observation_time',
                        y='temperature_celsius',
                        color='city',
                        title=f'Temperature Trends (Last {days} Days)',
                        labels={
                            'observation_time': 'Date',
                            'temperature_celsius': 'Temperature (°C)',
                            'city': 'City'
                        }
                    )
                    
                    # Add moving average
                    for city in selected_cities:
                        city_data = temp_df[temp_df['city'] == city]
                        if not city_data.empty:
                            fig.add_trace(
                                go.Scatter(
                                    x=city_data['observation_time'],
                                    y=city_data['temperature_celsius'].rolling(24).mean(),
                                    name=f'{city} (24h MA)',
                                    line=dict(dash='dash', width=1),
                                    opacity=0.5
                                )
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
                    
                    # Temperature statistics
                    st.subheader("Temperature Statistics")
                    
                    stats_data = []
                    for city in selected_cities:
                        city_temp = temp_df[temp_df['city'] == city]['temperature_celsius']
                        if not city_temp.empty:
                            stats_data.append({
                                'City': city,
                                'Average': city_temp.mean(),
                                'Max': city_temp.max(),
                                'Min': city_temp.min(),
                                'Std Dev': city_temp.std()
                            })
                    
                    if stats_data:
                        stats_df = pd.DataFrame(stats_data)
                        stats_df['Average'] = stats_df['Average'].round(1)
                        stats_df['Max'] = stats_df['Max'].round(1)
                        stats_df['Min'] = stats_df['Min'].round(1)
                        stats_df['Std Dev'] = stats_df['Std Dev'].round(2)
                        
                        st.dataframe(stats_df, use_container_width=True)
                
                else:
                    st.info("No temperature data available")
            
            except Exception as e:
                st.error(f"Failed to load temperature trends: {str(e)}")
        
        # Humidity trends
        if "Humidity" in metrics:
            st.subheader("💧 Humidity Trends")
            
            try:
                # Get city summaries for humidity
                humid_data = []
                for city in selected_cities:
                    df = analytics.get_city_summary(city)
                    if not df.empty:
                        df['city'] = city
                        humid_data.append(df)
                
                if humid_data:
                    humid_df = pd.concat(humid_data, ignore_index=True)
                    
                    # Create humidity chart
                    fig = px.line(
                        humid_df,
                        x='observation_date',
                        y='avg_humidity',
                        color='city',
                        title=f'Humidity Trends (Last {len(humid_df["observation_date"].unique())} Days)',
                        labels={
                            'observation_date': 'Date',
                            'avg_humidity': 'Average Humidity (%)',
                            'city': 'City'
                        }
                    )
                    
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No humidity data available")
            
            except Exception as e:
                st.error(f"Failed to load humidity trends: {str(e)}")
        
        # Wind Speed trends
        if "Wind Speed" in metrics:
            st.subheader("💨 Wind Speed Trends")
            
            try:
                wind_data = []
                for city in selected_cities:
                    df = analytics.get_city_summary(city)
                    if not df.empty:
                        df['city'] = city
                        wind_data.append(df)
                
                if wind_data:
                    wind_df = pd.concat(wind_data, ignore_index=True)
                    
                    # Create wind speed chart
                    fig = px.bar(
                        wind_df,
                        x='city',
                        y='avg_wind_speed',
                        color='observation_date',
                        title='Average Wind Speed by City',
                        labels={
                            'city': 'City',
                            'avg_wind_speed': 'Average Wind Speed (km/h)',
                            'observation_date': 'Date'
                        },
                        barmode='group'
                    )
                    
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No wind speed data available")
            
            except Exception as e:
                st.error(f"Failed to load wind speed trends: {str(e)}")
    
    else:
        st.info("Please select at least one city and metric to view trends")