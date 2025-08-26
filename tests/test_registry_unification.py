"""
Tests for unified registry usage.
Ensures no duplicate registries and all tools accessible.
"""

import pytest
from research_system.tools.registry import tool_registry, Registry
from research_system.tools.search_registry import register_search_tools


class TestRegistryUnification:
    """Test unified registry implementation."""
    
    def test_global_registry_exists(self):
        """Test that global registry is available."""
        assert tool_registry is not None
        assert isinstance(tool_registry, Registry)
    
    def test_search_tools_register_to_global(self):
        """Test that search tools register to global registry."""
        # Register search tools
        register_search_tools(tool_registry)
        
        # Check that search tools are registered
        assert hasattr(tool_registry, '_tools')
        tools = tool_registry._tools
        
        # Should have search tools registered
        expected_tools = [
            "search_tavily",
            "search_brave", 
            "search_serper",
            "search_serpapi",
            "search_nps"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in tools, f"Tool {tool_name} not found in registry"
    
    def test_no_duplicate_registries_in_orchestrator(self):
        """Test that orchestrator uses global registry, not its own."""
        from research_system.orchestrator import Orchestrator, OrchestratorSettings
        from pathlib import Path
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = OrchestratorSettings(
                topic="test topic",
                depth="rapid",
                output_dir=Path(tmpdir),
                strict=False,
                resume=False,
                verbose=False
            )
            
            # Create orchestrator
            orch = Orchestrator(settings)
            
            # Orchestrator should NOT have its own registry attribute
            assert not hasattr(orch, 'registry'), "Orchestrator should not have its own registry"
    
    def test_registry_tool_execution(self):
        """Test that tools can be executed through the registry."""
        # Register a test tool
        from research_system.tools.registry import ToolSpec
        
        def test_function(x: int, y: int) -> int:
            return x + y
        
        spec = ToolSpec(
            name="test_add",
            fn=test_function,
            description="Test addition function"
        )
        
        # Use a separate registry for this test to avoid polluting global
        test_registry = Registry()
        test_registry.register(spec)
        
        # Execute the tool
        result = test_registry.execute("test_add", {"x": 2, "y": 3})
        assert result == 5
    
    def test_registry_duplicate_prevention(self):
        """Test that registry prevents duplicate tool names."""
        from research_system.tools.registry import ToolSpec
        
        test_registry = Registry()
        
        def dummy_func():
            pass
        
        spec1 = ToolSpec(name="duplicate", fn=dummy_func, description="First")
        spec2 = ToolSpec(name="duplicate", fn=dummy_func, description="Second")
        
        # Register first tool
        test_registry.register(spec1)
        
        # Attempt to register duplicate should raise error
        with pytest.raises(ValueError, match="Duplicate tool name"):
            test_registry.register(spec2)
    
    def test_registry_unknown_tool_error(self):
        """Test that executing unknown tool raises appropriate error."""
        test_registry = Registry()
        
        with pytest.raises(KeyError, match="Unknown tool"):
            test_registry.execute("nonexistent_tool", {})


class TestParseToolsRegistration:
    """Test that parse tools are properly registered."""
    
    def test_parse_tools_available(self):
        """Test that parse tools are instantiated and available."""
        from research_system.tools.parse_tools import ParseTools
        
        # Create instance
        parser = ParseTools()
        
        # Check that parser has expected methods
        assert hasattr(parser, 'extract_text')
        assert hasattr(parser, 'clean_html')
        assert hasattr(parser, 'extract_metadata')
        assert hasattr(parser, 'extract_links')
        assert hasattr(parser, 'extract_images')
    
    def test_parse_tools_registration_to_global(self):
        """Test that parse tools register to global registry."""
        from research_system.tools.parse_tools import ParseTools
        
        # Create instance (which triggers registration)
        parser = ParseTools()
        
        # Check that tools are in global registry
        expected_tools = ["extract_text", "clean_html", "extract_metadata"]
        
        for tool_name in expected_tools:
            assert tool_name in tool_registry._tools, f"Parse tool {tool_name} not in global registry"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])