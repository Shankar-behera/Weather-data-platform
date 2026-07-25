
  
    
        create or replace table `weather`.`bronze_staging`.`stg_weather`
      
      
    using delta
  
      
      
      
      
      
      
      
      
      as
      ﻿

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
FROM `weather`.`weather`.`weather_gold`
WHERE is_valid = TRUE
  