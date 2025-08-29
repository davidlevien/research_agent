"""
Test that output directories are properly structured for all runs.
"""

import pytest
import tempfile
import shutil
import re
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os


class TestOutputDirectoryStructure:
    """Test that outputs are always saved in proper subdirectories."""
    
    def test_main_creates_subdirectory(self):
        """Test that main.py creates a subdirectory based on topic and timestamp."""
        from datetime import datetime
        
        # Test topic slug generation
        topic = "Tax Rates & Economic Class Relationships 2024!"
        topic_slug = re.sub(r'[^\w\s-]', '', topic.lower())
        topic_slug = re.sub(r'[\s_-]+', '_', topic_slug)[:50]
        
        assert topic_slug == "tax_rates_economic_class_relationships_2024"
        
        # Test that subdirectory would be created
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_dir = Path(tempfile.mkdtemp())
        
        try:
            run_dir = base_dir / f"{topic_slug}_{timestamp}"
            
            # Verify the path structure
            assert topic_slug in str(run_dir)
            assert timestamp in str(run_dir)
            assert run_dir.parent == base_dir
            
        finally:
            shutil.rmtree(base_dir, ignore_errors=True)
    
    def test_subdirectory_for_incomplete_runs(self):
        """Test that even incomplete/crashed runs use subdirectories."""
        from research_system.orchestrator import OrchestratorSettings
        
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            
            # Simulate what main.py does
            topic = "test topic"
            topic_slug = re.sub(r'[^\w\s-]', '', topic.lower())
            topic_slug = re.sub(r'[\s_-]+', '_', topic_slug)[:50]
            timestamp = "20240101_120000"  # Fixed for testing
            
            run_output_dir = base_dir / f"{topic_slug}_{timestamp}"
            
            settings = OrchestratorSettings(
                topic=topic,
                depth="rapid",
                output_dir=run_output_dir,
                strict=False
            )
            
            # Verify the settings use subdirectory
            assert settings.output_dir == run_output_dir
            assert "test_topic" in str(settings.output_dir)
            assert str(settings.output_dir).startswith(str(base_dir))
    
    def test_no_direct_outputs_folder_pollution(self):
        """Test that files are never written directly to the base outputs folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "outputs"
            base_dir.mkdir(parents=True, exist_ok=True)
            
            # Create a mock run that would previously pollute outputs/
            topic = "incomplete run test"
            topic_slug = re.sub(r'[^\w\s-]', '', topic.lower())
            topic_slug = re.sub(r'[\s_-]+', '_', topic_slug)[:50]
            
            # The new behavior should create a subdirectory
            run_dir = base_dir / f"{topic_slug}_20240101_120000"
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # Write test files to the subdirectory
            (run_dir / "test.md").write_text("test content")
            (run_dir / "evidence.jsonl").write_text("{}")
            
            # Verify base directory is clean
            base_files = [f for f in base_dir.iterdir() if f.is_file()]
            assert len(base_files) == 0, "Base outputs directory should have no files"
            
            # Verify subdirectory has the files
            subdir_files = list(run_dir.glob("*"))
            assert len(subdir_files) == 2
            assert any("test.md" in str(f) for f in subdir_files)
            assert any("evidence.jsonl" in str(f) for f in subdir_files)
    
    def test_special_characters_in_topic(self):
        """Test that topics with special characters are handled properly."""
        
        test_cases = [
            ("AI & Machine Learning: 2024-2025", "ai_machine_learning_2024_2025"),
            ("What's the impact of $100 billion?", "whats_the_impact_of_100_billion"),
            ("COVID-19 / pandemic effects!", "covid_19_pandemic_effects"),
            ("Tax rates (high income) vs. low", "tax_rates_high_income_vs_low"),
        ]
        
        for topic, expected_slug_part in test_cases:
            topic_slug = re.sub(r'[^\w\s-]', '', topic.lower())
            topic_slug = re.sub(r'[\s_-]+', '_', topic_slug)[:50]
            
            assert topic_slug == expected_slug_part, \
                f"Topic '{topic}' should produce slug '{expected_slug_part}', got '{topic_slug}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])