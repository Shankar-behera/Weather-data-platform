{{
  config(
    materialized='table'
  )
}}
SELECT 
    city,
    observation_time,
    temperature_celsius,
    humidity,
    wind_speed,
    weather_main,
    CURRENT_TIMESTAMP() as created_at
FROM {{ ref('stg_weather') }}
WHERE 1=0  -- Returns empty result set
