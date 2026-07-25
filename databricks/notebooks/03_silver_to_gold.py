# Databricks notebook source
# MAGIC %md
# MAGIC # Silver to Gold Layer Transformation
# MAGIC 
# MAGIC This notebook creates business-ready analytical models from the Silver layer.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup and Configuration

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.window import Window
from delta.tables import DeltaTable
from datetime import datetime, timedelta

# Initialize Spark with Delta Lake
spark = SparkSession.builder \
    .appName("Silver to Gold Transformation") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("sppark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Configuration
catalog = "weather"
schema = "gold"
silver_table = f"weather.silver.weather_silver"

# Gold table names
daily_summary_table = "weather_daily_summary"
trend_analysis_table = "weather_trend_analysis"
extreme_events_table = "extreme_weather_events"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read Silver Data

# COMMAND ----------

# Read silver data
print("Reading silver layer data...")

silver_df = spark.sql(f"""
    SELECT 
        city,
        temperature_celsius,
        humidity,
        pressure,
        wind_speed,
        weather_main,
        weather_description,
        observation_time,
        is_valid
    FROM {silver_table}
    WHERE is_valid = true
      AND observation_time >= DATE_SUB(CURRENT_DATE(), 30)  -- Last 30 days
""")

print(f"Found {silver_df.count()} valid silver records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Daily Summary Metrics

# COMMAND ----------

# Create daily summary metrics
print("Creating daily weather summary...")

daily_summary_df = silver_df.groupBy(
    col("city"),
    col("observation_time").cast("date").alias("observation_date")
).agg(
    count("*").alias("record_count"),
    avg("temperature_celsius").alias("avg_temperature"),
    max("temperature_celsius").alias("max_temperature"),
    min("temperature_celsius").alias("min_temperature"),
    avg("humidity").alias("avg_humidity"),
    avg("wind_speed").alias("avg_wind_speed"),
    mode("weather_main").alias("most_common_weather"),
    collect_list("weather_main").alias("weather_types")
).withColumn(
    "last_updated", current_timestamp()
)

# Add temperature classification
daily_summary_df = daily_summary_df.withColumn(
    "temp_category",
    when(col("avg_temperature") < 0, "Freezing")
    .when(col("avg_temperature") < 10, "Cold")
    .when(col("avg_temperature") < 20, "Mild")
    .when(col("avg_temperature") < 30, "Warm")
    .otherwise("Hot")
)

print(f"Created {daily_summary_df.count()} daily summary records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Trend Analysis

# COMMAND ----------

# Create trend analysis with window functions
print("Creating weather trend analysis...")

# Define window specifications
window_24h = Window.partitionBy("city").orderBy("observation_time") \
    .rangeBetween(-86400, 0)  # 24 hours in seconds

window_7d = Window.partitionBy("city").orderBy("observation_time") \
    .rangeBetween(-604800, 0)  # 7 days in seconds

# Calculate rolling averages
trend_df = silver_df.withColumn(
    "rolling_24h_avg_temp",
    avg("temperature_celsius").over(window_24h)
).withColumn(
    "rolling_7d_avg_temp",
    avg("temperature_celsius").over(window_7d)
).withColumn(
    "temp_change_24h",
    col("temperature_celsius") - lag("temperature_celsius", 1).over(
        Window.partitionBy("city").orderBy("observation_time")
    )
).withColumn(
    "temp_change_pct",
    when(lag("temperature_celsius", 1).over(
        Window.partitionBy("city").orderBy("observation_time")
    ) != 0,
        (col("temperature_celsius") - lag("temperature_celsius", 1).over(
            Window.partitionBy("city").orderBy("observation_time")
        )) / lag("temperature_celsius", 1).over(
            Window.partitionBy("city").orderBy("observation_time")
        ) * 100
    ).otherwise(0)
)

# Add trend classification
trend_df = trend_df.withColumn(
    "trend_direction",
    when(col("temp_change_24h") > 2, "Rising")
    .when(col("temp_change_24h") < -2, "Falling")
    .otherwise("Stable")
)

# Create final trend table
trend_final_df = trend_df.select(
    "city",
    "observation_time",
    "temperature_celsius",
    "rolling_24h_avg_temp",
    "rolling_7d_avg_temp",
    "temp_change_24h",
    "temp_change_pct",
    "trend_direction",
    current_timestamp().alias("last_updated")
)

print(f"Created {trend_final_df.count()} trend analysis records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Extreme Weather Events Detection

# COMMAND ----------

# Detect extreme weather events
print("Detecting extreme weather events...")

extreme_df = silver_df.withColumn(
    "is_heatwave",
    when((col("temperature_celsius") > 35) & (col("temperature_celsius") > lit(30)), True)
    .otherwise(False)
).withColumn(
    "is_storm",
    when((col("wind_speed") > 50) | (col("weather_main") == "Thunderstorm"), True)
    .otherwise(False)
).withColumn(
    "is_heavy_rain",
    when(col("weather_main") == "Rain", True)
    .otherwise(False)
).withColumn(
    "event_type",
    when(col("is_heatwave"), "Heatwave")
    .when(col("is_storm"), "Storm")
    .when(col("is_heavy_rain"), "Heavy Rain")
    .otherwise("Normal")
)

# Filter only extreme events
extreme_events_df = extreme_df.filter(
    (col("is_heatwave") == True) |
    (col("is_storm") == True) |
    (col("is_heavy_rain") == True)
).select(
    "city",
    "observation_time",
    "temperature_celsius",
    "wind_speed",
    "weather_main",
    "weather_description",
    "event_type",
    current_timestamp().alias("detection_time")
)

print(f"Detected {extreme_events_df.count()} extreme weather events")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Gold Layer

# COMMAND ----------

def write_to_gold(df, table_name, partition_cols=None):
    """Helper function to write DataFrame to Gold layer Delta table."""
    full_table_name = f"{catalog}.{schema}.{table_name}"
    
    if df.count() > 0:
        if DeltaTable.isDeltaTable(spark, full_table_name):
            print(f"Merging data into {table_name}...")
            delta_table = DeltaTable.forName(spark, full_table_name)
            
            # Create temporary view
            df.createOrReplaceTempView(f"{table_name}_updates")
            
            # Merge based on key
            if "city" in df.columns and "observation_date" in df.columns:
                delta_table.alias("target") \
                    .merge(
                        spark.table(f"{table_name}_updates").alias("source"),
                        "target.city = source.city AND target.observation_date = source.observation_date"
                    ) \
                    .whenMatchedUpdateAll() \
                    .whenNotMatchedInsertAll() \
                    .execute()
            elif "city" in df.columns and "observation_time" in df.columns:
                delta_table.alias("target") \
                    .merge(
                        spark.table(f"{table_name}_updates").alias("source"),
                        "target.city = source.city AND target.observation_time = source.observation_time"
                    ) \
                    .whenMatchedUpdateAll() \
                    .whenNotMatchedInsertAll() \
                    .execute()
            else:
                print(f"Appending to {table_name} (no merge key)")
                df.write \
                    .format("delta") \
                    .mode("append") \
                    .option("mergeSchema", "true") \
                    .saveAsTable(full_table_name)
        else:
            print(f"Creating new table: {table_name}")
            write_options = {
                "format": "delta",
                "mode": "overwrite",
                "option": {"mergeSchema": "true"}
            }
            if partition_cols:
                write_options["partitionBy"] = partition_cols
            
            df.write \
                .format("delta") \
                .mode("overwrite") \
                .partitionBy(*partition_cols) \
                .option("mergeSchema", "true") \
                .saveAsTable(full_table_name)

# Write daily summary
write_to_gold(
    daily_summary_df,
    daily_summary_table,
    partition_cols=["city", "observation_date"]
)

# Write trend analysis
write_to_gold(
    trend_final_df,
    trend_analysis_table,
    partition_cols=["city"]
)

# Write extreme events
write_to_gold(
    extreme_events_df,
    extreme_events_table,
    partition_cols=["city"]
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold Layer Analytics

# COMMAND ----------

# Create analytical views
print("Creating analytical views...")

# City comparison dashboard
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW city_comparison AS
SELECT 
    city,
    AVG(avg_temperature) as avg_temperature,
    AVG(avg_humidity) as avg_humidity,
    AVG(record_count) as avg_daily_records,
    COUNT(DISTINCT observation_date) as days_of_data
FROM {catalog}.{schema}.{daily_summary_table}
GROUP BY city
""")

print("City comparison view created")

# Weather distribution
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW weather_distribution AS
SELECT 
    city,
    weather_main,
    COUNT(*) as occurrence_count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY city), 2) as percentage
FROM {silver_table}
WHERE is_valid = true
GROUP BY city, weather_main
""")

print("Weather distribution view created")

# Recent trends
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW recent_trends AS
SELECT 
    city,
    observation_time,
    temperature_celsius,
    rolling_24h_avg_temp,
    rolling_7d_avg_temp,
    trend_direction
FROM {catalog}.{schema}.{trend_analysis_table}
WHERE observation_time >= DATE_SUB(CURRENT_DATE(), 7)
ORDER BY city, observation_time DESC
""")

print("Recent trends view created")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Gold Layer Optimization

# COMMAND ----------

# Optimize all gold tables
print("Optimizing gold tables...")

for table in [daily_summary_table, trend_analysis_table, extreme_events_table]:
    full_table_name = f"{catalog}.{schema}.{table}"
    print(f"Optimizing {table}...")
    spark.sql(f"OPTIMIZE {full_table_name}")
    spark.sql(f"VACUUM {full_table_name} RETAIN 168 HOURS")

# Show table statistics
print("Gold table statistics:")

for table in [daily_summary_table, trend_analysis_table, extreme_events_table]:
    full_table_name = f"{catalog}.{schema}.{table}"
    print(f"\n{table}:")
    display(spark.sql(f"DESCRIBE DETAIL {full_table_name}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Quality Validation

# COMMAND ----------

# Validate gold layer data
print("Validating gold layer data...")

# Check for missing data
missing_checks = spark.sql(f"""
SELECT 
    city,
    COUNT(*) as total_days,
    SUM(CASE WHEN avg_temperature IS NULL THEN 1 ELSE 0 END) as missing_temp,
    SUM(CASE WHEN avg_humidity IS NULL THEN 1 ELSE 0 END) as missing_humidity
FROM {catalog}.{schema}.{daily_summary_table}
WHERE observation_date >= DATE_SUB(CURRENT_DATE(), 7)
GROUP BY city
""")

print("Data completeness (last 7 days):")
display(missing_checks)

# Check for data freshness
freshness_check = spark.sql(f"""
SELECT 
    city,
    MAX(observation_date) as latest_data_date,
    DATEDIFF(CURRENT_DATE(), MAX(observation_date)) as days_old
FROM {catalog}.{schema}.{daily_summary_table}
GROUP BY city
""")

print("Data freshness:")
display(freshness_check)

# Extreme events summary
print("Extreme events summary:")
display(spark.sql(f"""
SELECT 
    city,
    event_type,
    COUNT(*) as event_count,
    MIN(observation_time) as first_event,
    MAX(observation_time) as last_event
FROM {catalog}.{schema}.{extreme_events_table}
GROUP BY city, event_type
ORDER BY city, event_count DESC
"""))

# COMMAND ----------

print("Gold layer transformation complete!")