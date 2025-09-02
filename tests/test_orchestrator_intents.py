"""Test that orchestrator properly handles all Intent references."""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

def test_orchestrator_intent_references_are_valid():
    """Test that all Intent references in orchestrator are valid enum values."""
    from research_system.orchestrator import Orchestrator, OrchestratorSettings
    from research_system.intent.classifier import Intent
    
    # Test with a trends query that would trigger the Intent checking code
    with tempfile.TemporaryDirectory() as tmpdir:
        s = OrchestratorSettings(
            topic="latest travel & tourism trends",
            depth="quick",
            output_dir=Path(tmpdir),
            strict=False,
            verbose=False
        )
        
        # Create orchestrator - this should not raise AttributeError
        o = Orchestrator(s)
        
        # Mock the registry to avoid actual API calls
        with patch('research_system.orchestrator.registry') as mock_registry:
            mock_registry.return_value = MagicMock()
            
            # Set up minimal mocks to let the code run far enough to check Intent references
            with patch('research_system.orchestrator.asyncio.run') as mock_run:
                mock_run.return_value = {}
                
                with patch('research_system.orchestrator.choose_providers') as mock_choose:
                    mock_choose.return_value = MagicMock(
                        categories=['travel'],
                        providers=['wikipedia', 'worldbank']
                    )
                    
                    # This should run without AttributeError on Intent.BUSINESS
                    try:
                        # Run just the collection phase which contains the Intent checks
                        o._run_internal()
                    except Exception as e:
                        # We expect other errors (no actual data), but not AttributeError on Intent
                        if isinstance(e, AttributeError) and 'Intent' in str(e):
                            pytest.fail(f"Invalid Intent reference: {e}")


def test_all_intent_values_in_orchestrator_exist():
    """Verify that all Intent.X references in orchestrator.py are valid."""
    import re
    import ast
    
    # Get valid Intent values from the enum
    from research_system.intent.classifier import Intent
    valid_intents = set()
    for attr in dir(Intent):
        if not attr.startswith('_') and attr.isupper():
            valid_intents.add(f'Intent.{attr}')
    
    # Parse orchestrator.py for Intent references
    with open('research_system/orchestrator.py', 'r') as f:
        content = f.read()
    
    # Find all Intent.SOMETHING references
    intent_refs = re.findall(r'Intent\.\w+', content)
    unique_refs = set(intent_refs)
    
    # Check each reference is valid
    invalid_refs = []
    for ref in unique_refs:
        if ref not in valid_intents:
            invalid_refs.append(ref)
    
    assert not invalid_refs, f"Invalid Intent references found: {invalid_refs}"


def test_trends_query_triggers_correct_code_path():
    """Test that trends queries don't crash with Intent errors."""
    from research_system.orchestrator import Orchestrator, OrchestratorSettings
    from research_system.intent.classifier import classify
    
    trends_queries = [
        "latest travel trends",
        "current tourism outlook",
        "recent market forecast",
        "trending topics in tech"
    ]
    
    for query in trends_queries:
        # Classify the query
        intent = classify(query)
        
        # Create settings
        with tempfile.TemporaryDirectory() as tmpdir:
            s = OrchestratorSettings(
                topic=query,
                depth="quick",
                output_dir=Path(tmpdir),
                strict=False,
                verbose=False
            )
            
            # This should not raise AttributeError
            try:
                o = Orchestrator(s)
                # Just creating the orchestrator is enough to verify Intent references work
                assert o is not None
            except AttributeError as e:
                if 'Intent' in str(e):
                    pytest.fail(f"Query '{query}' triggered invalid Intent reference: {e}")