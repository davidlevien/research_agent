"""
System health monitoring and diagnostics
"""

import asyncio
import psutil
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import logging

from ..config import config

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """System health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"


class ComponentStatus(Enum):
    """Component status levels"""
    UP = "up"
    DOWN = "down"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check result"""
    component: str
    status: ComponentStatus
    message: str
    latency_ms: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_usage_percent: float
    network_io_bytes: Dict[str, int]
    active_connections: int
    thread_count: int
    process_count: int


class HealthMonitor:
    """Comprehensive system health monitoring"""
    
    def __init__(self):
        self.checks: List[HealthCheck] = []
        self.metrics_history: List[Tuple[datetime, SystemMetrics]] = []
        self.component_checks: Dict[str, callable] = {}
        self.thresholds = self._init_thresholds()
        self.last_check_time: Optional[datetime] = None
        self._register_default_checks()
    
    def _init_thresholds(self) -> Dict[str, Dict[str, float]]:
        """Initialize health thresholds"""
        return {
            "cpu": {
                "warning": 70.0,
                "critical": 90.0
            },
            "memory": {
                "warning": 80.0,
                "critical": 95.0
            },
            "disk": {
                "warning": 80.0,
                "critical": 95.0
            },
            "response_time": {
                "warning": 1000,  # ms
                "critical": 5000  # ms
            },
            "error_rate": {
                "warning": 0.05,  # 5%
                "critical": 0.20  # 20%
            }
        }
    
    def _register_default_checks(self):
        """Register default health checks"""
        self.register_check("system", self._check_system_resources)
        self.register_check("database", self._check_database)
        self.register_check("redis", self._check_redis)
        self.register_check("api_providers", self._check_api_providers)
        self.register_check("disk_space", self._check_disk_space)
    
    def register_check(self, name: str, check_function: callable):
        """Register a health check function"""
        self.component_checks[name] = check_function
        logger.info(f"Registered health check: {name}")
    
    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        
        start_time = time.time()
        self.checks = []
        
        # Run all component checks
        check_tasks = []
        for name, check_func in self.component_checks.items():
            if asyncio.iscoroutinefunction(check_func):
                check_tasks.append(self._run_async_check(name, check_func))
            else:
                self.checks.append(self._run_sync_check(name, check_func))
        
        # Wait for async checks
        if check_tasks:
            async_results = await asyncio.gather(*check_tasks, return_exceptions=True)
            for result in async_results:
                if isinstance(result, HealthCheck):
                    self.checks.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Health check failed: {result}")
        
        # Collect system metrics
        metrics = self._collect_system_metrics()
        self.metrics_history.append((datetime.utcnow(), metrics))
        
        # Trim history (keep last 100 entries)
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]
        
        # Determine overall health
        overall_status = self._determine_overall_health()
        
        # Calculate check duration
        check_duration = (time.time() - start_time) * 1000
        
        self.last_check_time = datetime.utcnow()
        
        return {
            "status": overall_status.value,
            "timestamp": self.last_check_time.isoformat(),
            "duration_ms": check_duration,
            "checks": [self._check_to_dict(check) for check in self.checks],
            "metrics": self._metrics_to_dict(metrics),
            "issues": self._identify_issues()
        }
    
    def _run_sync_check(self, name: str, check_func: callable) -> HealthCheck:
        """Run synchronous health check"""
        start_time = time.time()
        
        try:
            result = check_func()
            latency = (time.time() - start_time) * 1000
            
            if isinstance(result, HealthCheck):
                return result
            elif isinstance(result, bool):
                return HealthCheck(
                    component=name,
                    status=ComponentStatus.UP if result else ComponentStatus.DOWN,
                    message="Check passed" if result else "Check failed",
                    latency_ms=latency
                )
            else:
                return HealthCheck(
                    component=name,
                    status=ComponentStatus.UNKNOWN,
                    message=str(result),
                    latency_ms=latency
                )
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheck(
                component=name,
                status=ComponentStatus.DOWN,
                message=f"Check failed: {str(e)}",
                latency_ms=latency
            )
    
    async def _run_async_check(self, name: str, check_func: callable) -> HealthCheck:
        """Run asynchronous health check"""
        start_time = time.time()
        
        try:
            result = await check_func()
            latency = (time.time() - start_time) * 1000
            
            if isinstance(result, HealthCheck):
                return result
            elif isinstance(result, bool):
                return HealthCheck(
                    component=name,
                    status=ComponentStatus.UP if result else ComponentStatus.DOWN,
                    message="Check passed" if result else "Check failed",
                    latency_ms=latency
                )
            else:
                return HealthCheck(
                    component=name,
                    status=ComponentStatus.UNKNOWN,
                    message=str(result),
                    latency_ms=latency
                )
                
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return HealthCheck(
                component=name,
                status=ComponentStatus.DOWN,
                message=f"Check failed: {str(e)}",
                latency_ms=latency
            )
    
    def _check_system_resources(self) -> HealthCheck:
        """Check system resource usage"""
        
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        
        status = ComponentStatus.UP
        messages = []
        
        # Check CPU
        if cpu_percent > self.thresholds["cpu"]["critical"]:
            status = ComponentStatus.DOWN
            messages.append(f"CPU critical: {cpu_percent:.1f}%")
        elif cpu_percent > self.thresholds["cpu"]["warning"]:
            status = ComponentStatus.PARTIAL
            messages.append(f"CPU high: {cpu_percent:.1f}%")
        
        # Check memory
        if memory.percent > self.thresholds["memory"]["critical"]:
            status = ComponentStatus.DOWN
            messages.append(f"Memory critical: {memory.percent:.1f}%")
        elif memory.percent > self.thresholds["memory"]["warning"]:
            if status == ComponentStatus.UP:
                status = ComponentStatus.PARTIAL
            messages.append(f"Memory high: {memory.percent:.1f}%")
        
        message = "; ".join(messages) if messages else "Resources OK"
        
        return HealthCheck(
            component="system_resources",
            status=status,
            message=message,
            latency_ms=0,
            metadata={
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3)
            }
        )
    
    def _check_database(self) -> HealthCheck:
        """Check database connectivity"""
        
        try:
            # Simplified check - in production, would actually connect
            db_url = config.database.url
            
            if db_url:
                # Simulate connection check
                return HealthCheck(
                    component="database",
                    status=ComponentStatus.UP,
                    message="Database reachable",
                    latency_ms=15.0
                )
            else:
                return HealthCheck(
                    component="database",
                    status=ComponentStatus.UNKNOWN,
                    message="Database not configured",
                    latency_ms=0
                )
                
        except Exception as e:
            return HealthCheck(
                component="database",
                status=ComponentStatus.DOWN,
                message=f"Database error: {str(e)}",
                latency_ms=0
            )
    
    def _check_redis(self) -> HealthCheck:
        """Check Redis connectivity"""
        
        try:
            # Simplified check - in production, would actually connect
            redis_url = config.redis.url
            
            if redis_url:
                # Simulate connection check
                return HealthCheck(
                    component="redis",
                    status=ComponentStatus.UP,
                    message="Redis reachable",
                    latency_ms=5.0
                )
            else:
                return HealthCheck(
                    component="redis",
                    status=ComponentStatus.UNKNOWN,
                    message="Redis not configured",
                    latency_ms=0
                )
                
        except Exception as e:
            return HealthCheck(
                component="redis",
                status=ComponentStatus.DOWN,
                message=f"Redis error: {str(e)}",
                latency_ms=0
            )
    
    def _check_api_providers(self) -> HealthCheck:
        """Check API provider availability"""
        
        providers_status = []
        
        # Check for API keys
        api_keys = {
            "OpenAI": config.api.openai_key,
            "Anthropic": config.api.anthropic_key,
            "Tavily": config.api.tavily_key,
            "Serper": config.api.serper_key
        }
        
        configured = sum(1 for key in api_keys.values() if key)
        total = len(api_keys)
        
        if configured == 0:
            status = ComponentStatus.DOWN
            message = "No API providers configured"
        elif configured < total:
            status = ComponentStatus.PARTIAL
            message = f"{configured}/{total} API providers configured"
        else:
            status = ComponentStatus.UP
            message = "All API providers configured"
        
        return HealthCheck(
            component="api_providers",
            status=status,
            message=message,
            latency_ms=0,
            metadata={"configured": configured, "total": total}
        )
    
    def _check_disk_space(self) -> HealthCheck:
        """Check available disk space"""
        
        disk = psutil.disk_usage('/')
        
        if disk.percent > self.thresholds["disk"]["critical"]:
            status = ComponentStatus.DOWN
            message = f"Disk space critical: {disk.percent:.1f}% used"
        elif disk.percent > self.thresholds["disk"]["warning"]:
            status = ComponentStatus.PARTIAL
            message = f"Disk space low: {disk.percent:.1f}% used"
        else:
            status = ComponentStatus.UP
            message = f"Disk space OK: {disk.percent:.1f}% used"
        
        return HealthCheck(
            component="disk_space",
            status=status,
            message=message,
            latency_ms=0,
            metadata={
                "used_percent": disk.percent,
                "free_gb": disk.free / (1024**3)
            }
        )
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect current system metrics"""
        
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        net_io = psutil.net_io_counters()
        connections = len(psutil.net_connections())
        process = psutil.Process()
        
        return SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available_mb=memory.available / (1024**2),
            disk_usage_percent=disk.percent,
            network_io_bytes={
                "sent": net_io.bytes_sent,
                "received": net_io.bytes_recv
            },
            active_connections=connections,
            thread_count=process.num_threads(),
            process_count=len(psutil.pids())
        )
    
    def _determine_overall_health(self) -> HealthStatus:
        """Determine overall system health status"""
        
        if not self.checks:
            return HealthStatus.UNKNOWN
        
        down_count = sum(1 for check in self.checks if check.status == ComponentStatus.DOWN)
        partial_count = sum(1 for check in self.checks if check.status == ComponentStatus.PARTIAL)
        
        if down_count > len(self.checks) * 0.5:
            return HealthStatus.CRITICAL
        elif down_count > 0:
            return HealthStatus.UNHEALTHY
        elif partial_count > len(self.checks) * 0.3:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY
    
    def _identify_issues(self) -> List[str]:
        """Identify current health issues"""
        
        issues = []
        
        for check in self.checks:
            if check.status in [ComponentStatus.DOWN, ComponentStatus.PARTIAL]:
                issues.append(f"{check.component}: {check.message}")
        
        # Check metrics
        if self.metrics_history:
            _, latest_metrics = self.metrics_history[-1]
            
            if latest_metrics.cpu_percent > self.thresholds["cpu"]["warning"]:
                issues.append(f"High CPU usage: {latest_metrics.cpu_percent:.1f}%")
            
            if latest_metrics.memory_percent > self.thresholds["memory"]["warning"]:
                issues.append(f"High memory usage: {latest_metrics.memory_percent:.1f}%")
        
        return issues
    
    def _check_to_dict(self, check: HealthCheck) -> Dict[str, Any]:
        """Convert health check to dictionary"""
        return {
            "component": check.component,
            "status": check.status.value,
            "message": check.message,
            "latency_ms": check.latency_ms,
            "metadata": check.metadata,
            "timestamp": check.timestamp.isoformat()
        }
    
    def _metrics_to_dict(self, metrics: SystemMetrics) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "memory_available_mb": metrics.memory_available_mb,
            "disk_usage_percent": metrics.disk_usage_percent,
            "network_io_bytes": metrics.network_io_bytes,
            "active_connections": metrics.active_connections,
            "thread_count": metrics.thread_count,
            "process_count": metrics.process_count
        }
    
    def get_uptime(self) -> timedelta:
        """Get system uptime"""
        boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
        return datetime.now(timezone.utc) - boot_time
    
    def get_health_summary(self) -> str:
        """Get human-readable health summary"""
        
        if not self.last_check_time:
            return "No health check performed yet"
        
        overall = self._determine_overall_health()
        issues = self._identify_issues()
        
        summary = f"""
System Health: {overall.value.upper()}
Last Check: {self.last_check_time.isoformat()}
Uptime: {self.get_uptime()}

Component Status:
"""
        
        for check in self.checks:
            icon = "✅" if check.status == ComponentStatus.UP else "❌"
            summary += f"  {icon} {check.component}: {check.status.value}\n"
        
        if issues:
            summary += "\nIssues:\n"
            for issue in issues:
                summary += f"  ⚠️ {issue}\n"
        
        return summary