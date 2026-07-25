"""
Alerting system for weather data platform.
Handles Slack, Email, and custom alert notifications.
"""

import os
import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

import requests
from jinja2 import Template


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Alert delivery channels."""
    SLACK = "slack"
    EMAIL = "email"
    PAGERDUTY = "pagerduty"
    WEBHOOK = "webhook"


@dataclass
class Alert:
    """Alert data structure."""
    title: str
    message: str
    severity: AlertSeverity
    channel: AlertChannel
    timestamp: datetime
    metadata: Dict[str, Any]
    source: str = "weather-platform"


class AlertManager:
    """Manage alert delivery across multiple channels."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        
        # Load configuration from environment
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.email_sender = os.getenv("EMAIL_SENDER")
        self.email_password = os.getenv("EMAIL_PASSWORD")
        self.email_recipients = os.getenv("EMAIL_RECIPIENTS", "").split(",")
        self.pagerduty_key = os.getenv("PAGERDUTY_KEY")
        
        # Alert templates
        self.slack_template = Template("""
*{{ alert.title }}*
*Severity:* {{ alert.severity.value.upper() }}
*Time:* {{ alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') }}
*Source:* {{ alert.source }}

{{ alert.message }}

{% if alert.metadata %}
*Metadata:*
{% for key, value in alert.metadata.items() %}
• {{ key }}: {{ value }}
{% endfor %}
{% endif %}
""")
        
        self.email_template = Template("""
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .alert-box { 
            border: 1px solid #ddd;
            padding: 20px;
            margin: 20px 0;
            border-radius: 5px;
        }
        .severity-critical { border-left: 4px solid #dc3545; }
        .severity-error { border-left: 4px solid #fd7e14; }
        .severity-warning { border-left: 4px solid #ffc107; }
        .severity-info { border-left: 4px solid #17a2b8; }
        .metadata { 
            background-color: #f8f9fa;
            padding: 10px;
            border-radius: 3px;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <h2>{{ alert.title }}</h2>
    <div class="alert-box severity-{{ alert.severity.value }}">
        <p><strong>Severity:</strong> {{ alert.severity.value.upper() }}</p>
        <p><strong>Time:</strong> {{ alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC') }}</p>
        <p><strong>Source:</strong> {{ alert.source }}</p>
        <p>{{ alert.message }}</p>
        {% if alert.metadata %}
        <h4>Metadata:</h4>
        <div class="metadata">
            {% for key, value in alert.metadata.items() %}
            <p><strong>{{ key }}:</strong> {{ value }}</p>
            {% endfor %}
        </div>
        {% endif %}
    </div>
</body>
</html>
""")
    
    def setup_logging(self):
        """Configure logging."""
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            '{"time": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
        ))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def send_alert(self, alert: Alert) -> bool:
        """
        Send alert through appropriate channel.
        
        Args:
            alert: Alert object
            
        Returns:
            bool: True if sent successfully
        """
        try:
            if alert.channel == AlertChannel.SLACK:
                return self._send_slack(alert)
            elif alert.channel == AlertChannel.EMAIL:
                return self._send_email(alert)
            elif alert.channel == AlertChannel.PAGERDUTY:
                return self._send_pagerduty(alert)
            elif alert.channel == AlertChannel.WEBHOOK:
                return self._send_webhook(alert)
            else:
                self.logger.error(f"Unknown alert channel: {alert.channel}")
                return False
        
        except Exception as e:
            self.logger.error(f"Failed to send alert: {str(e)}")
            return False
    
    def _send_slack(self, alert: Alert) -> bool:
        """Send alert to Slack."""
        if not self.slack_webhook:
            self.logger.warning("Slack webhook not configured")
            return False
        
        try:
            message = self.slack_template.render(alert=alert)
            
            payload = {
                "text": message,
                "username": "Weather Platform Alerts",
                "icon_emoji": self._get_severity_emoji(alert.severity),
                "attachments": [
                    {
                        "color": self._get_severity_color(alert.severity),
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity.value.upper(),
                                "short": True
                            },
                            {
                                "title": "Time",
                                "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                                "short": True
                            }
                        ]
                    }
                ]
            }
            
            response = requests.post(self.slack_webhook, json=payload, timeout=5)
            response.raise_for_status()
            
            self.logger.info(f"Slack alert sent: {alert.title}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send Slack alert: {str(e)}")
            return False
    
    def _send_email(self, alert: Alert) -> bool:
        """Send alert via email."""
        if not self.email_sender or not self.email_password or not self.email_recipients:
            self.logger.warning("Email configuration incomplete")
            return False
        
        try:
            # Create email message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.title}"
            msg['From'] = self.email_sender
            msg['To'] = ', '.join(self.email_recipients)
            
            # HTML version
            html_content = self.email_template.render(alert=alert)
            msg.attach(MIMEText(html_content, 'html'))
            
            # Plain text version
            plain_text = f"""
            {alert.title}
            Severity: {alert.severity.value.upper()}
            Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
            Source: {alert.source}
            
            {alert.message}
            
            Metadata:
            {json.dumps(alert.metadata, indent=2)}
            """
            msg.attach(MIMEText(plain_text, 'plain'))
            
            # Send email
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.email_sender, self.email_password)
                server.send_message(msg)
            
            self.logger.info(f"Email alert sent: {alert.title}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email alert: {str(e)}")
            return False
    
    def _send_pagerduty(self, alert: Alert) -> bool:
        """Send alert to PagerDuty."""
        if not self.pagerduty_key:
            self.logger.warning("PagerDuty key not configured")
            return False
        
        try:
            payload = {
                "routing_key": self.pagerduty_key,
                "event_action": "trigger",
                "payload": {
                    "summary": alert.title,
                    "severity": alert.severity.value,
                    "source": alert.source,
                    "timestamp": alert.timestamp.isoformat(),
                    "component": "weather-platform",
                    "custom_details": {
                        "message": alert.message,
                        **alert.metadata
                    }
                }
            }
            
            response = requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            
            self.logger.info(f"PagerDuty alert sent: {alert.title}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send PagerDuty alert: {str(e)}")
            return False
    
    def _send_webhook(self, alert: Alert) -> bool:
        """Send alert to custom webhook."""
        webhook_url = os.getenv("CUSTOM_WEBHOOK_URL")
        if not webhook_url:
            self.logger.warning("Custom webhook not configured")
            return False
        
        try:
            payload = {
                "title": alert.title,
                "message": alert.message,
                "severity": alert.severity.value,
                "timestamp": alert.timestamp.isoformat(),
                "source": alert.source,
                "metadata": alert.metadata
            }
            
            response = requests.post(webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            
            self.logger.info(f"Webhook alert sent: {alert.title}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send webhook alert: {str(e)}")
            return False
    
    def _get_severity_emoji(self, severity: AlertSeverity) -> str:
        """Get emoji for severity level."""
        emojis = {
            AlertSeverity.INFO: ":information_source:",
            AlertSeverity.WARNING: ":warning:",
            AlertSeverity.ERROR: ":x:",
            AlertSeverity.CRITICAL: ":rotating_light:"
        }
        return emojis.get(severity, ":grey_question:")
    
    def _get_severity_color(self, severity: AlertSeverity) -> str:
        """Get color for severity level."""
        colors = {
            AlertSeverity.INFO: "#17a2b8",
            AlertSeverity.WARNING: "#ffc107",
            AlertSeverity.ERROR: "#fd7e14",
            AlertSeverity.CRITICAL: "#dc3545"
        }
        return colors.get(severity, "#6c757d")
    
    def create_data_quality_alert(self, metrics: Dict) -> Alert:
        """
        Create alert from data quality metrics.
        
        Args:
            metrics: Data quality metrics
            
        Returns:
            Alert object
        """
        severity = AlertSeverity.INFO
        
        if metrics.get("critical_alerts", 0) > 0:
            severity = AlertSeverity.CRITICAL
        elif metrics.get("warning_alerts", 0) > 0:
            severity = AlertSeverity.WARNING
        
        title = f"Data Quality Report - {metrics.get('total_checks', 0)} checks"
        message = f"""
        Data quality check completed.
        
        Summary:
        • Total checks: {metrics.get('total_checks', 0)}
        • Critical alerts: {metrics.get('critical_alerts', 0)}
        • Warning alerts: {metrics.get('warning_alerts', 0)}
        • Info alerts: {metrics.get('info_alerts', 0)}
        """
        
        return Alert(
            title=title,
            message=message.strip(),
            severity=severity,
            channel=AlertChannel.SLACK,
            timestamp=datetime.utcnow(),
            metadata=metrics.get("metrics", []),
            source="weather-platform-quality"
        )
    
    def create_pipeline_alert(self, pipeline_name: str, status: str, 
                              duration: float, error: Optional[str] = None) -> Alert:
        """
        Create alert for pipeline status.
        
        Args:
            pipeline_name: Name of the pipeline
            status: Pipeline status (success/failure)
            duration: Pipeline duration in seconds
            error: Error message if failed
            
        Returns:
            Alert object
        """
        if status == "failure":
            severity = AlertSeverity.CRITICAL
            title = f"🚨 Pipeline Failed: {pipeline_name}"
            message = f"Pipeline {pipeline_name} failed after {duration:.2f} seconds."
        else:
            severity = AlertSeverity.INFO
            title = f"✅ Pipeline Succeeded: {pipeline_name}"
            message = f"Pipeline {pipeline_name} completed successfully in {duration:.2f} seconds."
        
        metadata = {
            "pipeline": pipeline_name,
            "status": status,
            "duration_seconds": duration,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if error:
            metadata["error"] = error
            if status == "success":
                # If error is provided but status is success, it might be a warning
                severity = AlertSeverity.WARNING
        
        return Alert(
            title=title,
            message=message,
            severity=severity,
            channel=AlertChannel.SLACK,
            timestamp=datetime.utcnow(),
            metadata=metadata,
            source="weather-platform-pipeline"
        )
    
    def create_weather_alert(self, city: str, event_type: str, 
                             value: float, threshold: float) -> Alert:
        """
        Create alert for extreme weather events.
        
        Args:
            city: City name
            event_type: Type of event
            value: Actual value
            threshold: Threshold value
            
        Returns:
            Alert object
        """
        event_descriptions = {
            "heatwave": f"Temperature of {value:.1f}°C exceeds threshold of {threshold:.1f}°C",
            "storm": f"Wind speed of {value:.1f} km/h exceeds threshold of {threshold:.1f} km/h",
            "heavy_rain": f"Heavy rain detected in {city}",
            "cold_wave": f"Temperature of {value:.1f}°C is below {threshold:.1f}°C"
        }
        
        title = f"⚠️ Extreme Weather Alert: {city}"
        message = event_descriptions.get(event_type, f"Extreme weather event in {city}")
        
        metadata = {
            "city": city,
            "event_type": event_type,
            "value": value,
            "threshold": threshold,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return Alert(
            title=title,
            message=message,
            severity=AlertSeverity.WARNING,
            channel=AlertChannel.SLACK,
            timestamp=datetime.utcnow(),
            metadata=metadata,
            source="weather-platform-weather"
        )


# Singleton instance
_alert_manager = None


def get_alert_manager() -> AlertManager:
    """Get or create alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager  