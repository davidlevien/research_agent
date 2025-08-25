#!/bin/bash
# Setup script to ensure Python 3.11+ and install all dependencies

set -e  # Exit on error

echo "=== Research System Environment Setup ==="
echo

# Check for Python 3.11+
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    PIP_CMD="pip3.11"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    PIP_CMD="pip3.12"
elif command -v python3 &> /dev/null; then
    # Check if python3 is at least 3.11
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ]; then
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    else
        echo "Error: Python 3.11+ is required (found Python $PYTHON_VERSION)"
        echo "Please install Python 3.11 or higher"
        exit 1
    fi
else
    echo "Error: Python 3.11+ is not installed"
    echo "Please install Python 3.11 or higher from https://www.python.org/downloads/"
    exit 1
fi

echo "✓ Found Python: $($PYTHON_CMD --version)"
echo

# Upgrade pip
echo "Upgrading pip..."
$PYTHON_CMD -m pip install --upgrade pip --quiet

# Install the project with all dependencies
echo "Installing research-system with all dependencies..."
echo "This may take a few minutes..."
$PIP_CMD install -e ".[web,test,dev,monitoring]"

if [ $? -eq 0 ]; then
    echo
    echo "✓ Setup complete! Environment is ready."
    echo
    echo "You can now run:"
    echo "  - Tests: $PYTHON_CMD -m pytest tests/"
    echo "  - Research: ./run_research.sh --topic 'your topic'"
    echo "  - Production: ./run_production.sh"
else
    echo
    echo "✗ Installation failed. Please check the error messages above."
    exit 1
fi