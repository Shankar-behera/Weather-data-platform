"""
Main entry point for weather data ingestion pipeline.
"""

import sys
import logging
from datetime import datetime
from typing import Optional

from .config import config
from .service import WeatherService
from .databricks_client import DatabricksClient
from .models import RawWeatherRecord, SilverWeatherRecord


def setup_logging():
    """Configure root logger."""
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def run_ingestion_pipeline():
    """
    Execute the complete ingestion pipeline.
    
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting weather data ingestion pipeline")
    
    try:
        # Initialize services
        weather_service = WeatherService()
        databricks_client = DatabricksClient()
        
        # Step 1: Create tables if they don't exist
        logger.info("Creating Delta tables if they don't exist")
        databricks_client.create_bronze_table()
        databricks_client.create_silver_table()
        databricks_client.create_gold_table()
        
        # Step 2: Fetch weather data
        logger.info("Fetching weather data for all cities")
        weather_data = weather_service.fetch_all_cities()
        
        if not weather_data:
            logger.error("No weather data fetched")
            return False
        
        logger.info(f"Fetched weather data for {len(weather_data)} cities")
        
        # Step 3: Create bronze records
        logger.info("Creating bronze layer records")
        bronze_records = weather_service.create_bronze_records(weather_data)
        databricks_client.insert_bronze_records(bronze_records)
        
        # Step 4: Create silver records
        logger.info("Creating silver layer records")
        silver_records = weather_service.create_silver_records(weather_data)
        databricks_client.insert_silver_records(silver_records)
        
        # Step 5: Optimize tables
        logger.info("Optimizing Delta tables")
        databricks_client.optimize_tables(config.BRONZE_TABLE)
        databricks_client.optimize_tables(config.SILVER_TABLE)
        
        # Step 6: Log metrics
        logger.info(
            "Pipeline completed successfully",
            extra={
                "cities_processed": len(weather_data),
                "bronze_records": len(bronze_records),
                "silver_records": len(silver_records),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        return False


if __name__ == "__main__":
    setup_logging()
    success = run_ingestion_pipeline()
    sys.exit(0 if success else 1)