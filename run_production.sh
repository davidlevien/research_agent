#!/bin/bash
# Production run with all features enabled

echo "========================================="
echo "PE-GRADE RESEARCH SYSTEM v5.0"
echo "========================================="
echo ""
echo "Topic: Global Tourism Recovery and Trends 2025"
echo "Depth: Deep (comprehensive analysis)"
echo "Mode: Strict (all quality thresholds enforced)"
echo ""
echo "Features Enabled:"
echo "✓ HTTP Caching"
echo "✓ Content Extraction"
echo "✓ MinHash Deduplication"  
echo "✓ Wayback Snapshots"
echo "✓ Politeness Checks"
echo "✓ AREX Expansion"
echo "✓ Controversy Detection"
echo "✓ Paraphrase Clustering"
echo "✓ Structured Triangulation"
echo "✓ Primary Quote Rescue"
echo "✓ Domain Diversity Enforcement"
echo ""
echo "Starting research run..."
echo "========================================="

# Set all feature flags
export ENABLE_HTTP_CACHE=true
export ENABLE_EXTRACT=true
export ENABLE_MINHASH_DEDUP=true
export ENABLE_SNAPSHOT=true
export ENABLE_POLITENESS=true
export ENABLE_AREX=true
export ENABLE_CONTROVERSY=true
export STRICT=true

# Set higher limits for deep analysis
export MAX_COST_USD=5.00
export FRESHNESS_WINDOW=180

# Run with all features
python3.11 -m research_system \
    --topic "global tourism recovery and trends 2025 Q1 international arrivals receipts UNWTO IATA WTTC" \
    --depth deep \
    --output-dir production_run \
    --strict \
    --verbose

echo ""
echo "========================================="
echo "Research run completed!"
echo "Output files in: production_run/"
echo "========================================="
