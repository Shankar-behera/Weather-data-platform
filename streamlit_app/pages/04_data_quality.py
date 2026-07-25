"""
Data quality monitoring page for the weather dashboard.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from duckdb.analytics import get_analytics


def display():
    """Render data quality page."""
    st.title("🔍 Data Quality Monitoring")
    
    analytics = get_analytics()
    
    # Data freshness
    st.subheader("🕐 Data Freshness")
    
    try:
        freshness_query = """
        SELECT 
            city,
            MAX(observation_time) as latest_data_time,
            DATEDIFF('minutes', MAX(observation_time), CURRENT_TIMESTAMP) as minutes_since_update
        FROM weather.weather_gold
        GROUP BY city
        ORDER BY minutes_since_update
        """
        
        freshness_df = analytics.execute_query(freshness_query)
        
        if not freshness_df.empty:
            # Create freshness gauge
            fig = px.bar(
                freshness_df,
                x='city',
                y='minutes_since_update',
                color='minutes_since_update',
                title='Data Freshness by City',
                labels={
                    'city': 'City',
                    'minutes_since_update': 'Minutes Since Last Update'
                },
                color_continuous_scale=['green', 'yellow', 'red']
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Display as table
            st.dataframe(
                freshness_df,
                use_container_width=True,
                column_config={
                    "city": "City",
                    "latest_data_time": "Latest Update",
                    "minutes_since_update": "Minutes Old"
                }
            )
            
            # Check for stale data
            stale_cities = freshness_df[
                freshness_df['minutes_since_update'] > 120
            ]['city'].tolist()
            
            if stale_cities:
                st.warning(f"⚠️ Stale data detected for: {', '.join(stale_cities)}")
            else:
                st.success("✅ All cities have fresh data")
        else:
            st.info("No freshness data available")
    
    except Exception as e:
        st.error(f"Failed to load freshness data: {str(e)}")
    
    st.markdown("---")
    
    # Data completeness
    st.subheader("📊 Data Completeness")
    
    try:
        completeness_df = analytics.get_quality_metrics()
        
        if not completeness_df.empty:
            # Create completeness chart
            fig = px.bar(
                completeness_df,
                x='city',
                y=['complete_days', 'incomplete_days'],
                title='Data Completeness by City',
                labels={
                    'city': 'City',
                    'value': 'Days',
                    'variable': 'Status'
                },
                barmode='stack',
                color_discrete_map={
                    'complete_days': '#4CAF50',
                    'incomplete_days': '#FFC107'
                }
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Display details
            st.dataframe(
                completeness_df,
                use_container_width=True,
                column_config={
                    "city": "City",
                    "days_analyzed": "Days Analyzed",
                    "avg_hourly_readings": "Avg Hourly Readings",
                    "min_hourly_readings": "Min Readings",
                    "max_hourly_readings": "Max Readings",
                    "complete_days": "Complete Days",
                    "incomplete_days": "Incomplete Days"
                }
            )
            
            # Quality scores
            completeness_df['quality_score'] = (
                completeness_df['complete_days'] / completeness_df['days_analyzed'] * 100
            ).round(1)
            
            fig = px.bar(
                completeness_df,
                x='city',
                y='quality_score',
                title='Data Quality Score (%)',
                labels={
                    'city': 'City',
                    'quality_score': 'Quality Score (%)'
                },
                color='quality_score',
                color_continuous_scale=['red', 'yellow', 'green']
            )
            
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No completeness data available")
    
    except Exception as e:
        st.error(f"Failed to load completeness data: {str(e)}")
    
    st.markdown("---")
    
    # Data volume trends
    st.subheader("📈 Data Volume Trends")
    
    try:
        volume_query = """
        SELECT 
            DATE(observation_time) as date,
            city,
            COUNT(*) as records
        FROM weather.weather_gold
        WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(observation_time), city
        ORDER BY date DESC, city
        """
        
        volume_df = analytics.execute_query(volume_query)
        
        if not volume_df.empty:
            fig = px.line(
                volume_df,
                x='date',
                y='records',
                color='city',
                title='Data Volume by City (Last 7 Days)',
                labels={
                    'date': 'Date',
                    'records': 'Number of Records',
                    'city': 'City'
                },
                markers=True
            )
            
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Check for missing data
            expected_records = 24  # Hourly data
            missing_df = volume_df[volume_df['records'] < expected_records * 0.8]
            
            if not missing_df.empty:
                st.warning(f"⚠️ Low data volume detected for: {missing_df['city'].unique().tolist()}")
            else:
                st.success("✅ All cities have expected data volume")
        else:
            st.info("No volume data available")
    
    except Exception as e:
        st.error(f"Failed to load volume data: {str(e)}")
    
    st.markdown("---")
    
    # Validation results
    st.subheader("✅ Validation Results")
    
    try:
        validation_query = """
        WITH validation_data AS (
            SELECT 
                city,
                COUNT(*) as total_records,
                SUM(CASE WHEN temperature_celsius < -50 OR temperature_celsius > 60 THEN 1 ELSE 0 END) as temp_outliers,
                SUM(CASE WHEN humidity < 0 OR humidity > 100 THEN 1 ELSE 0 END) as humidity_outliers,
                SUM(CASE WHEN wind_speed < 0 OR wind_speed > 150 THEN 1 ELSE 0 END) as wind_outliers
            FROM weather.weather_gold
            WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY city
        )
        SELECT 
            city,
            total_records,
            temp_outliers,
            humidity_outliers,
            wind_outliers,
            (temp_outliers + humidity_outliers + wind_outliers) as total_outliers,
            ROUND(100.0 * (total_records - (temp_outliers + humidity_outliers + wind_outliers)) / total_records, 2) as validation_rate
        FROM validation_data
        """
        
        validation_df = analytics.execute_query(validation_query)
        
        if not validation_df.empty:
            # Display validation results
            st.dataframe(
                validation_df,
                use_container_width=True,
                column_config={
                    "city": "City",
                    "total_records": "Total Records",
                    "temp_outliers": "Temperature Outliers",
                    "humidity_outliers": "Humidity Outliers",
                    "wind_outliers": "Wind Speed Outliers",
                    "total_outliers": "Total Outliers",
                    "validation_rate": "Validation Rate (%)"
                }
            )
            
            # Validation rate chart
            fig = px.bar(
                validation_df,
                x='city',
                y='validation_rate',
                title='Validation Rate by City',
                labels={
                    'city': 'City',
                    'validation_rate': 'Validation Rate (%)'
                },
                color='validation_rate',
                color_continuous_scale=['red', 'yellow', 'green']
            )
            
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
            
            # Check for validation issues
            low_validation = validation_df[validation_df['validation_rate'] < 90]
            if not low_validation.empty:
                st.warning(f"⚠️ Low validation rate detected for: {low_validation['city'].tolist()}")
            else:
                st.success("✅ All cities have good validation rate")
        else:
            st.info("No validation data available")
    
    except Exception as e:
        st.error(f"Failed to load validation data: {str(e)}")