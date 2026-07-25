-- Test for seasonal pattern consistency
-- Ensures weather patterns are consistent with expected seasonal norms

WITH seasonal_metrics AS (
    SELECT 
        city,
        EXTRACT(MONTH FROM observation_time) as month,
        AVG(temperature_celsius) as avg_temp,
        AVG(humidity) as avg_humidity,
        COUNT(*) as sample_size
    FROM {{ ref('stg_weather') }}
    WHERE observation_time >= CURRENT_DATE - INTERVAL '90 days'
    GROUP BY city, EXTRACT(MONTH FROM observation_time)
)
SELECT 
    city,
    month,
    avg_temp,
    avg_humidity,
    sample_size,
    CASE 
        WHEN month IN (6, 7, 8) AND avg_temp < 10 THEN 'Unusually Cold Summer'
        WHEN month IN (12, 1, 2) AND avg_temp > 15 THEN 'Unusually Warm Winter'
        WHEN month IN (3, 4, 5) AND avg_temp < 0 THEN 'Unusually Cold Spring'
        WHEN month IN (9, 10, 11) AND avg_temp > 25 THEN 'Unusually Warm Autumn'
        ELSE 'Normal Season'
    END as seasonal_anomaly
FROM seasonal_metrics
WHERE seasonal_anomaly != 'Normal Season'