#!/usr/bin/env python
"""Verify the system is ready for CLI execution"""

import os
import sys
from pathlib import Path

# Set test environment variables
os.environ.update({
    'LLM_PROVIDER': 'openai',
    'OPENAI_API_KEY': 'sk-fake-test',
    'SEARCH_PROVIDERS': 'tavily,brave,serper', 
    'TAVILY_API_KEY': 'fake-tavily',
    'BRAVE_API_KEY': 'fake-brave',
    'SERPERDEV_API_KEY': 'fake-serper'
})

print("1. Testing package imports...")
try:
    from research_system import EvidenceCard, Orchestrator, OrchestratorSettings, Settings
    print("   ✓ Package imports successful")
except ImportError as e:
    print(f"   ✗ Package import failed: {e}")
    sys.exit(1)

print("\n2. Testing tools imports...")
try:
    from research_system.tools import ToolRegistry
    from research_system.tools.registry import Registry, ToolRegistry as TR2
    assert ToolRegistry == Registry  # Should be an alias
    print("   ✓ ToolRegistry available")
except ImportError as e:
    print(f"   ✗ Tools import failed: {e}")
    sys.exit(1)

print("\n3. Testing Settings validation...")
try:
    settings = Settings()
    providers = settings.enabled_providers()
    print(f"   ✓ Settings validated with {len(providers)} providers: {providers}")
except Exception as e:
    print(f"   ✗ Settings failed: {e}")
    sys.exit(1)

print("\n4. Testing orchestrator initialization...")
try:
    orch_settings = OrchestratorSettings(
        topic="Test Topic",
        depth="standard",
        output_dir=Path("test_outputs"),
        strict=True
    )
    orch = Orchestrator(orch_settings)
    print("   ✓ Orchestrator initialized")
except Exception as e:
    print(f"   ✗ Orchestrator failed: {e}")
    sys.exit(1)

print("\n5. Testing registry operations...")
try:
    from research_system.tools.registry import Registry, ToolSpec
    from research_system.tools.search_models import SearchRequest, SearchHit
    
    r = Registry()
    
    # Register a test tool
    def test_search(**kwargs) -> list[SearchHit]:
        return [SearchHit(title="Test", url="http://test.com", provider="test")]
    
    r.register(ToolSpec(
        name="test_search",
        fn=test_search,
        input_model=SearchRequest,
        output_model=list[SearchHit],
        description="Test search"
    ))
    
    # Execute the tool
    result = r.execute("test_search", {"query": "test", "count": 1})
    assert len(result) == 1
    print("   ✓ Registry operations working")
except Exception as e:
    print(f"   ✗ Registry failed: {e}")
    sys.exit(1)

print("\n6. Testing metrics...")
try:
    from research_system.metrics import SEARCH_REQUESTS, SEARCH_ERRORS, SEARCH_LATENCY
    SEARCH_REQUESTS.labels(provider="test").inc()
    print("   ✓ Metrics functional")
except Exception as e:
    print(f"   ✗ Metrics failed: {e}")
    sys.exit(1)

print("\n7. Testing API server import...")
try:
    from research_system.api.server import app
    print("   ✓ API server importable")
except Exception as e:
    print(f"   ✗ API import failed: {e}")
    sys.exit(1)

print("\n✅ All pre-flight checks passed!")
print("\nReady to run:")
print("  research-system --topic 'Test' --depth standard --output-dir outputs --strict")
print("  research-system-api  # for API server")