"""
Databricks Delta Lake client for data ingestion and management.
"""

import logging
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from databricks.sql import connect
from databricks.sql.client import Connection

from .config import config
from .models import RawWeatherRecord, SilverWeatherRecord


class DatabricksClient:
    """Client for interacting with Databricks Delta Lake."""
    
    def __init__(self):
        """Initialize Databricks client."""
        self.host = config.DATABRICKS_HOST
        self.token = config.DATABRICKS_TOKEN
        self.http_path = config.DATABRICKS_HTTP_PATH
        self.catalog = config.DATABRICKS_CATALOG
        self.schema = config.DATABRICKS_SCHEMA
        self.logger = logging.getLogger(__name__)
        
        self._connection = None
    
    def get_connection(self) -> Connection:
        """Get or create Databricks SQL connection."""
        if self._connection is None:
            try:
                self._connection = connect(
                    server_hostname=self.host,
                    http_path=self.http_path,
                    access_token=self.token,
                    catalog=self.catalog,
                    schema=self.schema
                )
                self.logger.info("Connected to Databricks")
            except Exception as e:
                self.logger.error(f"Failed to connect to Databricks: {str(e)}")
                raise
        return self._connection
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """
        Execute SQL query on Databricks.
        Handles both SELECT (returns rows) and DDL statements (returns empty list).
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Check if query returns results (SELECT statements)
            if cursor.description is None:
                return []
            
            # For SELECT statements, fetch results
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            return results
            
        finally:
            cursor.close()
    
    def create_bronze_table(self):
        """Create bronze table if it doesn't exist."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.catalog}.{self.schema}.{config.BRONZE_TABLE} (
            ingestion_id STRING,
            ingestion_time TIMESTAMP,
            city STRING,
            source STRING,
            source_city STRING,
            raw_payload STRING,
            api_response_time DOUBLE
        )
        USING DELTA
        PARTITIONED BY (source, source_city)
        TBLPROPERTIES (
            'delta.autoOptimize.optimizeWrite' = 'true',
            'delta.autoOptimize.autoCompact' = 'true'
        )
        """
        
        self.execute_query(query)
        self.logger.info(f"Created bronze table: {config.BRONZE_TABLE}")
    
    def create_silver_table(self):
        """Create silver table if it doesn't exist."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.catalog}.{self.schema}.{config.SILVER_TABLE} (
            city STRING,
            temperature_celsius DOUBLE,
            humidity INT,
            pressure INT,
            wind_speed DOUBLE,
            weather_main STRING,
            weather_description STRING,
            observation_time TIMESTAMP,
            ingestion_id STRING,
            processed_time TIMESTAMP,
            is_valid BOOLEAN,
            quality_checks_passed INT,
            quality_checks_total INT
        )
        USING DELTA
        PARTITIONED BY (city)
        TBLPROPERTIES (
            'delta.autoOptimize.optimizeWrite' = 'true',
            'delta.autoOptimize.autoCompact' = 'true'
        )
        """
        
        self.execute_query(query)
        self.logger.info(f"Created silver table: {config.SILVER_TABLE}")
    
    def create_gold_table(self):
        """Create gold table if it doesn't exist."""
        query = f"""
        CREATE TABLE IF NOT EXISTS {self.catalog}.{self.schema}.{config.GOLD_TABLE} (
            city STRING,
            observation_date DATE,
            avg_temperature DOUBLE,
            max_temperature DOUBLE,
            min_temperature DOUBLE,
            avg_humidity DOUBLE,
            avg_wind_speed DOUBLE,
            record_count INT,
            last_updated TIMESTAMP
        )
        USING DELTA
        PARTITIONED BY (city, observation_date)
        TBLPROPERTIES (
            'delta.autoOptimize.optimizeWrite' = 'true',
            'delta.autoOptimize.autoCompact' = 'true'
        )
        """
        
        self.execute_query(query)
        self.logger.info(f"Created gold table: {config.GOLD_TABLE}")
    
    def insert_bronze_records(self, records: List[RawWeatherRecord]):
        """
        Insert records into bronze table using MERGE for deduplication.
        
        Args:
            records: List of RawWeatherRecord objects
        """
        if not records:
            self.logger.warning("No records to insert into bronze table")
            return
        
        inserted_count = 0
        
        for record in records:
            try:
                # Serialize JSON with datetime handling and escape single quotes
                raw_payload = json.dumps(
                    record.raw_payload,
                    default=lambda x: x.isoformat() if hasattr(x, "isoformat") else str(x)
                ).replace("'", "''")
                
                # Escape single quotes in string fields
                city = record.city.replace("'", "''")
                source = record.source.replace("'", "''")
                source_city = record.source_city.replace("'", "''")
                
                insert_sql = f"""
                MERGE INTO {self.catalog}.{self.schema}.{config.BRONZE_TABLE} AS target
                USING (
                    SELECT
                        '{record.ingestion_id}' AS ingestion_id,
                        CAST('{record.ingestion_time.isoformat()}' AS TIMESTAMP) AS ingestion_time,
                        '{city}' AS city,
                        '{source}' AS source,
                        '{source_city}' AS source_city,
                        '{raw_payload}' AS raw_payload,
                        {record.api_response_time} AS api_response_time
                ) AS source
                ON target.ingestion_id = source.ingestion_id
                WHEN NOT MATCHED THEN
                    INSERT (
                        ingestion_id, ingestion_time, city, source, 
                        source_city, raw_payload, api_response_time
                    ) VALUES (
                        source.ingestion_id, source.ingestion_time, source.city, source.source,
                        source.source_city, source.raw_payload, source.api_response_time
                    )
                """
                
                self.execute_query(insert_sql)
                inserted_count += 1
                
            except Exception as e:
                self.logger.error(f"Failed to insert record {record.ingestion_id}: {str(e)}")
                continue
        
        self.logger.info(f"Inserted {inserted_count}/{len(records)} records into bronze table")
    
    def insert_silver_records(self, records: List[SilverWeatherRecord]):
        """
        Insert records into silver table.
        
        Args:
            records: List of SilverWeatherRecord objects
        """
        if not records:
            self.logger.warning("No records to insert into silver table")
            return
        
        # Build batch insert values
        values = []
        for record in records:
            try:
                # Escape single quotes in string fields
                city = record.city.replace("'", "''")
                weather_main = record.weather_main.replace("'", "''")
                weather_description = record.weather_description.replace("'", "''")
                
                values.append(
                    f"""(
                        '{city}',
                        {record.temperature_celsius},
                        {record.humidity},
                        {record.pressure},
                        {record.wind_speed},
                        '{weather_main}',
                        '{weather_description}',
                        CAST('{record.observation_time.isoformat()}' AS TIMESTAMP),
                        '{record.ingestion_id}',
                        CAST('{record.processed_time.isoformat()}' AS TIMESTAMP),
                        {str(record.is_valid).upper()},
                        {record.quality_checks_passed},
                        {record.quality_checks_total}
                    )"""
                )
            except Exception as e:
                self.logger.error(f"Failed to process record {record.ingestion_id}: {str(e)}")
                continue
        
        if not values:
            self.logger.warning("No valid records to insert into silver table")
            return
        
        insert_sql = f"""
        INSERT INTO {self.catalog}.{self.schema}.{config.SILVER_TABLE}
        (city, temperature_celsius, humidity, pressure, wind_speed,
         weather_main, weather_description, observation_time,
         ingestion_id, processed_time, is_valid,
         quality_checks_passed, quality_checks_total)
        VALUES {', '.join(values)}
        """
        
        try:
            self.execute_query(insert_sql)
            self.logger.info(f"Inserted {len(values)} records into silver table")
        except Exception as e:
            self.logger.error(f"Failed to insert silver records: {str(e)}")
            raise
    
    def optimize_tables(self, table_name: str):
        """
        Optimize Delta table with Z-order and compaction.
        
        Args:
            table_name: Name of the table to optimize
        """
        full_table_name = f"{self.catalog}.{self.schema}.{table_name}"
        
        # Choose ZORDER columns based on table schema
        if table_name == config.BRONZE_TABLE:
            optimize_sql = f"""
            OPTIMIZE {full_table_name}
            ZORDER BY ( ingestion_time)
            """
        elif table_name == config.SILVER_TABLE:
            optimize_sql = f"""
            OPTIMIZE {full_table_name}
            ZORDER BY ( observation_time)
            """
        elif table_name == config.GOLD_TABLE:
            optimize_sql = f"""
            OPTIMIZE {full_table_name}
            ZORDER BY (avg_temperature)
            """
        else:
            optimize_sql = f"""
            OPTIMIZE {full_table_name}
            """
        
        try:
            self.execute_query(optimize_sql)
            self.logger.info(f"Optimized table: {table_name}")
        except Exception as e:
            self.logger.error(f"Failed to optimize table {table_name}: {str(e)}")
            raise
        
        # Run VACUUM to clean up old files (keep last 7 days)
        try:
            vacuum_sql = f"VACUUM {full_table_name} RETAIN 168 HOURS"
            self.execute_query(vacuum_sql)
            self.logger.info(f"Vacuumed table: {table_name}")
        except Exception as e:
            self.logger.warning(f"Failed to vacuum table {table_name}: {str(e)}")
    
    def get_table_history(self, table_name: str, limit: int = 10) -> List[Dict]:
        """
        Get table history for time travel queries.
        
        Args:
            table_name: Name of the table
            limit: Number of historical versions to return
            
        Returns:
            List of historical versions
        """
        full_table_name = f"{self.catalog}.{self.schema}.{table_name}"
        query = f"DESCRIBE HISTORY {full_table_name} LIMIT {limit}"
        
        try:
            return self.execute_query(query)
        except Exception as e:
            self.logger.error(f"Failed to get table history for {table_name}: {str(e)}")
            return []
    
    def time_travel_query(self, table_name: str, timestamp: str) -> List[Dict]:
        """
        Query table at a specific point in time.
        
        Args:
            table_name: Name of the table
            timestamp: Timestamp in format 'YYYY-MM-DD HH:MM:SS'
            
        Returns:
            Query results
        """
        full_table_name = f"{self.catalog}.{self.schema}.{table_name}"
        query = f"""
        SELECT * FROM {full_table_name}
        TIMESTAMP AS OF '{timestamp}'
        """
        
        try:
            return self.execute_query(query)
        except Exception as e:
            self.logger.error(f"Failed to query table at timestamp {timestamp}: {str(e)}")
            return []
    
    def close_connection(self):
        """Close the database connection."""
        if self._connection:
            try:
                self._connection.close()
                self._connection = None
                self.logger.info("Closed Databricks connection")
            except Exception as e:
                self.logger.error(f"Error closing connection: {str(e)}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_connection()