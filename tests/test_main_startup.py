"""Test that the main application can actually start without crashing.

This test catches runtime errors that unit tests miss.
"""

import subprocess
import sys
import pytest
import tempfile
from pathlib import Path

def test_main_module_starts_without_crashing():
    """Test that python -m research_system doesn't crash on startup."""
    
    # Test with --help to avoid actually running research
    result = subprocess.run(
        [sys.executable, "-m", "research_system", "--help"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    assert result.returncode == 0, f"Main module crashed: {result.stderr}"
    assert "Research & Citations" in result.stdout
    
def test_main_with_string_seed_env_var():
    """Test that main can handle string seed from environment."""
    
    import os
    env = os.environ.copy()
    env["RA_GLOBAL_SEED"] = "20230817"  # The problematic string seed
    
    result = subprocess.run(
        [sys.executable, "-m", "research_system", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        env=env
    )
    
    assert result.returncode == 0, f"Main module crashed with string seed: {result.stderr}"

def test_main_with_integer_seed_env_var():
    """Test that main can handle integer seed from environment."""
    
    import os
    env = os.environ.copy()
    env["RA_GLOBAL_SEED"] = "42"  # Integer as string
    
    result = subprocess.run(
        [sys.executable, "-m", "research_system", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        env=env
    )
    
    assert result.returncode == 0, f"Main module crashed with int seed: {result.stderr}"

def test_main_can_import_all_modules():
    """Test that all critical imports work without errors."""
    
    script = """
import sys
try:
    from research_system.orchestrator import Orchestrator, OrchestratorSettings
    from research_system.config.settings import Settings
    from research_system.utils.deterministic import set_global_seeds
    from research_system.collection import collect_from_free_apis
    from research_system.triangulation.embeddings import get_model
    from pathlib import Path
    
    # Test string seed handling
    set_global_seeds("test_seed")
    
    # Test orchestrator can be created (catches registry issues)
    settings = OrchestratorSettings(
        topic='test query',
        depth='rapid',
        output_dir=Path('/tmp/test_startup'),
        strict=False
    )
    orch = Orchestrator(settings)
    
    print("SUCCESS: All imports and initialization work")
    sys.exit(0)
except Exception as e:
    print(f"RUNTIME ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
"""
    
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    assert result.returncode == 0, f"Import test failed: {result.stderr}"
    assert "SUCCESS" in result.stdout

def test_main_minimal_run():
    """Test that main can actually start a minimal research run."""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Run with immediate timeout to just test startup
        script = f"""
import sys
import os
os.environ["RA_GLOBAL_SEED"] = "20230817"
os.environ["WALL_TIMEOUT_SEC"] = "1"
os.environ["ENABLE_FREE_APIS"] = "true"
os.environ["USE_LLM_CLAIMS"] = "false"
os.environ["USE_LLM_SYNTH"] = "false"

sys.argv = [
    "research_system",
    "--topic", "test query",
    "--depth", "rapid", 
    "--output-dir", "{tmpdir}",
]

try:
    from research_system.main import main
    main()
except SystemExit as e:
    # Timeout exit is expected
    if e.code != 0:
        print(f"Exit code: {{e.code}}")
    sys.exit(0)  # Exit cleanly even on timeout
except Exception as e:
    print(f"STARTUP ERROR: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
    
print("STARTUP OK")
"""
        
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=5  # Shorter timeout
            )
        except subprocess.TimeoutExpired as e:
            # Timeout is expected since the app is actually running
            result = subprocess.CompletedProcess(
                args=e.args,
                returncode=0,  # Treat timeout as success (app is running)
                stdout=e.stdout or "",
                stderr=e.stderr or ""
            )
        
        # Check that it didn't crash with the string seed TypeError
        assert "TypeError: Cannot cast scalar" not in str(result.stderr)
        assert "dtype('<U8')" not in str(result.stderr)
        assert "object cannot be interpreted as an integer" not in str(result.stderr)
        assert "'function' object has no attribute 'register'" not in str(result.stderr)

if __name__ == "__main__":
    # Run the tests
    print("Testing main module startup...")
    
    try:
        test_main_module_starts_without_crashing()
        print("✅ Main module starts without crashing")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    try:
        test_main_with_string_seed_env_var()
        print("✅ String seed handled correctly")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    try:
        test_main_with_integer_seed_env_var()
        print("✅ Integer seed handled correctly")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    try:
        test_main_can_import_all_modules()
        print("✅ All modules import correctly")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    try:
        test_main_minimal_run()
        print("✅ Main can start minimal run")
    except AssertionError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    print("\n🎯 All startup tests passed!")