# research_system/monitoring/alerting.py
"""
Comprehensive alerting system
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import httpx
import json
import structlog

logger = structlog.get_logger()


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


@dataclass
class AlertRule:
    """Alert rule definition"""
    name: str
    description: str
    severity: AlertSeverity
    condition: Callable
    threshold: float
    window_seconds: int = 300
    cooldown_seconds: int = 600
    enabled: bool = True
    notification_channels: List[str] = field(default_factory=list)


@dataclass
class Alert:
    """Alert instance"""
    id: str
    rule_name: str
    severity: AlertSeverity
    message: str
    context: Dict[str, Any]
    timestamp: datetime
    status: AlertStatus = AlertStatus.ACTIVE
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class AlertManager:
    """Comprehensive alert management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.notification_channels: Dict[str, Callable] = {}
        self.metrics = AlertMetrics()
        self._bg_tasks: List[asyncio.Task] = []  # Track background tasks
        
        self._setup_default_rules()
        self._setup_notification_channels()
    
    def _setup_default_rules(self):
        """Setup default alert rules"""
        
        # High error rate
        self.add_rule(AlertRule(
            name="high_error_rate",
            description="Error rate exceeds threshold",
            severity=AlertSeverity.HIGH,
            condition=self._check_error_rate,
            threshold=0.1,  # 10% error rate
            window_seconds=300,
            cooldown_seconds=600
        ))
        
        # High response time
        self.add_rule(AlertRule(
            name="high_response_time",
            description="Response time exceeds threshold",
            severity=AlertSeverity.MEDIUM,
            condition=self._check_response_time,
            threshold=5.0,  # 5 seconds
            window_seconds=300,
            cooldown_seconds=300
        ))
        
        # Cost limit approaching
        self.add_rule(AlertRule(
            name="cost_limit_approaching",
            description="Cost limit approaching",
            severity=AlertSeverity.MEDIUM,
            condition=self._check_cost_limit,
            threshold=0.8,  # 80% of limit
            window_seconds=60,
            cooldown_seconds=300
        ))
        
        # API provider down
        self.add_rule(AlertRule(
            name="api_provider_down",
            description="API provider is down",
            severity=AlertSeverity.HIGH,
            condition=self._check_api_health,
            threshold=0.0,  # Any failure
            window_seconds=60,
            cooldown_seconds=300
        ))
        
        # Low evidence quality
        self.add_rule(AlertRule(
            name="low_evidence_quality",
            description="Evidence quality below threshold",
            severity=AlertSeverity.MEDIUM,
            condition=self._check_evidence_quality,
            threshold=0.3,  # 30% quality
            window_seconds=600,
            cooldown_seconds=300
        ))
    
    def _setup_notification_channels(self):
        """Setup notification channels"""
        
        # Slack notifications
        if "slack_webhook_url" in self.config:
            self.add_notification_channel(
                "slack",
                self._send_slack_notification
            )
        
        # Email notifications
        if "email_config" in self.config:
            self.add_notification_channel(
                "email",
                self._send_email_notification
            )
        
        # PagerDuty notifications
        if "pagerduty_api_key" in self.config:
            self.add_notification_channel(
                "pagerduty",
                self._send_pagerduty_notification
            )
        
        # Webhook notifications
        if "webhook_url" in self.config:
            self.add_notification_channel(
                "webhook",
                self._send_webhook_notification
            )
    
    def add_rule(self, rule: AlertRule):
        """Add alert rule"""
        self.rules[rule.name] = rule
        logger.info(f"Added alert rule: {rule.name}")
    
    def add_notification_channel(self, name: str, callback: Callable):
        """Add notification channel"""
        self.notification_channels[name] = callback
        logger.info(f"Added notification channel: {name}")
    
    async def evaluate_alerts(self, metrics: Dict[str, Any]):
        """Evaluate all alert rules"""
        
        for rule_name, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            try:
                # Check if rule should trigger
                should_alert = await rule.condition(metrics, rule.threshold)
                
                if should_alert:
                    await self._trigger_alert(rule, metrics)
                else:
                    await self._resolve_alert(rule_name)
                    
            except Exception as e:
                logger.error(f"Alert rule evaluation failed: {rule_name}, Error: {e}")
    
    async def _trigger_alert(self, rule: AlertRule, context: Dict[str, Any]):
        """Trigger an alert"""
        
        # Check cooldown
        if rule.name in self.active_alerts:
            alert = self.active_alerts[rule.name]
            if (datetime.utcnow() - alert.timestamp).seconds < rule.cooldown_seconds:
                return
        
        # Create alert
        alert = Alert(
            id=f"{rule.name}_{int(time.time())}",
            rule_name=rule.name,
            severity=rule.severity,
            message=rule.description,
            context=context,
            timestamp=datetime.utcnow()
        )
        
        # Store alert
        self.active_alerts[rule.name] = alert
        self.alert_history.append(alert)
        
        # Update metrics
        self.metrics.alerts_triggered += 1
        
        # Send notifications
        await self._send_notifications(alert, rule)
        
        logger.warning(
            f"Alert triggered: {rule.name}",
            severity=rule.severity.value,
            message=rule.description,
            context=context
        )
    
    async def _resolve_alert(self, rule_name: str):
        """Resolve an alert"""
        
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            
            del self.active_alerts[rule_name]
            
            logger.info(f"Alert resolved: {rule_name}")
    
    async def _send_notifications(self, alert: Alert, rule: AlertRule):
        """Send notifications for alert"""
        
        for channel_name in rule.notification_channels:
            if channel_name in self.notification_channels:
                try:
                    await self.notification_channels[channel_name](alert)
                except Exception as e:
                    logger.error(f"Notification failed: {channel_name}, Error: {e}")
    
    # Alert condition functions
    async def _check_error_rate(self, metrics: Dict[str, Any], threshold: float) -> bool:
        """Check if error rate exceeds threshold"""
        error_rate = metrics.get("error_rate", 0.0)
        return error_rate > threshold
    
    async def _check_response_time(self, metrics: Dict[str, Any], threshold: float) -> bool:
        """Check if response time exceeds threshold"""
        avg_response_time = metrics.get("avg_response_time", 0.0)
        return avg_response_time > threshold
    
    async def _check_cost_limit(self, metrics: Dict[str, Any], threshold: float) -> bool:
        """Check if cost is approaching limit"""
        current_cost = metrics.get("current_cost", 0.0)
        cost_limit = metrics.get("cost_limit", 1.0)
        return (current_cost / cost_limit) > threshold
    
    async def _check_api_health(self, metrics: Dict[str, Any], threshold: float) -> bool:
        """Check if API health is below threshold"""
        api_health = metrics.get("api_health", 1.0)
        return api_health <= threshold
    
    async def _check_evidence_quality(self, metrics: Dict[str, Any], threshold: float) -> bool:
        """Check if evidence quality is below threshold"""
        avg_quality = metrics.get("avg_evidence_quality", 1.0)
        return avg_quality < threshold
    
    # Notification methods
    async def _send_slack_notification(self, alert: Alert):
        """Send Slack notification"""
        
        webhook_url = self.config.get("slack_webhook_url")
        if not webhook_url:
            return
        
        color_map = {
            AlertSeverity.LOW: "#36a64f",
            AlertSeverity.MEDIUM: "#ffa500",
            AlertSeverity.HIGH: "#ff0000",
            AlertSeverity.CRITICAL: "#8b0000"
        }
        
        payload = {
            "attachments": [{
                "color": color_map.get(alert.severity, "#cccccc"),
                "title": f"Alert: {alert.rule_name}",
                "text": alert.message,
                "fields": [
                    {
                        "title": "Severity",
                        "value": alert.severity.value.upper(),
                        "short": True
                    },
                    {
                        "title": "Time",
                        "value": alert.timestamp.isoformat(),
                        "short": True
                    }
                ],
                "footer": "Research System Alert"
            }]
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload)
    
    async def _send_email_notification(self, alert: Alert):
        """Send email notification"""
        # Implementation would use smtplib or email service
        pass
    
    async def _send_pagerduty_notification(self, alert: Alert):
        """Send PagerDuty notification"""
        
        api_key = self.config.get("pagerduty_api_key")
        if not api_key:
            return
        
        payload = {
            "routing_key": api_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"Research System Alert: {alert.rule_name}",
                "severity": alert.severity.value,
                "source": "research_system",
                "custom_details": {
                    "message": alert.message,
                    "context": alert.context
                }
            }
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload
            )
    
    async def _send_webhook_notification(self, alert: Alert):
        """Send webhook notification"""
        
        webhook_url = self.config.get("webhook_url")
        if not webhook_url:
            return
        
        payload = {
            "alert_id": alert.id,
            "rule_name": alert.rule_name,
            "severity": alert.severity.value,
            "message": alert.message,
            "timestamp": alert.timestamp.isoformat(),
            "context": alert.context
        }
        
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload)
    
    def get_active_alerts(self) -> List[Alert]:
        """Get all active alerts"""
        return list(self.active_alerts.values())
    
    def get_alert_history(self, hours: int = 24) -> List[Alert]:
        """Get alert history for specified hours"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        return [
            alert for alert in self.alert_history
            if alert.timestamp >= cutoff
        ]
    
    def acknowledge_alert(self, rule_name: str, user: str):
        """Acknowledge an alert"""
        
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_by = user
            alert.acknowledged_at = datetime.utcnow()
            
            logger.info(f"Alert acknowledged: {rule_name} by {user}")
    
    def suppress_alert(self, rule_name: str, duration_hours: int = 1):
        """Suppress an alert temporarily"""
        
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            alert.status = AlertStatus.SUPPRESSED
            
            # Auto-resume after duration
            task = asyncio.create_task(self._resume_alert_after(rule_name, duration_hours))
            self._bg_tasks.append(task)
            
            logger.info(f"Alert suppressed: {rule_name} for {duration_hours} hours")
    
    async def _resume_alert_after(self, rule_name: str, hours: int):
        """Resume alert after suppression period"""
        await asyncio.sleep(hours * 3600)
        
        if rule_name in self.active_alerts:
            alert = self.active_alerts[rule_name]
            if alert.status == AlertStatus.SUPPRESSED:
                alert.status = AlertStatus.ACTIVE
                logger.info(f"Alert resumed: {rule_name}")
    
    async def shutdown(self):
        """Gracefully shutdown alert manager and cancel background tasks"""
        for task in self._bg_tasks:
            task.cancel()
        
        # Wait for all tasks to complete or be cancelled
        if self._bg_tasks:
            await asyncio.gather(*self._bg_tasks, return_exceptions=True)
        
        self._bg_tasks.clear()
        logger.info("Alert manager shutdown complete")


@dataclass
class AlertMetrics:
    """Alert metrics"""
    alerts_triggered: int = 0
    alerts_resolved: int = 0
    notifications_sent: int = 0
    notification_failures: int = 0


# Global alert manager instance
alert_manager = None


def init_alerting(config: Dict[str, Any]):
    """Initialize global alerting"""
    global alert_manager
    alert_manager = AlertManager(config)
    return alert_manager


def get_alert_manager():
    """Get global alert manager"""
    return alert_manager