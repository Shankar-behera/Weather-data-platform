
"""
Metrics collection and monitoring for weather data platform.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from collections import defaultdict

import pandas as pd

from ingestion.databricks_client import DatabricksClient
from ingestion.config import config


@dataclass
class Metric:
    """Individual metric data point."""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = ""


class MetricsCollector:
    """Collect and track metrics from the platform."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.databricks = DatabricksClient()
        self.logger = logging.getLogger(__name__)
        self.metrics: List[Metric] = []
        self.setup_logging()
    
    def setup_logging(self):
        """Configure logging."""
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def collect_pipeline_metrics(self) -> List[Metric]:
        """Collect pipeline execution metrics."""
        metrics = []
        
        try:
            # Check ingestion pipeline status
            ingestion_query = f"""
            SELECT 
                COUNT(*) as total_ingestions,
                MAX(ingestion_time) as last_ingestion,
                MIN(ingestion_time) as first_ingestion
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.BRONZE_TABLE}
            WHERE ingestion_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            """
            
            results = self.databricks.execute_query(ingestion_query)
            if results:
                row = results[0]
                metrics.append(Metric(
                    name="ingestion.total_records_24h",
                    value=row['total_ingestions'],
                    timestamp=datetime.utcnow(),
                    unit="records"
                ))
                
                if row['last_ingestion']:
                    hours_since_last = (datetime.utcnow() - row['last_ingestion']).total_seconds() / 3600
                    metrics.append(Metric(
                        name="ingestion.hours_since_last",
                        value=hours_since_last,
                        timestamp=datetime.utcnow(),
                        unit="hours"
                    ))
        
        except Exception as e:
            self.logger.error(f"Failed to collect ingestion metrics: {str(e)}")
        
        try:
            # Check silver pipeline status
            silver_query = f"""
            SELECT 
                COUNT(*) as total_silver_records,
                MAX(processed_time) as last_processed,
                AVG(quality_checks_passed) as avg_quality_score
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.SILVER_TABLE}
            WHERE processed_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            """
            
            results = self.databricks.execute_query(silver_query)
            if results:
                row = results[0]
                metrics.append(Metric(
                    name="silver.total_records_24h",
                    value=row['total_silver_records'],
                    timestamp=datetime.utcnow(),
                    unit="records"
                ))
                
                metrics.append(Metric(
                    name="silver.avg_quality_score",
                    value=row['avg_quality_score'],
                    timestamp=datetime.utcnow(),
                    unit="score"
                ))
        
        except Exception as e:
            self.logger.error(f"Failed to collect silver metrics: {str(e)}")
        
        return metrics
    
    def collect_table_metrics(self) -> List[Metric]:
        """Collect table size and performance metrics."""
        metrics = []
        
        for table_name in [config.BRONZE_TABLE, config.SILVER_TABLE, config.GOLD_TABLE]:
            try:
                query = f"""
                DESCRIBE DETAIL {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{table_name}
                """
                
                results = self.databricks.execute_query(query)
                if results:
                    row = results[0]
                    metrics.append(Metric(
                        name=f"delta.{table_name}.size_bytes",
                        value=row['sizeInBytes'],
                        timestamp=datetime.utcnow(),
                        unit="bytes"
                    ))
                    
                    metrics.append(Metric(
                        name=f"delta.{table_name}.num_files",
                        value=row['numFiles'],
                        timestamp=datetime.utcnow(),
                        unit="files"
                    ))
                    
                    if 'numRecords' in row:
                        metrics.append(Metric(
                            name=f"delta.{table_name}.num_records",
                            value=row['numRecords'],
                            timestamp=datetime.utcnow(),
                            unit="records"
                        ))
            
            except Exception as e:
                self.logger.error(f"Failed to collect metrics for {table_name}: {str(e)}")
        
        return metrics
    
    def collect_weather_metrics(self) -> List[Metric]:
        """Collect weather-related metrics."""
        metrics = []
        
        try:
            # Temperature extremes
            temp_query = f"""
            SELECT 
                city,
                AVG(temperature_celsius) as avg_temp,
                MAX(temperature_celsius) as max_temp,
                MIN(temperature_celsius) as min_temp
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.SILVER_TABLE}
            WHERE observation_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            GROUP BY city
            """
            
            results = self.databricks.execute_query(temp_query)
            if results:
                all_avgs = [row['avg_temp'] for row in results if row['avg_temp'] is not None]
                all_maxs = [row['max_temp'] for row in results if row['max_temp'] is not None]
                all_mins = [row['min_temp'] for row in results if row['min_temp'] is not None]
                
                if all_avgs:
                    metrics.append(Metric(
                        name="weather.global_avg_temp",
                        value=sum(all_avgs) / len(all_avgs),
                        timestamp=datetime.utcnow(),
                        tags={"period": "24h"},
                        unit="celsius"
                    ))
                
                if all_maxs:
                    metrics.append(Metric(
                        name="weather.global_max_temp",
                        value=max(all_maxs),
                        timestamp=datetime.utcnow(),
                        tags={"period": "24h"},
                        unit="celsius"
                    ))
                
                if all_mins:
                    metrics.append(Metric(
                        name="weather.global_min_temp",
                        value=min(all_mins),
                        timestamp=datetime.utcnow(),
                        tags={"period": "24h"},
                        unit="celsius"
                    ))
        
        except Exception as e:
            self.logger.error(f"Failed to collect weather metrics: {str(e)}")
        
        return metrics
    
    def collect_quality_metrics(self) -> List[Metric]:
        """Collect data quality metrics."""
        metrics = []
        
        try:
            quality_query = f"""
            SELECT 
                COUNT(*) as total_records,
                SUM(CASE WHEN is_valid THEN 1 ELSE 0 END) as valid_records,
                AVG(quality_checks_passed) as avg_quality_score
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.SILVER_TABLE}
            WHERE observation_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            """
            
            results = self.databricks.execute_query(quality_query)
            if results:
                row = results[0]
                
                metrics.append(Metric(
                    name="quality.total_records",
                    value=row['total_records'],
                    timestamp=datetime.utcnow(),
                    unit="records"
                ))
                
                metrics.append(Metric(
                    name="quality.valid_records",
                    value=row['valid_records'],
                    timestamp=datetime.utcnow(),
                    unit="records"
                ))
                
                if row['total_records'] > 0:
                    valid_ratio = row['valid_records'] / row['total_records'] * 100
                    metrics.append(Metric(
                        name="quality.valid_ratio",
                        value=valid_ratio,
                        timestamp=datetime.utcnow(),
                        unit="percent"
                    ))
                
                metrics.append(Metric(
                    name="quality.avg_score",
                    value=row['avg_quality_score'] or 0,
                    timestamp=datetime.utcnow(),
                    unit="score"
                ))
        
        except Exception as e:
            self.logger.error(f"Failed to collect quality metrics: {str(e)}")
        
        return metrics
    
    def collect_performance_metrics(self) -> List[Metric]:
        """Collect system performance metrics."""
        metrics = []
        
        # Note: In production, collect from cloud providers, Databricks APIs, etc.
        # This is a placeholder with simulated metrics
        
        try:
            # Query performance
            performance_query = """
            SELECT 
                COUNT(*) as query_count,
                AVG(duration) as avg_duration
            FROM (VALUES (1, 0.5), (2, 1.2), (3, 0.8)) AS t(query_id, duration)
            """
            
            # In production, this would be from Databricks query history
            
        except Exception as e:
            self.logger.error(f"Failed to collect performance metrics: {str(e)}")
        
        return metrics
    
    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect all metrics and return summary."""
        all_metrics = []
        
        # Collect from all sources
        all_metrics.extend(self.collect_pipeline_metrics())
        all_metrics.extend(self.collect_table_metrics())
        all_metrics.extend(self.collect_weather_metrics())
        all_metrics.extend(self.collect_quality_metrics())
        all_metrics.extend(self.collect_performance_metrics())
        
        # Store metrics
        self.metrics.extend(all_metrics)
        
        # Generate summary
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_metrics": len(all_metrics),
            "metrics": [asdict(m) for m in all_metrics]
        }
        
        # Log summary
        self.logger.info(
            "Metrics collection completed",
            extra={"total_metrics": len(all_metrics)}
        )
        
        return summary
    
    def get_metric_trend(self, metric_name: str, hours: int = 24) -> List[Metric]:
        """
        Get historical trend for a specific metric.
        
        Args:
            metric_name: Name of the metric
            hours: Number of hours to look back
            
        Returns:
            List of Metric objects
        """
        return [
            m for m in self.metrics
            if m.name == metric_name
            and m.timestamp >= datetime.utcnow() - timedelta(hours=hours)
        ]
    
    def get_metric_summary(self) -> Dict:
        """
        Get summary of all metrics.
        
        Returns:
            Dictionary with metric summaries
        """
        summary = {}
        
        # Group metrics by name
        metrics_by_name = defaultdict(list)
        for metric in self.metrics:
            metrics_by_name[metric.name].append(metric)
        
        for name, metrics in metrics_by_name.items():
            values = [m.value for m in metrics]
            summary[name] = {
                "current": values[-1] if values else None,
                "min": min(values) if values else None,
                "max": max(values) if values else None,
                "avg": sum(values) / len(values) if values else None,
                "count": len(values),
                "unit": metrics[0].unit if metrics else ""
            }
        
        return summary
    
    def export_metrics(self, format: str = "json") -> str:
        """
        Export metrics in specified format.
        
        Args:
            format: Export format (json, csv)
            
        Returns:
            String representation of metrics
        """
        if format == "json":
            return json.dumps([asdict(m) for m in self.metrics], default=str, indent=2)
        elif format == "csv":
            data = []
            for m in self.metrics:
                row = {
                    "name": m.name,
                    "value": m.value,
                    "timestamp": m.timestamp.isoformat(),
                    "unit": m.unit,
                    **m.tags
                }
                data.append(row)
            
            df = pd.DataFrame(data)
            return df.to_csv(index=False)
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Singleton instance
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def main():
    """Main entry point for metrics collection."""
    collector = get_metrics_collector()
    summary = collector.collect_all_metrics()
    
    # Save summary to file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"monitoring/logs/metrics_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(summary, f, indent=2, default=str)


if __name__ == "__main__":
    main()