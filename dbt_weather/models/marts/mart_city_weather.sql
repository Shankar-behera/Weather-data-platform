{{
  config(
    materialized='table',
    schema='marts',
    partition_by={'field': 'observation_date', 'data_type': 'date'},
    unique_key=['city', 'observation_date']
  )
}}

WITH city_metrics AS (
  SELECT
    city,
    observation_date,
    avg_temp,
    max_temp,
    min_temp,
    avg_humidity,
    avg_wind_speed,
    hourly_readings,
    most_common_weather,
    temperature_category,
    rolling_24h_avg_temp,
    rolling_7d_avg_temp,
    trend_direction,
    last_updated,
    -- Additional derived metrics
    avg_temp - rolling_7d_avg_temp AS temp_vs_7d_avg,
    CASE
      WHEN avg_temp > 30 AND avg_humidity > 70 THEN 'High Heat & Humidity'
      WHEN avg_temp > 30 THEN 'Heatwave Risk'
      WHEN avg_wind_speed > 50 THEN 'High Wind Alert'
      WHEN most_common_weather = 'Rain' AND avg_humidity > 80 THEN 'Heavy Rain Risk'
      ELSE 'Normal'
    END AS weather_alert
  FROM {{ ref('int_weather_metrics') }}
),

-- Add ranking metrics
ranked AS (
  SELECT
    *,
    RANK() OVER (ORDER BY avg_temp DESC) AS temp_rank_global,
    RANK() OVER (PARTITION BY observation_date ORDER BY avg_temp DESC) AS temp_rank_daily,
    PERCENT_RANK() OVER (ORDER BY avg_temp) AS temp_percentile
  FROM city_metrics
)

SELECT
  city,
  observation_date,
  avg_temp,
  max_temp,
  min_temp,
  avg_humidity,
  avg_wind_speed,
  hourly_readings,
  most_common_weather,
  temperature_category,
  rolling_24h_avg_temp,
  rolling_7d_avg_temp,
  trend_direction,
  temp_vs_7d_avg,
  weather_alert,
  temp_rank_global,
  temp_rank_daily,
  temp_percentile,
  last_updated
FROM ranked