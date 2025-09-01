#!/bin/bash
# Research Agent Runner Script

# v8.22.0: Make the wrapper work from anywhere
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "$SCRIPT_DIR")"
cd "$REPO_ROOT"

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