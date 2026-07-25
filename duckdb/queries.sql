-- ==========================================
-- Weather Analytics Queries
-- ==========================================

-- 1. Basic Weather Summary
-- Get average, min, max temperature for each city
SELECT 
    city,
    COUNT(*) as total_readings,
    AVG(temperature_celsius) as avg_temp,
    MIN(temperature_celsius) as min_temp,
    MAX(temperature_celsius) as max_temp,
    AVG(humidity) as avg_humidity,
    AVG(wind_speed) as avg_wind_speed,
    MAX(observation_time) as last_update
FROM weather.weather_gold
WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY city
ORDER BY avg_temp DESC;

-- 2. Daily Temperature Trends
-- Get daily temperature trends with rolling averages
WITH daily_stats AS (
    SELECT 
        city,
        DATE(observation_time) as observation_date,
        AVG(temperature_celsius) as avg_temp,
        MIN(temperature_celsius) as min_temp,
        MAX(temperature_celsius) as max_temp,
        COUNT(*) as reading_count
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY city, DATE(observation_time)
)
SELECT 
    city,
    observation_date,
    avg_temp,
    min_temp,
    max_temp,
    reading_count,
    AVG(avg_temp) OVER (
        PARTITION BY city 
        ORDER BY observation_date 
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) as rolling_7d_avg,
    AVG(avg_temp) OVER (
        PARTITION BY city 
        ORDER BY observation_date 
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) as rolling_30d_avg
FROM daily_stats
ORDER BY city, observation_date DESC;

-- 3. City Comparison
-- Compare weather conditions across cities
SELECT 
    city,
    AVG(temperature_celsius) as avg_temp,
    AVG(humidity) as avg_humidity,
    AVG(wind_speed) as avg_wind,
    mode(weather_main) as most_common_weather,
    COUNT(DISTINCT DATE(observation_time)) as active_days,
    DATEDIFF('days', MIN(observation_time), MAX(observation_time)) as data_span_days
FROM weather.weather_gold
WHERE observation_time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY city
ORDER BY avg_temp DESC;

-- 4. Weather Distribution
-- Get weather type distribution by city
SELECT 
    city,
    weather_main,
    COUNT(*) as occurrence_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY city), 2) as percentage
FROM weather.weather_gold
WHERE observation_time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY city, weather_main
ORDER BY city, occurrence_count DESC;

-- 5. Extreme Weather Events
-- Detect extreme weather events
WITH weather_events AS (
    SELECT 
        city,
        observation_time,
        temperature_celsius,
        wind_speed,
        weather_main,
        weather_description,
        CASE 
            WHEN temperature_celsius > 35 THEN 'Heatwave'
            WHEN temperature_celsius < -10 THEN 'Freezing'
            WHEN wind_speed > 50 THEN 'Storm'
            WHEN weather_main = 'Rain' AND humidity > 80 THEN 'Heavy Rain'
            ELSE 'Normal'
        END as event_type
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
)
SELECT 
    city,
    event_type,
    COUNT(*) as event_count,
    MIN(observation_time) as first_event,
    MAX(observation_time) as last_event,
    AVG(temperature_celsius) as avg_temp_during_events
FROM weather_events
WHERE event_type != 'Normal'
GROUP BY city, event_type
ORDER BY event_count DESC;

-- 6. Data Quality Metrics
-- Check data completeness and freshness
WITH daily_counts AS (
    SELECT 
        city,
        DATE(observation_time) as date,
        COUNT(*) as hourly_readings
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY city, DATE(observation_time)
),
freshness AS (
    SELECT 
        city,
        MAX(observation_time) as latest_update,
        DATEDIFF('hours', MAX(observation_time), CURRENT_TIMESTAMP) as hours_since_update
    FROM weather.weather_gold
    GROUP BY city
)
SELECT 
    dc.city,
    COUNT(DISTINCT dc.date) as days_with_data,
    AVG(dc.hourly_readings) as avg_hourly_readings,
    MIN(dc.hourly_readings) as min_hourly_readings,
    MAX(dc.hourly_readings) as max_hourly_readings,
    f.latest_update,
    f.hours_since_update,
    CASE 
        WHEN f.hours_since_update > 4 THEN 'Stale'
        WHEN COUNT(DISTINCT dc.date) < 7 THEN 'Incomplete'
        ELSE 'Healthy'
    END as data_health_status
