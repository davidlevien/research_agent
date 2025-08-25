# Python Version Requirements

## Required Python Version: 3.11+

This project requires **Python 3.11 or higher**. Using an older version will result in installation and runtime errors.

## Quick Setup

### Automatic Setup (Recommended)
```bash
# Run the setup script - it will check Python version and install dependencies
./setup_environment.sh
```

### Using Make
```bash
# Install all dependencies
make setup

# Run tests
make test

# Quick verification
make verify
```

### Manual Setup
```bash
# Ensure you're using Python 3.11+
python3.11 --version

# Install dependencies
pip3.11 install -e ".[web,test,dev,monitoring]"
```

## Version Enforcement

The project enforces Python 3.11+ in multiple ways:

1. **pyproject.toml**: `requires-python = ">=3.11"`
2. **Scripts**: All scripts check for Python 3.11+ before running
3. **.python-version**: Tools like pyenv will automatically use 3.11
4. **Makefile**: Automatically detects and uses Python 3.11+
5. **CI/CD**: GitHub Actions uses Python 3.11

## Files Updated for Python 3.11

- `run_research.sh` - Prioritizes Python 3.11+, fails if not found
- `setup_environment.sh` - New setup script that ensures correct Python version
- `.python-version` - Specifies 3.11 for pyenv users
- `Makefile` - All targets use Python 3.11+
- `scripts/*.py` - Shebang lines updated to `#!/usr/bin/env python3.11`

## Troubleshooting

### "Python 3.11+ is required" Error
Install Python 3.11 or higher:
- macOS: `brew install python@3.11`
- Ubuntu/Debian: `sudo apt install python3.11`
- Other: https://www.python.org/downloads/

### "No module named 'bleach'" or similar
Run the setup script: `./setup_environment.sh`

### Tests fail with import errors
Ensure you're using Python 3.11: `python3.11 -m pytest tests/`

## Verifying Your Setup

```bash
# Check Python version
python3.11 --version

# Verify dependencies installed
python3.11 -c "import bleach, psutil; print('✓ Dependencies OK')"

# Run quick tests
make test-fast
```

## For CI/CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) is already configured correctly:
```yaml
- uses: actions/setup-python@v5
  with: { python-version: '3.11' }
```

No changes needed for CI/CD - it already uses Python 3.11.