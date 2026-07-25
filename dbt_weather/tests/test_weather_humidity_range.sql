-- Test: Humidity must be within 0-100 range
SELECT
  city,
  observation_time,
  humidity
FROM {{ ref('stg_weather') }}
WHERE humidity < 0 OR humidity > 100