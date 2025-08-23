"""
Advanced cost management system
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CostCategory(Enum):
    """Cost categories for tracking"""
    SEARCH = "search"
    LLM = "llm"
    STORAGE = "storage"
    COMPUTE = "compute"
    NETWORK = "network"


@dataclass
class CostLimit:
    """Cost limit configuration"""
    soft_limit: float
    hard_limit: float
    alert_threshold: float = 0.8
    enforcement: str = "warn"  # warn, throttle, stop


@dataclass
class CostMetrics:
    """Cost tracking metrics"""
    total_cost: float = 0.0
    cost_by_category: Dict[str, float] = field(default_factory=dict)
    cost_by_provider: Dict[str, float] = field(default_factory=dict)
    api_calls: Dict[str, int] = field(default_factory=dict)
    last_reset: datetime = field(default_factory=datetime.utcnow)


class CostManager:
    """Advanced cost management with tracking, limits, and optimization"""
    
    # Cost rates per provider/operation
    COST_RATES = {
        "openai": {
            "gpt-4": 0.03,  # per 1K tokens
            "gpt-3.5-turbo": 0.002,  # per 1K tokens
            "embeddings": 0.0001,  # per 1K tokens
        },
        "anthropic": {
            "claude-3": 0.025,  # per 1K tokens
            "claude-2": 0.01,  # per 1K tokens
        },
        "tavily": {
            "search": 0.001,  # per search
            "deep_search": 0.005,  # per deep search
        },
        "serper": {
            "search": 0.002,  # per search
        },
        "storage": {
            "s3": 0.023,  # per GB/month
            "redis": 0.016,  # per GB/hour
        },
        "compute": {
            "cpu_hour": 0.05,
            "gpu_hour": 0.90,
        }
    }
    
    def __init__(self):
        self.metrics = CostMetrics()
        self.limits: Dict[str, CostLimit] = {}
        self.budgets: Dict[str, float] = {}
        self.cost_history: List[Dict[str, Any]] = []
        self.optimization_enabled = True
        self._init_default_limits()
    
    def _init_default_limits(self):
        """Initialize default cost limits"""
        self.limits = {
            "per_request": CostLimit(
                soft_limit=0.5,
                hard_limit=1.0,
                alert_threshold=0.8,
                enforcement="warn"
            ),
            "daily": CostLimit(
                soft_limit=50.0,
                hard_limit=100.0,
                alert_threshold=0.8,
                enforcement="throttle"
            ),
            "monthly": CostLimit(
                soft_limit=1000.0,
                hard_limit=2000.0,
                alert_threshold=0.9,
                enforcement="stop"
            )
        }
    
    def track_cost(
        self,
        amount: float,
        category: CostCategory,
        provider: str,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track cost and check limits
        
        Returns:
            bool: True if within limits, False if limit exceeded
        """
        
        # Update metrics
        self.metrics.total_cost += amount
        
        category_str = category.value
        if category_str not in self.metrics.cost_by_category:
            self.metrics.cost_by_category[category_str] = 0
        self.metrics.cost_by_category[category_str] += amount
        
        if provider not in self.metrics.cost_by_provider:
            self.metrics.cost_by_provider[provider] = 0
        self.metrics.cost_by_provider[provider] += amount
        
        # Track API calls
        api_key = f"{provider}:{operation}"
        if api_key not in self.metrics.api_calls:
            self.metrics.api_calls[api_key] = 0
        self.metrics.api_calls[api_key] += 1
        
        # Add to history
        self.cost_history.append({
            "timestamp": datetime.utcnow(),
            "amount": amount,
            "category": category_str,
            "provider": provider,
            "operation": operation,
            "metadata": metadata or {}
        })
        
        # Check limits
        within_limits = self._check_limits(amount)
        
        # Log cost
        logger.info(
            f"Cost tracked: ${amount:.4f} | "
            f"Category: {category_str} | "
            f"Provider: {provider} | "
            f"Total: ${self.metrics.total_cost:.2f}"
        )
        
        return within_limits
    
    def _check_limits(self, new_cost: float) -> bool:
        """Check if cost is within limits"""
        
        violations = []
        
        # Check per-request limit
        if "per_request" in self.limits:
            limit = self.limits["per_request"]
            if new_cost > limit.hard_limit:
                violations.append(("per_request", "hard", new_cost))
            elif new_cost > limit.soft_limit:
                violations.append(("per_request", "soft", new_cost))
        
        # Check daily limit
        daily_cost = self.get_daily_cost()
        if "daily" in self.limits:
            limit = self.limits["daily"]
            if daily_cost > limit.hard_limit:
                violations.append(("daily", "hard", daily_cost))
            elif daily_cost > limit.soft_limit:
                violations.append(("daily", "soft", daily_cost))
            elif daily_cost > limit.soft_limit * limit.alert_threshold:
                logger.warning(f"Approaching daily cost limit: ${daily_cost:.2f}")
        
        # Check monthly limit
        monthly_cost = self.get_monthly_cost()
        if "monthly" in self.limits:
            limit = self.limits["monthly"]
            if monthly_cost > limit.hard_limit:
                violations.append(("monthly", "hard", monthly_cost))
            elif monthly_cost > limit.soft_limit:
                violations.append(("monthly", "soft", monthly_cost))
        
        # Handle violations
        for limit_type, severity, amount in violations:
            self._handle_limit_violation(limit_type, severity, amount)
        
        # Return False if any hard limit exceeded
        return not any(sev == "hard" for _, sev, _ in violations)
    
    def _handle_limit_violation(
        self,
        limit_type: str,
        severity: str,
        amount: float
    ):
        """Handle cost limit violations"""
        
        limit = self.limits[limit_type]
        
        if severity == "hard":
            logger.error(
                f"HARD LIMIT EXCEEDED: {limit_type} = ${amount:.2f} "
                f"(limit: ${limit.hard_limit:.2f})"
            )
            
            if limit.enforcement == "stop":
                raise Exception(f"Cost limit exceeded: {limit_type}")
            
        elif severity == "soft":
            logger.warning(
                f"Soft limit exceeded: {limit_type} = ${amount:.2f} "
                f"(limit: ${limit.soft_limit:.2f})"
            )
            
            if limit.enforcement == "throttle":
                # Implement throttling logic
                time.sleep(1)  # Simple throttle
    
    def calculate_operation_cost(
        self,
        provider: str,
        operation: str,
        units: int = 1,
        unit_type: str = "request"
    ) -> float:
        """Calculate cost for an operation"""
        
        if provider not in self.COST_RATES:
            return 0.0
        
        if operation not in self.COST_RATES[provider]:
            return 0.0
        
        rate = self.COST_RATES[provider][operation]
        
        # Adjust for unit type
        if unit_type == "tokens":
            return (units / 1000) * rate  # Convert to per-1K tokens
        elif unit_type == "gb_hour":
            return units * rate
        else:
            return units * rate
    
    def estimate_request_cost(
        self,
        request_config: Dict[str, Any]
    ) -> Dict[str, float]:
        """Estimate cost for a research request"""
        
        estimates = {
            "search": 0.0,
            "llm": 0.0,
            "storage": 0.0,
            "total": 0.0
        }
        
        # Estimate search costs
        num_searches = request_config.get("num_searches", 10)
        search_depth = request_config.get("search_depth", "basic")
        
        if search_depth == "deep":
            estimates["search"] = num_searches * self.COST_RATES["tavily"]["deep_search"]
        else:
            estimates["search"] = num_searches * self.COST_RATES["tavily"]["search"]
        
        # Estimate LLM costs
        estimated_tokens = request_config.get("estimated_tokens", 10000)
        llm_model = request_config.get("llm_model", "gpt-3.5-turbo")
        
        if "gpt" in llm_model:
            provider = "openai"
        else:
            provider = "anthropic"
            
        if llm_model in self.COST_RATES.get(provider, {}):
            estimates["llm"] = self.calculate_operation_cost(
                provider,
                llm_model,
                estimated_tokens,
                "tokens"
            )
        
        # Estimate storage costs
        estimated_storage_gb = request_config.get("estimated_storage_gb", 0.001)
        estimates["storage"] = estimated_storage_gb * self.COST_RATES["storage"]["s3"]
        
        estimates["total"] = sum(estimates.values())
        
        return estimates
    
    def optimize_cost(
        self,
        operation: str,
        options: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Optimize operation selection based on cost"""
        
        if not self.optimization_enabled:
            return options[0] if options else {}
        
        best_option = None
        best_cost = float('inf')
        
        for option in options:
            cost = self.calculate_operation_cost(
                option.get("provider"),
                option.get("operation"),
                option.get("units", 1),
                option.get("unit_type", "request")
            )
            
            # Factor in quality/performance if available
            quality_factor = option.get("quality_factor", 1.0)
            adjusted_cost = cost / quality_factor
            
            if adjusted_cost < best_cost:
                best_cost = adjusted_cost
                best_option = option
        
        logger.info(f"Cost optimization selected: {best_option}")
        return best_option or options[0]
    
    def get_daily_cost(self) -> float:
        """Get total cost for current day"""
        
        today = datetime.utcnow().date()
        daily_cost = 0.0
        
        for entry in self.cost_history:
            if entry["timestamp"].date() == today:
                daily_cost += entry["amount"]
        
        return daily_cost
    
    def get_monthly_cost(self) -> float:
        """Get total cost for current month"""
        
        current_month = datetime.utcnow().replace(day=1)
        monthly_cost = 0.0
        
        for entry in self.cost_history:
            if entry["timestamp"] >= current_month:
                monthly_cost += entry["amount"]
        
        return monthly_cost
    
    def get_cost_breakdown(self) -> Dict[str, Any]:
        """Get detailed cost breakdown"""
        
        return {
            "total": self.metrics.total_cost,
            "by_category": self.metrics.cost_by_category,
            "by_provider": self.metrics.cost_by_provider,
            "daily": self.get_daily_cost(),
            "monthly": self.get_monthly_cost(),
            "api_calls": self.metrics.api_calls,
            "average_per_call": self._calculate_average_cost_per_call()
        }
    
    def _calculate_average_cost_per_call(self) -> Dict[str, float]:
        """Calculate average cost per API call"""
        
        averages = {}
        
        for api_key, count in self.metrics.api_calls.items():
            provider = api_key.split(":")[0]
            if provider in self.metrics.cost_by_provider and count > 0:
                averages[api_key] = self.metrics.cost_by_provider[provider] / count
        
        return averages
    
    def reset_daily_metrics(self):
        """Reset daily cost metrics"""
        
        # Archive current metrics
        self.archive_metrics()
        
        # Reset daily counters
        self.metrics = CostMetrics()
        logger.info("Daily cost metrics reset")
    
    def archive_metrics(self):
        """Archive current metrics for historical analysis"""
        
        archive_entry = {
            "timestamp": datetime.utcnow(),
            "metrics": {
                "total_cost": self.metrics.total_cost,
                "cost_by_category": dict(self.metrics.cost_by_category),
                "cost_by_provider": dict(self.metrics.cost_by_provider),
                "api_calls": dict(self.metrics.api_calls)
            }
        }
        
        # In production, save to database or S3
        logger.info(f"Metrics archived: {archive_entry}")
    
    def generate_cost_report(self) -> str:
        """Generate detailed cost report"""
        
        breakdown = self.get_cost_breakdown()
        
        report = f"""
# Cost Management Report
Generated: {datetime.utcnow().isoformat()}

## Summary
- Total Cost: ${breakdown['total']:.2f}
- Daily Cost: ${breakdown['daily']:.2f}
- Monthly Cost: ${breakdown['monthly']:.2f}

## By Category
"""
        for category, cost in breakdown['by_category'].items():
            report += f"- {category}: ${cost:.2f}\n"
        
        report += "\n## By Provider\n"
        for provider, cost in breakdown['by_provider'].items():
            report += f"- {provider}: ${cost:.2f}\n"
        
        report += "\n## API Calls\n"
        for api, count in breakdown['api_calls'].items():
            avg_cost = breakdown['average_per_call'].get(api, 0)
            report += f"- {api}: {count} calls (avg: ${avg_cost:.4f})\n"
        
        return report