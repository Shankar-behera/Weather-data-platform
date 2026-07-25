-- ============================================
-- Weather Data Platform - Delta Table Schemas
-- Medallion Architecture: Bronze → Silver → Gold
-- ============================================

-- ============================================
-- 1. BRONZE LAYER - Raw Ingestion
-- ============================================
-- Purpose: Store raw JSON data from OpenWeatherMap API
-- Strategy: Append-only, partition by source and city
-- ============================================

CREATE TABLE IF NOT EXISTS weather.bronze.weather_bronze (
    ingestion_id STRING COMMENT 'Unique identifier for each ingestion batch',
    ingestion_time TIMESTAMP COMMENT 'Timestamp when data was ingested',
    city STRING COMMENT 'City name (extracted for partitioning)',
    source STRING COMMENT 'Data source (openweathermap)',
    source_city STRING COMMENT 'Original city name from source',
    raw_payload STRING COMMENT 'Complete raw JSON payload from API',
    api_response_time DOUBLE COMMENT 'API response time in milliseconds'
)
USING DELTA
PARTITIONED BY (source, source_city)
COMMENT 'Bronze layer: Raw weather data from OpenWeatherMap API'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5',
    'delta.columnMapping.mode' = 'name'
);

-- ============================================
-- 2. SILVER LAYER - Cleaned & Validated Data
-- ============================================
-- Purpose: Cleaned, standardized, and validated weather data
-- Strategy: Partition by city for efficient queries
-- ============================================

CREATE TABLE IF NOT EXISTS weather.silver.weather_silver (
    city STRING COMMENT 'City name',
    temperature_celsius DOUBLE COMMENT 'Temperature in Celsius',
    humidity INT COMMENT 'Humidity percentage (0-100)',
    pressure INT COMMENT 'Atmospheric pressure in hPa',
    wind_speed DOUBLE COMMENT 'Wind speed in km/h',
    weather_main STRING COMMENT 'Main weather category',
    weather_description STRING COMMENT 'Detailed weather description',
    observation_time TIMESTAMP COMMENT 'Time of weather observation (UTC)',
    ingestion_id STRING COMMENT 'Reference to bronze ingestion ID',
    processed_time TIMESTAMP COMMENT 'Time record was processed to silver',
    is_valid BOOLEAN COMMENT 'Whether record passed all quality checks',
    quality_checks_passed INT COMMENT 'Number of quality checks passed',
    quality_checks_total INT COMMENT 'Total number of quality checks'
)
USING DELTA
PARTITIONED BY (city)
COMMENT 'Silver layer: Cleaned and validated weather data'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5',
    'delta.columnMapping.mode' = 'name'
);

-- ============================================
-- 3. GOLD LAYER - Business Metrics
-- ============================================

-- 3.1 Daily Weather Summary
-- ============================================
-- Purpose: Daily aggregated metrics by city
-- Strategy: Partition by city and date for optimal querying
-- ============================================

CREATE TABLE IF NOT EXISTS weather.gold.weather_daily_summary (
    city STRING COMMENT 'City name',
    observation_date DATE COMMENT 'Date of observation',
    avg_temperature DOUBLE COMMENT 'Average daily temperature in Celsius',
    max_temperature DOUBLE COMMENT 'Maximum daily temperature in Celsius',
    min_temperature DOUBLE COMMENT 'Minimum daily temperature in Celsius',
    avg_humidity DOUBLE COMMENT 'Average daily humidity percentage',
    avg_wind_speed DOUBLE COMMENT 'Average daily wind speed in km/h',
    record_count INT COMMENT 'Number of records used for aggregation',
    most_common_weather STRING COMMENT 'Most frequent weather type of the day',
    temp_category STRING COMMENT 'Temperature category: Freezing, Cold, Mild, Warm, Hot',
    last_updated TIMESTAMP COMMENT 'Last update timestamp'
)
USING DELTA
PARTITIONED BY (city, observation_date)
COMMENT 'Gold layer: Daily weather summary by city'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5',
    'delta.columnMapping.mode' = 'name'
);

-- ============================================
-- 3.2 Weather Trend Analysis
-- ============================================
-- Purpose: Rolling window calculations for trend detection
-- Strategy: Partition by city for efficient window functions
-- ============================================

