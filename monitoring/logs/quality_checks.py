"""
Data quality monitoring and alerting system.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum

import requests
from ingestion.databricks_client import DatabricksClient
from ingestion.config import config


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class QualityMetric:
    """Data quality metric."""
    name: str
    value: Any
    expected: Any
    severity: AlertSeverity
    description: str
    timestamp: datetime


class QualityMonitor:
    """Monitor data quality and generate alerts."""
    
    def __init__(self):
        """Initialize quality monitor."""
        self.databricks = DatabricksClient()
        self.logger = logging.getLogger(__name__)
        self.metrics: List[QualityMetric] = []
        self.setup_logging()
    
    def setup_logging(self):
        """Configure structured logging."""
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def check_data_freshness(self) -> List[QualityMetric]:
        """Check if data is fresh for all cities."""
        metrics = []
        
        try:
            query = f"""
            SELECT 
                city,
                MAX(observation_time) as latest_time,
                DATEDIFF('hours', MAX(observation_time), CURRENT_TIMESTAMP()) as hours_old
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.SILVER_TABLE}
            GROUP BY city
            """
            
            results = self.databricks.execute_query(query)
            
            for row in results:
                severity = AlertSeverity.INFO
                if row['hours_old'] > 24:
                    severity = AlertSeverity.CRITICAL
                elif row['hours_old'] > 4:
                    severity = AlertSeverity.WARNING
                
                metric = QualityMetric(
                    name=f"freshness_{row['city']}",
                    value=row['hours_old'],
                    expected=4,  # 4 hours
                    severity=severity,
                    description=f"Data freshness for {row['city']}",
                    timestamp=datetime.utcnow()
                )
                metrics.append(metric)
        
        except Exception as e:
            self.logger.error(f"Failed to check data freshness: {str(e)}")
        
        return metrics
    
    def check_quality_scores(self) -> List[QualityMetric]:
        """Check data quality scores."""
        metrics = []
        
        try:
            query = f"""
            SELECT 
                city,
                AVG(quality_checks_passed) as avg_quality_score,
                COUNT(*) as total_records
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.SILVER_TABLE}
            WHERE observation_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            GROUP BY city
            """
            
            results = self.databricks.execute_query(query)
            
            for row in results:
                severity = AlertSeverity.INFO
                if row['avg_quality_score'] < 4:
                    severity = AlertSeverity.CRITICAL
                elif row['avg_quality_score'] < 4.5:
                    severity = AlertSeverity.WARNING
                
                metric = QualityMetric(
                    name=f"quality_{row['city']}",
                    value=row['avg_quality_score'],
                    expected=5.0,
                    severity=severity,
                    description=f"Average quality score for {row['city']}",
                    timestamp=datetime.utcnow()
                )
                metrics.append(metric)
        
        except Exception as e:
            self.logger.error(f"Failed to check quality scores: {str(e)}")
        
        return metrics
    
    def check_data_volume(self) -> List[QualityMetric]:
        """Check if data volume is sufficient."""
        metrics = []
        
        try:
            query = f"""
            SELECT 
                city,
                COUNT(*) as records,
                DATEDIFF('hours', MIN(observation_time), MAX(observation_time)) as hours_span
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.SILVER_TABLE}
            WHERE observation_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            GROUP BY city
            """
            
            results = self.databricks.execute_query(query)
            
            for row in results:
                expected_records = row['hours_span']  # Should be 1 record per hour
                missing_ratio = 1 - (row['records'] / expected_records) if expected_records > 0 else 0
                
                severity = AlertSeverity.INFO
                if missing_ratio > 0.5:
                    severity = AlertSeverity.CRITICAL
                elif missing_ratio > 0.2:
                    severity = AlertSeverity.WARNING
                
                metric = QualityMetric(
                    name=f"volume_{row['city']}",
                    value=row['records'],
                    expected=expected_records,
                    severity=severity,
                    description=f"Data volume for {row['city']} (missing {missing_ratio*100:.1f}%)",
                    timestamp=datetime.utcnow()
                )
                metrics.append(metric)
        
        except Exception as e:
            self.logger.error(f"Failed to check data volume: {str(e)}")
        
        return metrics
    
    def check_extreme_events(self) -> List[QualityMetric]:
        """Check for extreme weather events."""
        metrics = []
        
        try:
            query = f"""
            SELECT 
                city,
                COUNT(*) as event_count,
                MAX(temperature_celsius) as max_temp,
                MAX(wind_speed) as max_wind
            FROM {config.DATABRICKS_CATALOG}.{config.DATABRICKS_SCHEMA}.{config.SILVER_TABLE}
            WHERE observation_time >= CURRENT_TIMESTAMP() - INTERVAL 24 HOURS
            AND (
                temperature_celsius > 35 
                OR temperature_celsius < -10
                OR wind_speed > 50
            )
            GROUP BY city
            """
            
            results = self.databricks.execute_query(query)
            
            for row in results:
                if row['event_count'] > 0:
                    metric = QualityMetric(
                        name=f"extreme_{row['city']}",
                        value=row['event_count'],
                        expected=0,
                        severity=AlertSeverity.WARNING,
                        description=f"Extreme events in {row['city']}: max temp {row['max_temp']:.1f}°C, max wind {row['max_wind']:.1f} km/h",
                        timestamp=datetime.utcnow()
                    )
                    metrics.append(metric)
        
        except Exception as e:
            self.logger.error(f"Failed to check extreme events: {str(e)}")
        
        return metrics
    
    def run_all_checks(self) -> Dict:
        """Run all quality checks and return summary."""
        all_metrics = []
        
        # Run all checks
        all_metrics.extend(self.check_data_freshness())
        all_metrics.extend(self.check_quality_scores())
        all_metrics.extend(self.check_data_volume())
        all_metrics.extend(self.check_extreme_events())
        
        # Store metrics
        self.metrics = all_metrics
        
        # Generate summary
        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_checks": len(all_metrics),
            "critical_alerts": len([m for m in all_metrics if m.severity == AlertSeverity.CRITICAL]),
            "warning_alerts": len([m for m in all_metrics if m.severity == AlertSeverity.WARNING]),
            "info_alerts": len([m for m in all_metrics if m.severity == AlertSeverity.INFO]),
            "metrics": [asdict(m) for m in all_metrics]
        }
        
        # Log summary
        self.logger.info(
            "Quality check completed",
            extra=summary
        )
        
        # Send alerts if critical issues found
        if summary["critical_alerts"] > 0:
            self.send_alerts(all_metrics)
        
        return summary
    
    def send_alerts(self, metrics: List[QualityMetric]):
        """Send alerts for critical issues."""
        critical_metrics = [m for m in metrics if m.severity == AlertSeverity.CRITICAL]
        
        if not critical_metrics:
            return
        
        # Format alert message
        alert_message = "🚨 Data Quality Critical Alert\n\n"
        alert_message += f"Time: {datetime.utcnow().isoformat()}\n"
        alert_message += f"Critical Issues: {len(critical_metrics)}\n\n"
        
        for metric in critical_metrics:
            alert_message += f"• {metric.name}: {metric.description}\n"
            alert_message += f"  Value: {metric.value}, Expected: {metric.expected}\n\n"
        
        self.logger.critical(alert_message)
        
        # In production, send to Slack, email, PagerDuty, etc.
        self._send_slack_alert(alert_message)
        self._send_email_alert(alert_message)
    
    def _send_slack_alert(self, message: str):
        """Send alert to Slack webhook."""
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return
        
        try:
            payload = {
                "text": message,
                "username": "Weather Data Quality Monitor",
                "icon_emoji": ":warning:"
            }
            
            response = requests.post(webhook_url, json=payload)
            response.raise_for_status()
            self.logger.info("Slack alert sent successfully")
        
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {str(e)}")
    
    def _send_email_alert(self, message: str):
        """Send email alert (placeholder implementation)."""
        # In production, use proper email service (SMTP, SendGrid, etc.)
        self.logger.info(f"Email alert would be sent: {message[:100]}...")


def main():
    """Main entry point for quality monitoring."""
    monitor = QualityMonitor()
    summary = monitor.run_all_checks()
    
    # Save summary to file for history
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"monitoring/logs/quality_{timestamp}.json"
    
    with open(filename, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    # Return exit code based on critical alerts
    if summary["critical_alerts"] > 0:
        exit(1)
    else:
        exit(0)


if __name__ == "__main__":
    main()