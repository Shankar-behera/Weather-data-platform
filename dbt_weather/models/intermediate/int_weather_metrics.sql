{{
  config(
    materialized='table',
    schema='intermediate'
  )
}}

WITH weather_data AS (
  SELECT
    city,
    DATE(observation_time) AS observation_date,
    observation_time,
    temperature_celsius,
    humidity,
    wind_speed,
    weather_main,
    weather_description
  FROM {{ ref('stg_weather') }}
),

-- Calculate daily statistics
daily_stats AS (
  SELECT
    city,
    observation_date,
    COUNT(*) AS hourly_readings,
    AVG(temperature_celsius) AS avg_temp,
    MAX(temperature_celsius) AS max_temp,
    MIN(temperature_celsius) AS min_temp,
    AVG(humidity) AS avg_humidity,
    AVG(wind_speed) AS avg_wind_speed,
    MODE(weather_main) AS most_common_weather
  FROM weather_data
  GROUP BY city, observation_date
),

-- Calculate rolling averages
rolling_stats AS (
  SELECT
    city,
    observation_time,
    temperature_celsius,
    AVG(temperature_celsius) OVER (
      PARTITION BY city
      ORDER BY observation_time
      ROWS BETWEEN 23 PRECEDING AND CURRENT ROW
    ) AS rolling_24h_avg_temp,
    AVG(temperature_celsius) OVER (
      PARTITION BY city
      ORDER BY observation_time
      ROWS BETWEEN 167 PRECEDING AND CURRENT ROW
    ) AS rolling_7d_avg_temp,
    LAG(temperature_celsius, 1) OVER (
      PARTITION BY city
      ORDER BY observation_time
    ) AS prev_temp,
    temperature_celsius - LAG(temperature_celsius, 1) OVER (
      PARTITION BY city
      ORDER BY observation_time
    ) AS temp_change
  FROM weather_data
),

-- Classification
classified AS (
  SELECT
    city,
    observation_time,
    temperature_celsius,
    rolling_24h_avg_temp,
    rolling_7d_avg_temp,
    CASE
      WHEN temp_change > 2 THEN 'Rising'
      WHEN temp_change < -2 THEN 'Falling'
      ELSE 'Stable'
    END AS trend_direction,
    CASE
      WHEN temperature_celsius < 0 THEN 'Freezing'
      WHEN temperature_celsius < 10 THEN 'Cold'
      WHEN temperature_celsius < 20 THEN 'Mild'
      WHEN temperature_celsius < 30 THEN 'Warm'
      ELSE 'Hot'
    END AS temperature_category
  FROM rolling_stats
)

SELECT
  ds.city,
  ds.observation_date,
  ds.hourly_readings,
  ds.avg_temp,
  ds.max_temp,
  ds.min_temp,
  ds.avg_humidity,
  ds.avg_wind_speed,
  ds.most_common_weather,
  cls.temperature_category,
  cls.rolling_24h_avg_temp,
  cls.rolling_7d_avg_temp,
  cls.trend_direction,
  CURRENT_TIMESTAMP() AS last_updated
FROM daily_stats ds
LEFT JOIN classified cls
  ON ds.city = cls.city
  AND ds.observation_date = DATE(cls.observation_time)