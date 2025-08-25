#!/bin/bash
# Test CI configuration locally to ensure it will pass
# This simulates the CI environment without needing real API keys

set -e

echo "==================================="
echo "Testing CI Configuration Locally"
echo "==================================="
echo

# Use Python 3.11
if command -v python3.11 &> /dev/null; then
    PYTHON="python3.11"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    echo "Error: Python 3 not found"
    exit 1
fi

echo "Using Python: $($PYTHON --version)"
echo

# Set CI environment variables
export SEARCH_PROVIDERS=""
export ENABLE_FREE_APIS="true"
export OUTPUT_DIR="test_outputs"
export CHECKPOINT_DIR="test_outputs/checkpoints"

# Create test output directory
mkdir -p test_outputs

echo "Environment:"
echo "  SEARCH_PROVIDERS: (empty - no API keys needed)"
echo "  ENABLE_FREE_APIS: true"
echo "  OUTPUT_DIR: test_outputs"
echo

# Check schema can be loaded
echo "Checking schema loading..."
$PYTHON - << 'PY'
try:
    from importlib import resources
    with resources.files("research_system.resources.schemas").joinpath("evidence.schema.json").open() as f:
        import json
        js = json.load(f)
        print("✓ Schema loaded successfully")
except Exception as e:
    print(f"✗ Failed to load schema: {e}")
    exit(1)
PY

# Check config loads without API keys
echo "Checking config loads without API keys..."
$PYTHON -c "
import os
os.environ['SEARCH_PROVIDERS'] = ''
os.environ['ENABLE_FREE_APIS'] = 'true'
from research_system.config import Settings
s = Settings()
print('✓ Config loads without API keys')
"

# Run a subset of tests that should pass
echo
echo "Running subset of tests..."
PYTHONPATH=. $PYTHON -m pytest tests/test_api_compliance.py -q --tb=no

echo
echo "==================================="
echo "✓ CI Configuration Test Passed!"
echo "==================================="
echo
echo "The CI should pass when pushed to GitHub."
echo "Note: Some tests may still fail if they have other issues,"
echo "but the basic configuration is correct."