"""
Custom exceptions for the research system
"""


class ResearchSystemError(Exception):
    """Base exception for research system"""
    pass


class ConfigurationError(ResearchSystemError):
    """Configuration related errors"""
    pass


class ValidationError(ResearchSystemError):
    """Validation errors"""
    pass


class PlanningError(ResearchSystemError):
    """Research planning errors"""
    pass


class CollectionError(ResearchSystemError):
    """Evidence collection errors"""
    pass


class APIError(ResearchSystemError):
    """API related errors"""
    def __init__(self, message: str, provider: str = None, status_code: int = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class RateLimitError(APIError):
    """Rate limit exceeded"""
    pass


class CostLimitError(ResearchSystemError):
    """Cost limit exceeded"""
    def __init__(self, message: str, current_cost: float, limit: float):
        super().__init__(message)
        self.current_cost = current_cost
        self.limit = limit


class TimeoutError(ResearchSystemError):
    """Operation timeout"""
    pass


class SecurityError(ResearchSystemError):
    """Security related errors"""
    pass


class DataQualityError(ResearchSystemError):
    """Data quality issues"""
    pass


class CircuitBreakerOpen(ResearchSystemError):
    """Circuit breaker is open"""
    def __init__(self, service: str):
        super().__init__(f"Circuit breaker for {service} is OPEN")
        self.service = service


class PartialResultError(ResearchSystemError):
    """Partial results due to errors"""
    def __init__(self, message: str, partial_data: list = None):
        super().__init__(message)
        self.partial_data = partial_data or []