CREATE TABLE IF NOT EXISTS weather.gold.weather_trend_analysis (
    city STRING COMMENT 'City name',
    observation_time TIMESTAMP COMMENT 'Time of observation',
    temperature_celsius DOUBLE COMMENT 'Temperature at observation time',
    rolling_24h_avg_temp DOUBLE COMMENT '24-hour rolling average temperature',
    rolling_7d_avg_temp DOUBLE COMMENT '7-day rolling average temperature',
    temp_change_24h DOUBLE COMMENT 'Temperature change over last 24 hours',
    temp_change_pct DOUBLE COMMENT 'Percentage temperature change over 24 hours',
    trend_direction STRING COMMENT 'Trend direction: Rising, Falling, Stable',
    trend_strength DOUBLE COMMENT 'Strength of the trend (0-1)',
    volatility_score DOUBLE COMMENT 'Weather volatility score (0-100)',
    last_updated TIMESTAMP COMMENT 'Last update timestamp'
)
USING DELTA
PARTITIONED BY (city)
COMMENT 'Gold layer: Weather trend analysis with rolling windows'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5',
    'delta.columnMapping.mode' = 'name'
);

-- ============================================
-- 3.3 Extreme Weather Events
-- ============================================
-- Purpose: Detection of extreme weather events for alerting
-- Strategy: Partition by city for event tracking
-- ============================================

CREATE TABLE IF NOT EXISTS weather.gold.extreme_weather_events (
    city STRING COMMENT 'City name',
    observation_time TIMESTAMP COMMENT 'Time of extreme event',
    temperature_celsius DOUBLE COMMENT 'Temperature during event',
    wind_speed DOUBLE COMMENT 'Wind speed during event',
    weather_main STRING COMMENT 'Weather type during event',
    weather_description STRING COMMENT 'Detailed weather description',
    event_type STRING COMMENT 'Type: Heatwave, Storm, Heavy Rain, Cold Wave',
    event_severity STRING COMMENT 'Severity: Low, Medium, High, Extreme',
    event_duration_minutes INT COMMENT 'Duration of event in minutes',
    affected_radius_km DOUBLE COMMENT 'Affected radius in kilometers',
    detection_time TIMESTAMP COMMENT 'Time event was detected',
    is_alert_sent BOOLEAN COMMENT 'Whether an alert was sent',
    alert_sent_time TIMESTAMP COMMENT 'Time alert was sent'
)
USING DELTA
PARTITIONED BY (city)
COMMENT 'Gold layer: Extreme weather events detection and tracking'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5',
    'delta.columnMapping.mode' = 'name'
);

-- ============================================
-- 4. ADDITIONAL OPTIMIZATION QUERIES
-- ============================================

-- Optimize Bronze table with Z-Order
OPTIMIZE weather.bronze.weather_bronze
ZORDER BY (city, ingestion_time);

-- Optimize Silver table with Z-Order
OPTIMIZE weather.silver.weather_silver
ZORDER BY (city, observation_time);

-- Optimize Gold tables with Z-Order
OPTIMIZE weather.gold.weather_daily_summary
ZORDER BY (city, observation_date);

OPTIMIZE weather.gold.weather_trend_analysis
ZORDER BY (city, observation_time);

OPTIMIZE weather.gold.extreme_weather_events
ZORDER BY (city, observation_time);

-- ============================================
-- 5. VACUUM (Clean up old files)
-- ============================================
-- Keep files for last 7 days (168 hours)
-- Run this periodically to reclaim storage

VACUUM weather.bronze.weather_bronze RETAIN 168 HOURS;
VACUUM weather.silver.weather_silver RETAIN 168 HOURS;
VACUUM weather.gold.weather_daily_summary RETAIN 168 HOURS;
VACUUM weather.gold.weather_trend_analysis RETAIN 168 HOURS;
VACUUM weather.gold.extreme_weather_events RETAIN 168 HOURS;

-- ============================================
-- 6. TABLE STATISTICS & METADATA
-- ============================================

-- View table details
DESCRIBE DETAIL weather.bronze.weather_bronze;
DESCRIBE DETAIL weather.silver.weather_silver;
DESCRIBE DETAIL weather.gold.weather_daily_summary;

-- View table history (for time travel)
DESCRIBE HISTORY weather.bronze.weather_bronze LIMIT 10;
DESCRIBE HISTORY weather.silver.weather_silver LIMIT 10;
DESCRIBE HISTORY weather.gold.weather_daily_summary LIMIT 10;

-- ============================================
-- 7. DROP TABLES (Use with caution!)
-- ============================================
-- Uncomment to drop tables for clean re-creation

-- DROP TABLE IF EXISTS weather.bronze.weather_bronze;
-- DROP TABLE IF EXISTS weather.silver.weather_silver;
-- DROP TABLE IF EXISTS weather.gold.weather_daily_summary;
-- DROP TABLE IF EXISTS weather.gold.weather_trend_analysis;
-- DROP TABLE IF EXISTS weather.gold.extreme_weather_events;

-- DROP SCHEMA IF EXISTS weather.bronze CASCADE;
-- DROP SCHEMA IF EXISTS weather.silver CASCADE;
-- DROP SCHEMA IF EXISTS weather.gold CASCADE;