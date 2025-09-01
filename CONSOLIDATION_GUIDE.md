# Module Consolidation Guide - v8.25.0

## Overview
This guide documents the architectural consolidation performed to eliminate module duplication and configuration drift in the research system.

## Key Changes

### 1. Unified Configuration (`research_system/config/`)
- **Single source of truth**: All configuration now lives in `config/settings.py`
- **Intent-aware thresholds**: Quality thresholds adapt based on query intent
- **Per-domain headers**: Centralized HTTP headers for API compliance
- **Legacy compatibility**: Old `config.py` and `config_v2.py` forward to new module with deprecation warnings

### 2. Unified Collection (`research_system/collection/`)
- **Merged modules**: Combined `collection.py` and `collection_enhanced.py` into single module
- **Enhanced API**: All collection functions available from `research_system.collection`
- **Legacy forwarders**: Old modules remain as forwarders with deprecation warnings

### 3. Unified Metrics (`research_system/metrics/`)
- **RunMetrics**: Single metrics model for all research runs
- **Adapters**: Convert between legacy and unified formats
- **Monitoring separation**: Prometheus metrics moved to `monitoring_metrics.py`

### 4. Import Guard (`research_system/guard/`)
- **Detect mixed imports**: Warns when legacy and unified modules are used together
- **Health checks**: `check_import_health()` provides diagnostic information
- **Strict enforcement**: Optional strict mode prevents any legacy usage

## Migration Guide

### For Configuration
```python
# Old (deprecated)
from research_system.config import Settings
from research_system.config_v2 import QualityConfigV2

# New (unified)
from research_system.config.settings import Settings, QualityThresholds
```

### For Collection
```python
# Old (deprecated)
from research_system.collection import parallel_provider_search
from research_system.collection_enhanced import collect_from_free_apis

# New (unified)
from research_system.collection import parallel_provider_search, collect_from_free_apis
```

### For Metrics
```python
# Old (deprecated)
from research_system.quality.metrics_v2 import FinalMetrics

# New (unified)
from research_system.metrics import RunMetrics
from research_system.metrics.adapters import from_quality_metrics_v2
```

## Intent-Aware Configuration

### Quality Thresholds by Intent
- **Travel/Tourism**: 30% primary, 25% triangulation, 35% domain cap
- **Stats/Economic**: 60% primary, 40% triangulation, 30% domain cap  
- **Medical/Health**: 65% primary, 50% triangulation, 20% domain cap
- **Finance/Regulatory**: 55% primary, 45% triangulation, 25% domain cap
- **News/Current Events**: 35% primary, 30% triangulation, 35% domain cap

### Domain-Specific Headers
Headers are automatically applied based on domain:
- **Mastercard**: Browser-like headers with referer
- **SEC/EDGAR**: Compliance headers with contact email
- **OECD**: JSON accept headers for API endpoints

## Directory Structure
```
research_system/
├── config/
│   ├── __init__.py
│   └── settings.py         # Single source of truth
├── collection/
│   ├── __init__.py
│   └── enhanced.py         # Unified collection logic
├── metrics/
│   ├── __init__.py
│   ├── run.py              # Unified metrics model
│   └── adapters.py         # Legacy compatibility
├── guard/
│   ├── __init__.py
│   └── import_guard.py     # Import health checks
├── config.py               # Legacy forwarder (deprecated)
├── config_v2.py            # Legacy forwarder (deprecated)
├── collection.py           # Legacy forwarder (deprecated)
├── collection_enhanced.py  # Legacy forwarder (deprecated)
└── monitoring_metrics.py   # Prometheus metrics (renamed)
```

## Testing
Run tests to verify consolidation:
```bash
# Run all tests
pytest tests/ -q --tb=no

# Check import health
python -c "from research_system.guard import check_import_health; print(check_import_health())"

# Verify no legacy imports (strict mode)
python -c "from research_system.guard import enforce_unified_imports; enforce_unified_imports()"
```

## Deprecation Timeline
- **v8.25.0**: Legacy modules emit deprecation warnings
- **v9.0.0**: Legacy forwarders will be removed
- **Migration period**: 3-6 months recommended

## Benefits
1. **Single source of truth**: No more configuration drift
2. **Intent-aware behavior**: Automatic threshold adjustment
3. **Cleaner imports**: One import path per functionality
4. **Better maintainability**: Less code duplication
5. **Type safety**: Unified models with proper types

## Troubleshooting

### Import Errors
If you see `ImportError: cannot import name 'X' from 'research_system.Y'`:
1. Check this migration guide for the new import path
2. Update to use the unified module
3. Run import health check to diagnose issues

### Deprecation Warnings
Warnings like `DeprecationWarning: config_v2 is deprecated` indicate legacy usage:
1. Update imports to use unified modules
2. See migration guide above for specifics
3. Warnings are informational only - code still works

### Mixed Import Detection
If you see `RuntimeError: Legacy and unified modules imported together`:
1. Choose either legacy or unified (prefer unified)
2. Update all imports consistently
3. Use import guard to find problematic imports

## Contact
For questions or issues with the consolidation, please file an issue on GitHub.