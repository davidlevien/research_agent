# research_system/monitoring/tracing.py
"""
OpenTelemetry tracing implementation
"""

import time
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
import structlog

logger = structlog.get_logger()

# Global tracer
tracer = None


class TracingManager:
    """Comprehensive tracing management system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tracer_provider = None
        self.tracer = None
        self.active_spans: List[trace.Span] = []
        self._setup_tracing()
    
    def _setup_tracing(self):
        """Initialize OpenTelemetry tracing"""
        global tracer
        
        # Create resource
        resource = Resource.create({
            "service.name": "research_system",
            "service.version": "5.0.0",
            "deployment.environment": self.config.get("environment", "development")
        })
        
        # Create tracer provider
        self.tracer_provider = TracerProvider(resource=resource)
        
        # Add span processors
        if self.config.get("enable_console_export", False):
            console_exporter = ConsoleSpanExporter()
            self.tracer_provider.add_span_processor(
                BatchSpanProcessor(console_exporter)
            )
        
        # Add OTLP exporter if configured
        otlp_endpoint = self.config.get("otlp_endpoint")
        if otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                otlp_exporter = OTLPSpanExporter(
                    endpoint=otlp_endpoint,
                    insecure=True
                )
                self.tracer_provider.add_span_processor(
                    BatchSpanProcessor(otlp_exporter)
                )
                logger.info(f"OTLP tracing enabled: {otlp_endpoint}")
            except Exception as e:
                logger.warning(f"OTLP tracing setup failed: {e}")
        
        # Set global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Create tracer
        self.tracer = trace.get_tracer(__name__)
        tracer = self.tracer
        
        # Setup instrumentations
        self._setup_instrumentations()
    
    def _setup_instrumentations(self):
        """Setup automatic instrumentations"""
        try:
            # HTTP client instrumentation
            HTTPXClientInstrumentor().instrument()
            logger.info("HTTPX instrumentation enabled")
        except Exception as e:
            logger.warning(f"HTTPX instrumentation failed: {e}")
        
        try:
            # Redis instrumentation
            RedisInstrumentor().instrument()
            logger.info("Redis instrumentation enabled")
        except Exception as e:
            logger.warning(f"Redis instrumentation failed: {e}")
        
        try:
            # SQLAlchemy instrumentation
            SQLAlchemyInstrumentor().instrument()
            logger.info("SQLAlchemy instrumentation enabled")
        except Exception as e:
            logger.warning(f"SQLAlchemy instrumentation failed: {e}")
    
    @asynccontextmanager
    async def trace_operation(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span: Optional[trace.Span] = None
    ):
        """Context manager for tracing operations"""
        
        if not self.tracer:
            yield None
            return
        
        span = self.tracer.start_span(
            operation_name,
            attributes=attributes or {},
            parent=parent_span
        )
        
        self.active_spans.append(span)
        
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise
        finally:
            span.end()
            if span in self.active_spans:
                self.active_spans.remove(span)
    
    def add_event(self, span: trace.Span, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add event to span"""
        if span:
            span.add_event(name, attributes or {})
    
    def set_attribute(self, span: trace.Span, key: str, value: Any):
        """Set attribute on span"""
        if span:
            span.set_attribute(key, value)
    
    def trace_research_request(self, request_id: str, topic: str, depth: str):
        """Create span for research request"""
        return self.tracer.start_span(
            "research_request",
            attributes={
                "request.id": request_id,
                "research.topic": topic,
                "research.depth": depth,
                "service.name": "research_system"
            }
        )
    
    def trace_phase(self, phase_name: str, parent_span: Optional[trace.Span] = None):
        """Create span for research phase"""
        return self.tracer.start_span(
            f"research_phase.{phase_name}",
            parent=parent_span,
            attributes={
                "phase.name": phase_name,
                "service.name": "research_system"
            }
        )
    
    def trace_api_call(
        self,
        provider: str,
        endpoint: str,
        method: str = "GET",
        parent_span: Optional[trace.Span] = None
    ):
        """Create span for API call"""
        return self.tracer.start_span(
            "api_call",
            parent=parent_span,
            attributes={
                "api.provider": provider,
                "api.endpoint": endpoint,
                "api.method": method,
                "service.name": "research_system"
            }
        )
    
    def trace_evidence_processing(
        self,
        evidence_id: str,
        source_domain: str,
        parent_span: Optional[trace.Span] = None
    ):
        """Create span for evidence processing"""
        return self.tracer.start_span(
            "evidence_processing",
            parent=parent_span,
            attributes={
                "evidence.id": evidence_id,
                "evidence.source_domain": source_domain,
                "service.name": "research_system"
            }
        )
    
    def get_trace_id(self, span: trace.Span) -> str:
        """Get trace ID from span"""
        if span:
            return format(span.get_span_context().trace_id, "032x")
        return "00000000000000000000000000000000"
    
    def get_span_id(self, span: trace.Span) -> str:
        """Get span ID from span"""
        if span:
            return format(span.get_span_context().span_id, "016x")
        return "0000000000000000"
    
    def export_traces(self):
        """Force export of all traces"""
        if self.tracer_provider:
            self.tracer_provider.force_flush()
    
    def shutdown(self):
        """Shutdown tracing system"""
        if self.tracer_provider:
            self.tracer_provider.shutdown()


# Global tracing manager instance
tracing_manager = None


def init_tracing(config: Dict[str, Any]):
    """Initialize global tracing"""
    global tracing_manager
    tracing_manager = TracingManager(config)
    return tracing_manager


def get_tracer():
    """Get global tracer"""
    return tracer


def get_tracing_manager():
    """Get global tracing manager"""
    return tracing_manager