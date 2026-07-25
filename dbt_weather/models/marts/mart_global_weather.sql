{{
  config(
    materialized='table',
    schema='marts'
  )
}}

WITH city_data AS (
  SELECT
    city,
    observation_date,
    avg_temp,
    avg_humidity,
    avg_wind_speed,
    most_common_weather
  FROM {{ ref('mart_city_weather') }}
),

-- Global daily aggregates
daily_global AS (
  SELECT
    observation_date,
    COUNT(DISTINCT city) AS active_cities,
    AVG(avg_temp) AS global_avg_temp,
    MAX(avg_temp) AS global_max_temp,
    MIN(avg_temp) AS global_min_temp,
    AVG(avg_humidity) AS global_avg_humidity,
    AVG(avg_wind_speed) AS global_avg_wind_speed,
    -- Most common weather globally
    MODE(most_common_weather) AS global_most_common_weather
  FROM city_data
  GROUP BY observation_date
),

-- City extremes for each day
city_extremes AS (
  SELECT
    observation_date,
    FIRST_VALUE(city) OVER (
      PARTITION BY observation_date
      ORDER BY avg_temp DESC
    ) AS hottest_city,
    FIRST_VALUE(avg_temp) OVER (
      PARTITION BY observation_date
      ORDER BY avg_temp DESC
    ) AS hottest_city_temp,
    FIRST_VALUE(city) OVER (
      PARTITION BY observation_date
      ORDER BY avg_temp ASC
    ) AS coldest_city,
    FIRST_VALUE(avg_temp) OVER (
      PARTITION BY observation_date
      ORDER BY avg_temp ASC
    ) AS coldest_city_temp,
    FIRST_VALUE(city) OVER (
      PARTITION BY observation_date
      ORDER BY avg_humidity DESC
    ) AS highest_humidity_city,
    FIRST_VALUE(avg_humidity) OVER (
      PARTITION BY observation_date
      ORDER BY avg_humidity DESC
    ) AS highest_humidity_value
  FROM city_data
  QUALIFY ROW_NUMBER() OVER (PARTITION BY observation_date ORDER BY observation_date) = 1
)

SELECT
  dg.observation_date,
  dg.active_cities,
  dg.global_avg_temp,
  dg.global_max_temp,
  dg.global_min_temp,
  dg.global_avg_humidity,
  dg.global_avg_wind_speed,
  dg.global_most_common_weather,
  ce.hottest_city,
  ce.hottest_city_temp,
  ce.coldest_city,
  ce.coldest_city_temp,
  ce.highest_humidity_city,
  ce.highest_humidity_value,
  -- Weather distribution
  (
    SELECT JSON_GROUP_ARRAY(
      JSON_OBJECT(
        'weather', weather_main,
        'count', occurrence_count,
        'percentage', percentage
      )
    )
    FROM (
      SELECT
        weather_main,
        COUNT(*) AS occurrence_count,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS percentage
      FROM {{ ref('stg_weather') }}
      WHERE DATE(observation_time) = dg.observation_date
      GROUP BY weather_main
    )
  ) AS weather_distribution,
  CURRENT_TIMESTAMP() AS last_updated
FROM daily_global dg
LEFT JOIN city_extremes ce
  ON dg.observation_date = ce.observation_date
ORDER BY dg.observation_date DESC