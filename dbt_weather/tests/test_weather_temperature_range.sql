-- Test: Temperature must be within reasonable range
SELECT
  city,
  observation_time,
  temperature_celsius
FROM {{ ref('stg_weather') }}
WHERE temperature_celsius < -50 OR temperature_celsius > 60