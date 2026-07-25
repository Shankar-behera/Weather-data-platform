-- Test for city coverage
-- Ensures all cities have data in the last 24 hours

WITH city_coverage AS (
    SELECT 
        city,
        COUNT(*) as reading_count,
        MAX(observation_time) as latest_reading
    FROM {{ ref('stg_weather') }}
    WHERE observation_time >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
    GROUP BY city
)
SELECT 
    city,
    reading_count,
    latest_reading,
    CASE 
        WHEN reading_count = 0 THEN 'No Data'
        WHEN reading_count < 12 THEN 'Partial Data'
        ELSE 'Complete Data'
    END as coverage_status
FROM city_coverage
WHERE reading_count = 0 OR reading_count < 12
ORDER BY reading_count ASC