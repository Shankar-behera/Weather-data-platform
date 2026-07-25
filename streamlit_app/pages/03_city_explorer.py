"""
City explorer page for the weather dashboard.
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


def display_city_alerts(city, analytics):
    """Display weather alerts for a city."""
    try:
        alerts_query = f"""
        SELECT 
            observation_time,
            temperature_celsius,
            wind_speed,
            weather_main,
            CASE 
                WHEN temperature_celsius > 35 THEN '🔴 Heatwave Alert'
                WHEN wind_speed > 50 THEN '🟠 Storm Alert'
                WHEN weather_main = 'Rain' THEN '🟡 Rain Alert'
                ELSE '🟢 Normal'
            END as alert_level
        FROM weather.weather_gold
        WHERE city = '{city}'
        AND observation_time >= CURRENT_DATE - INTERVAL '7 days'
        AND (
            temperature_celsius > 35 
            OR wind_speed > 50 
            OR weather_main = 'Rain'
        )
        ORDER BY observation_time DESC
        LIMIT 10
        """
        
        alerts_df = analytics.execute_query(alerts_query)
        
        if not alerts_df.empty:
            st.subheader("⚠️ Recent Alerts")
            
            for _, row in alerts_df.iterrows():
                alert_color = {
                    '🔴 Heatwave Alert': 'alert-high',
                    '🟠 Storm Alert': 'alert-medium',
                    '🟡 Rain Alert': 'alert-low'
                }.get(row['alert_level'], 'alert-low')
                
                st.markdown(f"""
                <div class="alert-card {alert_color}">
                    <strong>{row['alert_level']}</strong><br>
                    Time: {row['observation_time'].strftime('%Y-%m-%d %H:%M')}<br>
                    Temperature: {row['temperature_celsius']:.1f}°C | 
                    Wind Speed: {row['wind_speed']:.1f} km/h | 
                    Weather: {row['weather_main']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No recent alerts for this city")
    
    except Exception as e:
        st.error(f"Failed to load alerts: {str(e)}")


def display():
    """Render city explorer page."""
    st.title("🏙️ City Weather Explorer")
    
    analytics = get_analytics()
    
    # City selection
    cities = ["London", "New York", "Tokyo", "Sydney", "Berlin", "Mumbai", "Singapore", "Dubai"]
    selected_city = st.selectbox("Select a City", cities)
    
    if selected_city:
        # Get city data
        try:
            df = analytics.get_forecast_data(selected_city, days=30)
            
            if not df.empty:
                # Current conditions
                current = df.iloc[-1]
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "🌡️ Temperature",
                        f"{current['temperature_celsius']:.1f}°C",
                        delta=f"{current['temp_change']:.1f}°C" if pd.notna(current.get('temp_change')) else None
                    )
                
                with col2:
                    st.metric(
                        "💧 Humidity",
                        f"{current['humidity']}%"
                    )
                
                with col3:
                    st.metric(
                        "💨 Wind Speed",
                        f"{current['wind_speed']:.1f} km/h"
                    )
                
                with col4:
                    st.metric(
                        "☁️ Weather",
                        current['weather_main']
                    )
                
                st.markdown("---")
                
                # Temperature trend chart
                st.subheader("📊 Temperature History")
                
                fig = go.Figure()
                
                # Add temperature line
                fig.add_trace(go.Scatter(
                    x=df['observation_time'],
                    y=df['temperature_celsius'],
                    mode='lines',
                    name='Temperature',
                    line=dict(color='#ff6b6b', width=2)
                ))
                
                # Add 24-hour moving average
                ma_24h = df['temperature_celsius'].rolling(24).mean()
                fig.add_trace(go.Scatter(
                    x=df['observation_time'],
                    y=ma_24h,
                    mode='lines',
                    name='24h Moving Average',
                    line=dict(color='#4ecdc4', width=2, dash='dash')
                ))
                
                # Add 7-day moving average
                ma_7d = df['temperature_celsius'].rolling(168).mean()
                fig.add_trace(go.Scatter(
                    x=df['observation_time'],
                    y=ma_7d,
                    mode='lines',
                    name='7d Moving Average',
                    line=dict(color='#ffe66d', width=2, dash='dash')
                ))
                
                fig.update_layout(
                    height=400,
                    hovermode='x unified',
                    xaxis_title='Date',
                    yaxis_title='Temperature (°C)',
                    legend=dict(
                        orientation='h',
                        yanchor='bottom',
                        y=1.02,
                        xanchor='right',
                        x=1
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Weather distribution
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🌤️ Weather Distribution")
                    
                    weather_counts = df['weather_main'].value_counts()
                    fig_pie = px.pie(
                        values=weather_counts.values,
                        names=weather_counts.index,
                        title='Weather Conditions'
                    )
                    fig_pie.update_layout(height=300)
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                with col2:
                    st.subheader("📊 Temperature Distribution")
                    
                    fig_box = px.box(
                        df,
                        y='temperature_celsius',
                        title='Temperature Range'
                    )
                    fig_box.update_layout(height=300)
                    st.plotly_chart(fig_box, use_container_width=True)
                
                # Weather alerts for the city
                display_city_alerts(selected_city, analytics)
                
                # Detailed statistics
                st.subheader("📈 Detailed Statistics")
                
                stats = {
                    'Average Temperature': f"{df['temperature_celsius'].mean():.1f}°C",
                    'Max Temperature': f"{df['temperature_celsius'].max():.1f}°C",
                    'Min Temperature': f"{df['temperature_celsius'].min():.1f}°C",
                    'Average Humidity': f"{df['humidity'].mean():.1f}%",
                    'Average Wind Speed': f"{df['wind_speed'].mean():.1f} km/h",
                    'Total Records': len(df),
                    'Date Range': f"{df['observation_time'].min().strftime('%Y-%m-%d')} to {df['observation_time'].max().strftime('%Y-%m-%d')}"
                }
                
                stats_df = pd.DataFrame(stats.items(), columns=['Metric', 'Value'])
                st.dataframe(stats_df, use_container_width=True)
                
                # Raw data
                st.subheader("📋 Raw Data")
                st.dataframe(
                    df.tail(10),
                    use_container_width=True,
                    column_config={
                        "observation_time": "Time",
                        "temperature_celsius": "Temperature (°C)",
                        "humidity": "Humidity (%)",
                        "wind_speed": "Wind Speed (km/h)",
                        "weather_main": "Weather",
                        "weather_description": "Description"
                    }
                )
            
            else:
                st.info(f"No data available for {selected_city}")
        
        except Exception as e:
            st.error(f"Failed to load city data: {str(e)}")