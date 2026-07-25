-- Test for duplicate readings
-- Ensures no duplicate records for same city and time

SELECT 
    city,
    observation_time,
    COUNT(*) as duplicate_count
FROM {{ ref('stg_weather') }}
GROUP BY city, observation_time
HAVING COUNT(*) > 1