FROM daily_counts dc
LEFT JOIN freshness f ON dc.city = f.city
GROUP BY dc.city, f.latest_update, f.hours_since_update
ORDER BY data_health_status DESC;

-- 7. Hourly Patterns
-- Analyze hourly weather patterns
SELECT 
    city,
    EXTRACT(HOUR FROM observation_time) as hour_of_day,
    AVG(temperature_celsius) as avg_temp,
    AVG(humidity) as avg_humidity,
    AVG(wind_speed) as avg_wind,
    COUNT(*) as readings,
    mode(weather_main) as typical_weather
FROM weather.weather_gold
WHERE observation_time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY city, EXTRACT(HOUR FROM observation_time)
ORDER BY city, hour_of_day;

-- 8. Temperature Anomalies
-- Detect temperature anomalies (deviations from average)
WITH city_avg AS (
    SELECT 
        city,
        AVG(temperature_celsius) as city_avg_temp,
        STDDEV(temperature_celsius) as city_std_temp
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '30 days'
    GROUP BY city
),
current_readings AS (
    SELECT 
        w.city,
        w.observation_time,
        w.temperature_celsius,
        c.city_avg_temp,
        c.city_std_temp,
        (w.temperature_celsius - c.city_avg_temp) / c.city_std_temp as z_score
    FROM weather.weather_gold w
    JOIN city_avg c ON w.city = c.city
    WHERE w.observation_time >= CURRENT_DATE - INTERVAL '1 day'
)
SELECT 
    city,
    observation_time,
    temperature_celsius,
    city_avg_temp,
    z_score,
    CASE 
        WHEN z_score > 2 THEN 'Significantly Above Average'
        WHEN z_score < -2 THEN 'Significantly Below Average'
        WHEN z_score > 1 THEN 'Above Average'
        WHEN z_score < -1 THEN 'Below Average'
        ELSE 'Normal'
    END as anomaly_status
FROM current_readings
WHERE ABS(z_score) > 1
ORDER BY ABS(z_score) DESC;

-- 9. Weather Transition Analysis
-- Analyze weather transitions and changes
WITH transitions AS (
    SELECT 
        city,
        observation_time,
        weather_main,
        LAG(weather_main, 1) OVER (
            PARTITION BY city 
            ORDER BY observation_time
        ) as previous_weather,
        CASE 
            WHEN LAG(weather_main, 1) OVER (
                PARTITION BY city 
                ORDER BY observation_time
            ) != weather_main THEN 1
            ELSE 0
        END as weather_changed
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '30 days'
)
SELECT 
    city,
    COUNT(*) as total_readings,
    SUM(weather_changed) as weather_changes,
    ROUND(SUM(weather_changed) * 100.0 / COUNT(*), 2) as change_percentage,
    -- Most common transition
    mode(previous_weather || '→' || weather_main) as most_common_transition
FROM transitions
WHERE previous_weather IS NOT NULL
GROUP BY city
ORDER BY change_percentage DESC;

-- 10. Global Weather Dashboard
-- Comprehensive global weather dashboard
WITH city_metrics AS (
    SELECT 
        city,
        AVG(temperature_celsius) as avg_temp,
        MAX(temperature_celsius) as max_temp,
        MIN(temperature_celsius) as min_temp,
        AVG(humidity) as avg_humidity,
        AVG(wind_speed) as avg_wind,
        mode(weather_main) as typical_weather,
        COUNT(*) as reading_count,
        MAX(observation_time) as last_updated
    FROM weather.weather_gold
    WHERE observation_time >= CURRENT_DATE - INTERVAL '1 day'
    GROUP BY city
)
SELECT 
    'Global Summary' as summary_type,
    COUNT(DISTINCT city) as active_cities,
    AVG(avg_temp) as global_avg_temp,
    MAX(max_temp) as global_max_temp,
    MIN(min_temp) as global_min_temp,
    AVG(avg_humidity) as global_avg_humidity,
    SUM(reading_count) as total_readings,
    mode(typical_weather) as global_most_common_weather,
    MAX(last_updated) as latest_update
FROM city_metrics;