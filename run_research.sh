#!/bin/bash
# Research Agent Runner Script

# Check if Python 3.11+ is available (required by project)
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3 &> /dev/null; then
    # Check if python3 is at least 3.11
    PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc) -eq 1 ]]; then
        PYTHON_CMD="python3"
    else
        echo "Error: Python 3.11+ is required (found Python $PYTHON_VERSION)"
        echo "Please install Python 3.11 or higher"
        exit 1
    fi
else
    echo "Error: Python 3.11+ is not installed"
    exit 1
fi

# Run the research system with provided arguments
$PYTHON_CMD -m research_system "$@"