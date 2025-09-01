"""
Comprehensive monitoring with Prometheus metrics
"""

from prometheus_client import Counter, Histogram, Gauge, Info
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
import time
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()

# Prometheus metrics
research_requests = Counter(
    'research_requests_total',
    'Total number of research requests',
    ['topic_category', 'depth', 'status']
)

research_duration = Histogram(
    'research_duration_seconds',
    'Research execution duration',
    ['phase', 'depth'],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

evidence_quality = Histogram(
    'evidence_quality_score',
    'Distribution of evidence quality scores',
    ['source_type'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

api_calls = Counter(
    'api_calls_total',
    'Total API calls',
    ['provider', 'endpoint', 'status']
)

cost_consumed = Counter(
    'cost_consumed_usd',
    'Total cost consumed in USD',
    ['component', 'provider']
)

active_researches = Gauge(
    'active_researches',
    'Number of active research operations'
)

system_health = Gauge(
    'system_health_score',
    'Overall system health score (0-1)'
)

# OpenTelemetry setup
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Configure OTLP exporter
otlp_exporter = OTLPSpanExporter(
    endpoint="localhost:4317",
    insecure=True
)

span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)


class ObservabilityManager:
    """Comprehensive observability management."""
    
    def __init__(self):
        self.tracer = tracer
        self.metrics = {
            'requests': research_requests,
            'duration': research_duration,
            'quality': evidence_quality,
            'api_calls': api_calls,
            'cost': cost_consumed,
            'active': active_researches,
            'health': system_health
        }
        self.alert_manager = AlertManager()
    
    def start_research_trace(self, request_id: str, topic: str) -> Any:
        """Start distributed trace for research."""
        return self.tracer.start_as_current_span(
            "research_execution",
            attributes={
                "request.id": request_id,
                "research.topic": topic,
                "service.name": "research_system"
            }
        )
    
    def record_phase_duration(self, phase: str, depth: str, duration: float):
        """Record phase execution duration."""
        self.metrics['duration'].labels(
            phase=phase,
            depth=depth
        ).observe(duration)
        
        # Check for anomalies
        if duration > self._get_phase_threshold(phase):
            self.alert_manager.trigger_alert(
                "slow_phase_execution",
                {
                    "phase": phase,
                    "duration": duration,
                    "threshold": self._get_phase_threshold(phase)
                }
            )
    
    def record_evidence_quality(self, source_type: str, quality_score: float):
        """Record evidence quality metrics."""
        self.metrics['quality'].labels(
            source_type=source_type
        ).observe(quality_score)
        
        # Alert on low quality
        if quality_score < 0.3:
            self.alert_manager.trigger_alert(
                "low_quality_evidence",
                {
                    "source_type": source_type,
                    "quality_score": quality_score
                }
            )
    
    def record_api_call(self, provider: str, endpoint: str, status: str):
        """Record API call metrics."""
        self.metrics['api_calls'].labels(
            provider=provider,
            endpoint=endpoint,
            status=status
        ).inc()
        
        # Track failures
        if status != "success":
            self.alert_manager.check_api_health(provider, status)
    
    def update_system_health(self):
        """Calculate and update system health score."""
        health_score = self._calculate_health_score()
        self.metrics['health'].set(health_score)
        
        if health_score < 0.5:
            self.alert_manager.trigger_alert(
                "system_health_degraded",
                {"health_score": health_score}
            )
    
    def _calculate_health_score(self) -> float:
        """Calculate overall system health (0-1)."""
        factors = {
            'api_availability': self._check_api_availability(),
            'error_rate': 1 - self._get_error_rate(),
            'response_time': self._check_response_times(),
            'resource_usage': self._check_resource_usage()
        }
        
        # Weighted average
        weights = {
            'api_availability': 0.3,
            'error_rate': 0.3,
            'response_time': 0.2,
            'resource_usage': 0.2
        }
        
        score = sum(
            factors[k] * weights[k]
            for k in factors
        )
        
        return min(max(score, 0), 1)
    
    def _get_phase_threshold(self, phase: str) -> float:
        """Get duration threshold for phase."""
        thresholds = {
            'planning': 10,
            'collection': 60,
            'verification': 20,
            'synthesis': 30
        }
        return thresholds.get(phase, 30)
    
    def _check_api_availability(self) -> float:
        """Check API availability score."""
        # Implementation would check actual API health
        return 0.95
    
    def _get_error_rate(self) -> float:
        """Get current error rate."""
        # Implementation would calculate from metrics
        return 0.02
    
    def _check_response_times(self) -> float:
        """Check response time health."""
        # Implementation would check p95 latencies
        return 0.9
    
    def _check_resource_usage(self) -> float:
        """Check resource usage health."""
        # Implementation would check CPU/memory
        return 0.85


class MetricsReporter:
    """Metrics reporting system (renamed from AlertManager to avoid naming conflict)."""
    
    def __init__(self):
        self.alert_thresholds = {
            'api_failure_rate': 0.1,
            'cost_threshold': 0.8,
            'duration_threshold': 2.0
        }
        self.alert_history = []
    
    def trigger_alert(self, alert_type: str, context: Dict[str, Any]):
        """Trigger an alert."""
        alert = {
            'type': alert_type,
            'context': context,
            'timestamp': time.time(),
            'severity': self._determine_severity(alert_type)
        }
        
        self.alert_history.append(alert)
        
        # Send to external systems
        self._send_to_alerting_system(alert)
        
        logger.warning(
            "alert_triggered",
            alert_type=alert_type,
            **context
        )
    
    def check_api_health(self, provider: str, status: str):
        """Check API health and alert if needed."""
        # Track failures per provider
        # Alert if threshold exceeded
        pass
    
    def _determine_severity(self, alert_type: str) -> str:
        """Determine alert severity."""
        critical = ['system_health_degraded', 'all_apis_down']
        high = ['cost_limit_approaching', 'high_error_rate']
        medium = ['slow_phase_execution', 'low_quality_evidence']
        
        if alert_type in critical:
            return 'critical'
        elif alert_type in high:
            return 'high'
        elif alert_type in medium:
            return 'medium'
        else:
            return 'low'
    
    def _send_to_alerting_system(self, alert: Dict):
        """Send alert to external system (PagerDuty, Slack, etc.)."""
        # Implementation would integrate with alerting services
        pass