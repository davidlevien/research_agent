#!/bin/bash
# Research Agent Runner Script

# Check if Python 3 is available
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
else
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Run the research system with provided arguments
$PYTHON_CMD -m research_system "$@"