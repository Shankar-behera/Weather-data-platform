# Databricks notebook source
# MAGIC %md
# MAGIC # Weather Data Ingestion - Bronze Layer
# MAGIC 
# MAGIC This notebook handles the ingestion of weather data from OpenWeatherMap API
# MAGIC into the Delta Lake Bronze layer.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup and Configuration

# COMMAND ----------

import requests
import json
import time
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType, TimestampType
from delta.tables import DeltaTable

# Initialize Spark session with Delta Lake support
spark = SparkSession.builder \
    .appName("Weather Ingestion") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# Configuration from environment variables
api_key = dbutils.secrets.get(scope="weather", key="openweather_api_key")
base_url = "https://api.openweathermap.org/data/2.5"

cities = [
    "London", "New York", "Tokyo", "Sydney",
    "Berlin", "Mumbai", "Singapore", "Dubai"
]

catalog = "weather"
schema = "bronze"
table_name = "weather_bronze"

# Schema definition for bronze table
bronze_schema = StructType([
    StructField("ingestion_id", StringType(), True),
    StructField("ingestion_time", TimestampType(), True),
    StructField("source", StringType(), True),
    StructField("source_city", StringType(), True),
    StructField("raw_payload", StringType(), True),
    StructField("api_response_time", DoubleType(), True)
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Extraction Functions

# COMMAND ----------

def fetch_weather_data(city: str) -> Optional[Dict]:
    """
    Fetch weather data for a specific city from OpenWeatherMap API.
    
    Args:
        city: City name
        
    Returns:
        Dictionary with weather data or None if failed
    """
    try:
        params = {
            "q": city,
            "appid": api_key,
            "units": "metric"
        }
        
        start_time = time.time()
        response = requests.get(f"{base_url}/weather", params=params, timeout=10)
        elapsed_time = (time.time() - start_time) * 1000
        
        if response.status_code == 200:
            data = response.json()
            return {
                "city": city,
                "temperature": data["main"]["temp"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "wind_speed": data["wind"]["speed"],
                "weather_main": data["weather"][0]["main"],
                "weather_description": data["weather"][0]["description"],
                "timestamp": datetime.fromtimestamp(data["dt"]),
                "api_response_time": elapsed_time
            }
        else:
            print(f"Failed to fetch {city}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error fetching {city}: {str(e)}")
        return None

def fetch_all_cities() -> List[Dict]:
    """
    Fetch weather data for all configured cities.
    
    Returns:
        List of weather data dictionaries
    """
    results = []
    for city in cities:
        print(f"Fetching weather for {city}")
        data = fetch_weather_data(city)
        if data:
            results.append(data)
    return results

# COMMAND ----------

# MAGIC %md
# MAGIC ## Bronze Layer Ingestion

# COMMAND ----------

def create_bronze_records(weather_data: List[Dict]) -> List[Dict]:
    """
    Transform weather data into bronze layer records.
    
    Args:
        weather_data: List of weather data dictionaries
        
    Returns:
        List of bronze layer records
    """
    records = []
    for data in weather_data:
        record = {
            "ingestion_id": str(uuid.uuid4()),
            "ingestion_time": datetime.utcnow(),
            "source": "openweathermap",
            "source_city": data["city"],
            "raw_payload": json.dumps(data),
            "api_response_time": data.get("api_response_time", 0.0)
        }
        records.append(record)
    return records

# COMMAND ----------

# MAGIC %md
# MAGIC ## Main Execution

# COMMAND ----------

# Fetch weather data
print("Fetching weather data for all cities...")
weather_data = fetch_all_cities()
print(f"Fetched data for {len(weather_data)} cities")

# Create bronze records
bronze_records = create_bronze_records(weather_data)

# Create DataFrame
df_bronze = spark.createDataFrame(bronze_records, schema=bronze_schema)

# Write to Delta table
full_table_name = f"{catalog}.{schema}.{table_name}"

# Use MERGE for deduplication
if DeltaTable.isDeltaTable(spark, full_table_name):
    print("Merging data into existing table...")
    delta_table = DeltaTable.forName(spark, full_table_name)
    
    # Create source view for merge
    df_bronze.createOrReplaceTempView("source_data")
    
    delta_table.alias("target") \
        .merge(
            spark.table("source_data").alias("source"),
            "target.ingestion_id = source.ingestion_id"
        ) \
        .whenNotMatchedInsertAll() \
        .execute()
else:
    print("Creating new table...")
    df_bronze.write \
        .format("delta") \
        .mode("append") \
        .partitionBy("source", "source_city") \
        .option("mergeSchema", "true") \
        .saveAsTable(full_table_name)

print(f"Successfully ingested {len(bronze_records)} records into bronze layer")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Table Optimization

# COMMAND ----------

# Optimize the table
print("Optimizing bronze table...")
spark.sql(f"OPTIMIZE {full_table_name} ZORDER BY (source_city)")

# Vacuum old files (keep last 7 days)
spark.sql(f"VACUUM {full_table_name} RETAIN 168 HOURS")

# Show table statistics
print("Table statistics:")
display(spark.sql(f"DESCRIBE DETAIL {full_table_name}"))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Data Quality Checks

# COMMAND ----------

# Data quality validation
print("Running data quality checks...")

# Check for null values
null_checks = spark.sql(f"""
    SELECT 
        COUNT(*) as total_rows,
        SUM(CASE WHEN raw_payload IS NULL THEN 1 ELSE 0 END) as null_payloads,
        SUM(CASE WHEN source_city IS NULL THEN 1 ELSE 0 END) as null_cities
    FROM {full_table_name}
""")

display(null_checks)

# Check duplicate ingestion IDs
duplicate_check = spark.sql(f"""
    SELECT 
        ingestion_id,
        COUNT(*) as duplicate_count
    FROM {full_table_name}
    GROUP BY ingestion_id
    HAVING COUNT(*) > 1
""")

if duplicate_check.count() > 0:
    print(f"WARNING: Found {duplicate_check.count()} duplicate ingestion IDs")
    display(duplicate_check)
else:
    print("No duplicate ingestion IDs found")

# Show recent ingestions
print("Recent ingestions:")
display(spark.sql(f"""
    SELECT 
        source_city,
        MAX(ingestion_time) as last_ingestion,
        COUNT(*) as total_records
    FROM {full_table_name}
    GROUP BY source_city
    ORDER BY last_ingestion DESC
"""))

# COMMAND ----------

print("Bronze layer ingestion complete!")