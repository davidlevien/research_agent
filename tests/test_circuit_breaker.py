"""Tests for circuit breaker functionality."""

import pytest
import time
import os
from research_system.net.circuit import Circuit


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    def test_circuit_starts_closed(self):
        """Test circuit starts in closed state."""
        circuit = Circuit(fail_thresh=3, cooldown=1)
        
        assert circuit.allow("example.com")
        assert not circuit.is_open("example.com")
    
    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        circuit = Circuit(fail_thresh=3, cooldown=1)
        
        # Record failures
        circuit.fail("example.com")
        assert circuit.allow("example.com")  # Still closed
        
        circuit.fail("example.com")
        assert circuit.allow("example.com")  # Still closed
        
        circuit.fail("example.com")  # Third failure
        assert not circuit.allow("example.com")  # Now open
        assert circuit.is_open("example.com")
    
    def test_circuit_closes_after_cooldown(self):
        """Test circuit closes after cooldown period."""
        circuit = Circuit(fail_thresh=2, cooldown=1)
        
        # Open the circuit
        circuit.fail("example.com")
        circuit.fail("example.com")
        assert circuit.is_open("example.com")
        
        # Wait for cooldown
        time.sleep(1.1)
        
        # Circuit should be closed again
        assert circuit.allow("example.com")
        assert not circuit.is_open("example.com")
    
    def test_circuit_resets_on_success(self):
        """Test circuit resets failure count on success."""
        circuit = Circuit(fail_thresh=3, cooldown=1)
        
        # Record some failures
        circuit.fail("example.com")
        circuit.fail("example.com")
        
        # Record success
        circuit.ok("example.com")
        
        # Failure count should be reset
        circuit.fail("example.com")
        circuit.fail("example.com")
        assert circuit.allow("example.com")  # Still closed (only 2 failures after reset)
    
    def test_manual_reset(self):
        """Test manual circuit reset."""
        circuit = Circuit(fail_thresh=2, cooldown=10)
        
        # Open the circuit
        circuit.fail("example.com")
        circuit.fail("example.com")
        assert circuit.is_open("example.com")
        
        # Manual reset
        circuit.reset("example.com")
        assert circuit.allow("example.com")
        assert not circuit.is_open("example.com")
    
    def test_different_hosts_independent(self):
        """Test different hosts have independent circuits."""
        circuit = Circuit(fail_thresh=2, cooldown=1)
        
        # Fail host1
        circuit.fail("host1.com")
        circuit.fail("host1.com")
        assert circuit.is_open("host1.com")
        
        # host2 should still be closed
        assert circuit.allow("host2.com")
        assert not circuit.is_open("host2.com")
    
    def test_environment_configuration(self):
        """Test circuit breaker reads from environment."""
        # Set environment variables
        os.environ["HTTP_CB_FAILS"] = "5"
        os.environ["HTTP_CB_RESET"] = "120"
        
        try:
            circuit = Circuit()
            
            # Should use environment values
            assert circuit.th == 5  # fail threshold
            assert circuit.cd == 120  # cooldown
            
            # Verify it takes 5 failures to open
            for i in range(4):
                circuit.fail("test.com")
                assert circuit.allow("test.com")
            
            circuit.fail("test.com")  # 5th failure
            assert not circuit.allow("test.com")
            
        finally:
            # Clean up
            del os.environ["HTTP_CB_FAILS"]
            del os.environ["HTTP_CB_RESET"]
    
    def test_default_values_without_env(self):
        """Test circuit breaker uses defaults when no environment set."""
        circuit = Circuit()
        
        # Should use defaults
        assert circuit.th == 3  # default fail threshold
        assert circuit.cd == 900  # default cooldown (15 minutes)
    
    def test_explicit_values_override_env(self):
        """Test explicit values override environment."""
        os.environ["HTTP_CB_FAILS"] = "10"
        os.environ["HTTP_CB_RESET"] = "300"
        
        try:
            circuit = Circuit(fail_thresh=2, cooldown=5)
            
            # Should use explicit values, not environment
            assert circuit.th == 2
            assert circuit.cd == 5
            
        finally:
            # Clean up
            del os.environ["HTTP_CB_FAILS"]
            del os.environ["HTTP_CB_RESET"]
    
    def test_global_instance(self):
        """Test global circuit breaker instance."""
        from research_system.net.circuit import CIRCUIT
        
        # Should be a Circuit instance
        assert isinstance(CIRCUIT, Circuit)
        
        # Should work normally
        assert CIRCUIT.allow("test.com")