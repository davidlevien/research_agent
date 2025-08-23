"""
Comprehensive error recovery with circuit breakers and fallbacks
"""

import asyncio
import time
from typing import Optional, Callable, Any, Dict
from enum import Enum
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: type = Exception
    name: str = "default"


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.success_count = 0
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        
        # Check if circuit should be opened
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception(f"Circuit breaker {self.config.name} is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.config.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try recovery."""
        return (
            self.last_failure_time and
            time.time() - self.last_failure_time >= self.config.recovery_timeout
        )
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:  # Require 3 successes to close
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info(f"Circuit breaker {self.config.name} CLOSED")
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.config.name} OPEN")
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0


class ErrorRecoveryManager:
    """Comprehensive error recovery system."""
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.fallback_strategies: Dict[str, Callable] = {}
        self.partial_result_handlers: Dict[str, Callable] = {}
    
    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig):
        """Register a circuit breaker for a service."""
        self.circuit_breakers[name] = CircuitBreaker(config)
    
    def register_fallback(self, name: str, fallback: Callable):
        """Register fallback strategy."""
        self.fallback_strategies[name] = fallback
    
    async def execute_with_recovery(
        self,
        operation_name: str,
        operation: Callable,
        fallback: Optional[Callable] = None,
        partial_handler: Optional[Callable] = None,
        *args,
        **kwargs
    ) -> Any:
        """Execute operation with full error recovery."""
        
        # Try with circuit breaker if registered
        if operation_name in self.circuit_breakers:
            breaker = self.circuit_breakers[operation_name]
            try:
                return await breaker.call(operation, *args, **kwargs)
            except Exception as e:
                logger.error(f"Operation {operation_name} failed: {e}")
                
                # Try fallback
                if fallback or operation_name in self.fallback_strategies:
                    fallback_fn = fallback or self.fallback_strategies[operation_name]
                    logger.info(f"Attempting fallback for {operation_name}")
                    
                    try:
                        return await fallback_fn(*args, **kwargs)
                    except Exception as fallback_error:
                        logger.error(f"Fallback failed: {fallback_error}")
                
                # Try partial result handler
                if partial_handler or operation_name in self.partial_result_handlers:
                    handler = partial_handler or self.partial_result_handlers[operation_name]
                    logger.info(f"Generating partial result for {operation_name}")
                    return await handler(*args, **kwargs)
                
                raise
        else:
            # No circuit breaker, execute directly
            return await operation(*args, **kwargs)


# Fallback strategies
async def search_fallback_strategy(query: str, **kwargs) -> list:
    """Fallback search using fewer providers."""
    logger.info("Using fallback search strategy")
    # Try with just one provider
    from research_system.tools.search_tools import search_with_single_provider
    return await search_with_single_provider(query, provider="tavily")


async def llm_fallback_strategy(prompt: str, **kwargs) -> str:
    """Fallback to simpler/cheaper model."""
    logger.info("Using fallback LLM strategy")
    from research_system.tools.llm_tools import generate_with_fallback_model
    return await generate_with_fallback_model(prompt, model="gpt-3.5-turbo")


async def partial_result_handler(request: Any, collected_data: list) -> Any:
    """Generate partial report from available data."""
    logger.info(f"Generating partial report with {len(collected_data)} items")
    from research_system.models import PartialReport
    
    return PartialReport(
        topic=request.topic,
        evidence=collected_data,
        status="partial",
        reason="System degraded - partial results only"
    )