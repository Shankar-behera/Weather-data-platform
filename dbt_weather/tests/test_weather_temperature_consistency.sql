-- Test for temperature consistency across readings
-- Ensures that temperature doesn't change too rapidly

WITH temperature_changes AS (
    SELECT 
        city,
        observation_time,
        temperature_celsius,
        LAG(temperature_celsius, 1) OVER (
            PARTITION BY city 
            ORDER BY observation_time
        ) as prev_temp,
        ABS(temperature_celsius - LAG(temperature_celsius, 1) OVER (
            PARTITION BY city 
            ORDER BY observation_time
        )) as temp_change
    FROM {{ ref('stg_weather') }}
    WHERE observation_time >= CURRENT_DATE - INTERVAL '7 days'
)
SELECT 
    city,
    observation_time,
    temperature_celsius,
    prev_temp,
    temp_change
FROM temperature_changes
WHERE temp_change > 15  -- Temperature change > 15°C in an hour is unrealistic
  AND prev_temp IS NOT NULL
ORDER BY temp_change DESC