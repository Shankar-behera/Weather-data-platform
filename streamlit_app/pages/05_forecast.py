"""
Weather forecast and predictions page.
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


def display_forecast_chart(df, city):
    """Display forecast chart with historical data."""
    if df.empty:
        st.info(f"No forecast data available for {city}")
        return
    
    # Create figure with historical and forecast
    fig = go.Figure()
    
    # Historical data
    historical = df[df['observation_time'] < datetime.now()]
    if not historical.empty:
        fig.add_trace(go.Scatter(
            x=historical['observation_time'],
            y=historical['temperature_celsius'],
            mode='lines+markers',
            name='Historical',
            line=dict(color='#1f77b4')
        ))
    
    # Forecast data (simulated)
    forecast = df[df['observation_time'] >= datetime.now()]
    if not forecast.empty:
        fig.add_trace(go.Scatter(
            x=forecast['observation_time'],
            y=forecast['temperature_celsius'],
            mode='lines+markers',
            name='Forecast',
            line=dict(color='#ff7f0e', dash='dash')
        ))
    
    fig.update_layout(
        height=400,
        hovermode='x unified',
        xaxis_title='Date',
        yaxis_title='Temperature (°C)',
        title=f'Temperature Forecast for {city}'
    )
    
    st.plotly_chart(fig, use_container_width=True)


def display():
    """Render forecast page."""
    st.title("🔮 Weather Forecast")
    
    analytics = get_analytics()
    
    # City selection
    cities = ["London", "New York", "Tokyo", "Sydney", "Berlin", "Mumbai", "Singapore", "Dubai"]
    selected_city = st.selectbox("Select City for Forecast", cities)
    
    # Forecast horizon
    forecast_days = st.slider("Forecast Horizon (Days)", 1, 7, 3)
    
    if selected_city:
        try:
            # Get historical data
            historical_df = analytics.get_forecast_data(selected_city, days=30)
            
            if not historical_df.empty:
                # Generate forecast data (simulated)
                last_date = historical_df['observation_time'].max()
                last_temp = historical_df['temperature_celsius'].iloc[-1]
                
                # Simulate forecast with some variation
                forecast_data = []
                for i in range(1, forecast_days * 24 + 1):
                    forecast_time = last_date + timedelta(hours=i)
                    # Add some daily pattern and random variation
                    hour_of_day = forecast_time.hour
                    daily_variation = 2 * (hour_of_day - 12) / 12  # Peak at noon
                    random_variation = (i % 5 - 2) * 0.5  # Small random variation
                    temp = last_temp + daily_variation + random_variation
                    
                    forecast_data.append({
                        'observation_time': forecast_time,
                        'temperature_celsius': temp,
                        'humidity': 50 + (i % 20),
                        'wind_speed': 5 + (i % 10),
                        'weather_main': ['Clear', 'Clouds', 'Rain', 'Sunny'][i % 4]
                    })
                
                forecast_df = pd.DataFrame(forecast_data)
                
                # Combine historical and forecast
                combined_df = pd.concat([historical_df, forecast_df], ignore_index=True)
                
                # Display forecast
                display_forecast_chart(combined_df, selected_city)
                
                # Forecast summary
                st.subheader("📊 Forecast Summary")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    avg_temp = forecast_df['temperature_celsius'].mean()
                    st.metric("Average Temperature", f"{avg_temp:.1f}°C")
                
                with col2:
                    max_temp = forecast_df['temperature_celsius'].max()
                    st.metric("Maximum Temperature", f"{max_temp:.1f}°C")
                
                with col3:
                    min_temp = forecast_df['temperature_celsius'].min()
                    st.metric("Minimum Temperature", f"{min_temp:.1f}°C")
                
                with col4:
                    avg_humidity = forecast_df['humidity'].mean()
                    st.metric("Average Humidity", f"{avg_humidity:.1f}%")
                
                # Daily forecast breakdown
                st.subheader("📅 Daily Forecast")
                
                daily_forecast = forecast_df.groupby(
                    forecast_df['observation_time'].dt.date
                ).agg({
                    'temperature_celsius': ['mean', 'max', 'min'],
                    'humidity': 'mean',
                    'wind_speed': 'mean',
                    'weather_main': lambda x: x.mode()[0] if not x.empty else 'Unknown'
                })
                
                daily_forecast.columns = ['Avg Temp', 'Max Temp', 'Min Temp', 'Avg Humidity', 'Avg Wind Speed', 'Weather']
                daily_forecast['Avg Temp'] = daily_forecast['Avg Temp'].round(1)
                daily_forecast['Max Temp'] = daily_forecast['Max Temp'].round(1)
                daily_forecast['Min Temp'] = daily_forecast['Min Temp'].round(1)
                daily_forecast['Avg Humidity'] = daily_forecast['Avg Humidity'].round(1)
                daily_forecast['Avg Wind Speed'] = daily_forecast['Avg Wind Speed'].round(1)
                
                st.dataframe(daily_forecast, use_container_width=True)
                
                # Weather distribution in forecast
                st.subheader("🌤️ Forecast Weather Distribution")
                
                weather_counts = forecast_df['weather_main'].value_counts()
                fig = px.pie(
                    values=weather_counts.values,
                    names=weather_counts.index,
                    title='Predicted Weather Conditions'
                )
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
                
            else:
                st.info(f"No historical data available for {selected_city}")
        
        except Exception as e:
            st.error(f"Failed to load forecast data: {str(e)}")