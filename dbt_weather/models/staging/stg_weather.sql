{{
  config(
    materialized='table'
  )
}}

SELECT 
    city,
    temperature_celsius,
    humidity,
    pressure,
    wind_speed,
    weather_main,
    weather_description,
    observation_time,
    'sample' as ingestion_id,
    CURRENT_TIMESTAMP() as processed_time
FROM {{ source('weather', 'weather_gold') }}
WHERE is_valid = TRUE