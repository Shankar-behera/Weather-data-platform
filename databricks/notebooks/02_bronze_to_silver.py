# Databricks notebook source
# MAGIC %md
# MAGIC # Bronze to Silver Layer Transformation
# MAGIC 
# MAGIC This notebook transforms raw weather data from the Bronze layer 
# MAGIC into cleaned, validated Silver layer tables.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup and Configuration

# COMMAND ----------

from pyspark.sql import SparkSession
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window
from delta.tables import DeltaTable
import json
from datetime import datetime, timedelta

# Initialize Spark with Delta Lake
spark = SparkSession.builder \
    .appName("Bronze to Silver Transformation") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Configuration
catalog = "weather"
schema = "silver"
table_name = "weather_silver"
bronze_table = f"weather.bronze.weather_bronze"

# Silver table schema
silver_schema = StructType([
    StructField("city", StringType(), False),
    StructField("temperature_celsius", DoubleType(), False),
    StructField("humidity", IntegerType(), False),
    StructField("pressure", IntegerType(), False),
    StructField("wind_speed", DoubleType(), False),
    StructField("weather_main", StringType(), False),
    StructField("weather_description", StringType(), False),
    StructField("observation_time", TimestampType(), False),
    StructField("ingestion_id", StringType(), False),
    StructField("processed_time", TimestampType(), False),
    StructField("is_valid", BooleanType(), False),
    StructField("quality_checks_passed", IntegerType(), False),
    StructField("quality_checks_total", IntegerType(), False)
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Read Bronze Data

# COMMAND ----------

# Read latest bronze data (incremental processing)
print("Reading bronze layer data...")

# Get the latest ingestion timestamp for each city
latest_ingestion = spark.sql(f"""
    SELECT 
        source_city,
        MAX(ingestion_time) as latest_time
    FROM {bronze_table}
    GROUP BY source_city
""")

# Read only new data (last 24 hours)
bronze_df = spark.sql(f"""
    SELECT 
        ingestion_id,
        ingestion_time,
        source_city,
        raw_payload
    FROM {bronze_table}
    WHERE ingestion_time >= (SELECT MAX(latest_time) - INTERVAL 24 HOURS FROM latest_ingestion)
""")

print(f"Found {bronze_df.count()} bronze records to process")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Transformation Functions
 
# COMMAND ----------

def flatten_json_payload(df):
    """
    Flatten the JSON payload in raw_payload column.
    
    Args:
        df: DataFrame with raw_payload column
        
    Returns:
        DataFrame with flattened columns
    """
    # Parse JSON from raw_payload
    parsed_df = df.withColumn("parsed", from_json(col("raw_payload"), 
        StructType([
            StructField("city", StringType(), True),
            StructField("temperature", DoubleType(), True),
            StructField("humidity", IntegerType(), True),
            StructField("pressure", IntegerType(), True),
            StructField("wind_speed", DoubleType(), True),
            StructField("weather_main", StringType(), True),
            StructField("weather_description", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("api_response_time", DoubleType(), True)
        ])
    ))
    
    # Extract fields
    flattened_df = parsed_df.select(
        col("ingestion_id"),
        col("ingestion_time"),
        col("source_city").alias("source_city"),
        col("parsed.temperature"),
        col("parsed.humidity"),
        col("parsed.pressure"),
        col("parsed.wind_speed"),
        col("parsed.weather_main"),
        col("parsed.weather_description"),
        col("parsed.timestamp").cast(TimestampType()).alias("observation_time")
    )
    
    return flattened_df

def perform_quality_checks(df):
    """
    Perform data quality checks on the DataFrame.
    
    Args:
        df: DataFrame to check
        
    Returns:
        DataFrame with quality check columns
    """
    # Define quality checks
    df = df.withColumn("quality_checks_passed", 
        (col("temperature").isNotNull() & 
         col("temperature").between(-50, 60)).cast(IntegerType()) +
        (col("humidity").isNotNull() & 
         col("humidity").between(0, 100)).cast(IntegerType()) +
        (col("pressure").isNotNull() & 
         col("pressure").between(800, 1100)).cast(IntegerType()) +
        (col("wind_speed").isNotNull() & 
         col("wind_speed").between(0, 150)).cast(IntegerType()) +
        (col("weather_main").isNotNull() & 
         col("weather_description").isNotNull()).cast(IntegerType())
    )
    
    df = df.withColumn("quality_checks_total", lit(5))
    df = df.withColumn("is_valid", col("quality_checks_passed") == col("quality_checks_total"))
    
    return df

def remove_duplicates(df):
    """
    Remove duplicate records based on observation time and city.
    
    Args:
        df: DataFrame with duplicates
        
    Returns:
        DataFrame with duplicates removed
    """
    # Use window function to keep most recent record for each city and observation time
    window_spec = Window.partitionBy("source_city", "observation_time").orderBy(col("ingestion_time").desc())
    
    deduped_df = df.withColumn("row_num", row_number().over(window_spec)) \
        .filter(col("row_num") == 1) \
        .drop("row_num")
    
    return deduped_df

def standardize_timestamps(df):
    """
    Standardize timestamps to UTC.
    
    Args:
        df: DataFrame with timestamps
        
    Returns:
        DataFrame with standardized timestamps
    """
    return df.withColumn("observation_time_utc", 
        to_utc_timestamp(col("observation_time"), "UTC")) \
        .withColumn("processed_time_utc", 
        to_utc_timestamp(current_timestamp(), "UTC"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Transform Data

# COMMAND ----------

# Flatten JSON
print("Flattening JSON payloads...")
flattened_df = flatten_json_payload(bronze_df)

# Remove duplicates
print("Removing duplicates...")
deduped_df = remove_duplicates(flattened_df)

# Perform quality checks
print("Performing quality checks...")
quality_df = perform_quality_checks(deduped_df)

# Standardize timestamps
print("Standardizing timestamps...")
final_df = standardize_timestamps(quality_df)

# Rename columns to match silver schema
silver_df = final_df.select(
    col("source_city").alias("city"),
    col("temperature").alias("temperature_celsius"),
    col("humidity"),
    col("pressure"),
    col("wind_speed"),
    col("weather_main"),
    col("weather_description"),
    col("observation_time_utc").alias("observation_time"),
    col("ingestion_id"),
    col("processed_time_utc").alias("processed_time"),
    col("is_valid"),
    col("quality_checks_passed"),
    col("quality_checks_total")
)

print(f"Created {silver_df.count()} silver records")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Write to Silver Layer

# COMMAND ----------

# Write to Delta table
full_table_name = f"{catalog}.{schema}.{table_name}"

if silver_df.count() > 0:
    # Use merge for incremental updates
    if DeltaTable.isDeltaTable(spark, full_table_name):
        print("Merging data into existing silver table...")
        delta_table = DeltaTable.forName(spark, full_table_name)
        
        # Create temporary view for merge
        silver_df.createOrReplaceTempView("silver_updates")
        
        # Merge with deduplication
        delta_table.alias("target") \
            .merge(
                spark.table("silver_updates").alias("source"),
                "target.city = source.city AND target.observation_time = source.observation_time"
            ) \
            .whenMatchedUpdateAll() \
            .whenNotMatchedInsertAll() \
            .execute()
            
        print(f"Updated silver table with {silver_df.count()} records")
    else:
        print("Creating new silver table...")
        silver_df.write \
            .format("delta") \
            .mode("append") \
            .partitionBy("city") \
            .option("mergeSchema", "true") \
            .saveAsTable(full_table_name)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Quality Monitoring

# COMMAND ----------

# Quality monitoring metrics
print("Quality monitoring metrics:")

# Overall quality score
quality_stats = spark.sql(f"""
    SELECT 
        COUNT(*) as total_records,
        SUM(CASE WHEN is_valid THEN 1 ELSE 0 END) as valid_records,
        AVG(quality_checks_passed) as avg_quality_score,
        city,
        AVG(quality_checks_passed) as city_quality_score
    FROM {full_table_name}
    GROUP BY city
""")

display(quality_stats)

# Invalid records analysis
invalid_records = spark.sql(f"""
    SELECT 
        city,
        quality_checks_passed,
        COUNT(*) as count
    FROM {full_table_name}
    WHERE is_valid = false
    GROUP BY city, quality_checks_passed
    ORDER BY count DESC
""")

if invalid_records.count() > 0:
    print("WARNING: Found invalid records")
    display(invalid_records)

# Time-based quality trends
quality_trends = spark.sql(f"""
    SELECT 
        DATE(observation_time) as date,
        AVG(quality_checks_passed) as avg_quality_score,
        COUNT(*) as record_count
    FROM {full_table_name}
    GROUP BY DATE(observation_time)
    ORDER BY date DESC
    LIMIT 7
""")

print("Quality trends (last 7 days):")
display(quality_trends)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table Optimization

# COMMAND ----------

# Optimize silver table
print("Optimizing silver table...")
spark.sql(f"OPTIMIZE {full_table_name} ZORDER BY (city, observation_time)")

# Vacuum old files (keep last 7 days)
spark.sql(f"VACUUM {full_table_name} RETAIN 168 HOURS")

# Show table details
print("Table details:")
display(spark.sql(f"DESCRIBE DETAIL {full_table_name}"))

# COMMAND ----------

print("Silver layer transformation complete!")