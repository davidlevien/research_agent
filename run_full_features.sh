#!/usr/bin/env bash
# Run research system with ALL features enabled
# This demonstrates the full PE-grade v8.4 capabilities

set -euo pipefail
IFS=$'\n\t'

# Check Python version
if ! command -v python3.11 &> /dev/null; then
    echo "Error: Python 3.11+ is required"
    exit 1
fi

# Check for .env file
if [ ! -f .env ]; then
    echo "Error: No .env file found."
    echo "Please ensure your .env file exists with your API keys"
    exit 1
fi

# Load environment variables
source .env

# Default topic if not provided
TOPIC="${1:-AI economic impact and job market transformation 2024-2025}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/full_test_$(date +%Y%m%d_%H%M%S)}"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Write run metadata
{
    echo "Run ID: $(date -Iseconds)"
    git rev-parse HEAD 2>/dev/null || echo "Git SHA: unavailable"
    echo "Topic: $TOPIC"
    echo "Python: $(python3.11 --version)"
    echo "Platform: $(uname -s)"
} > "$OUTPUT_DIR/RUN_METADATA.txt"

echo "=================================="
echo "Research System v8.4 - FULL FEATURES"
echo "=================================="
echo "Topic: $TOPIC"
echo "Output: $OUTPUT_DIR"
echo ""
echo "Enabled Features:"
echo "  ✓ All search providers (Tavily, Brave, Serper)"
echo "  ✓ Free APIs (Wikipedia, Wikidata, arXiv, etc.)"
echo "  ✓ LLM-based claims extraction & synthesis"
echo "  ✓ Cross-encoder reranking"
echo "  ✓ Iterative backfill (min 24 cards)"
echo "  ✓ MinHash deduplication"
echo "  ✓ SBERT clustering"
echo "  ✓ DuckDB aggregations"
echo "  ✓ AREX expansion for uncorroborated metrics"
echo "  ✓ Controversy detection"
echo "  ✓ Primary source connectors"
echo "  ✓ Article extraction"
echo "  ✓ Domain balancing (25% cap)"
echo "  ✓ Triangulation enforcement (35% min)"
echo "  ✓ Strict quality gates"
echo ""
echo "v8.4 Fixes Applied:"
echo "  ✓ Enhanced quote extraction (70% coverage)"
echo "  ✓ Anti-bot handling for SEC/WEF/Mastercard"
echo "  ✓ PDF download deduplication"
echo "  ✓ Free API fallbacks (OpenAlex/OECD/Crossref)"
echo "  ✓ Robust report generation"
echo ""
echo "Starting in 3 seconds..."
sleep 3

# Run with all features including v8.4 fixes
# Note: v8.4 fixes (quote extraction, anti-bot, PDF dedup) are built into the code
# and don't require environment variables - they're always active
LOG_LEVEL=INFO \
ENABLE_FREE_APIS=true \
USE_LLM_CLAIMS=true \
USE_LLM_SYNTH=true \
USE_LLM_RERANK=true \
MIN_EVIDENCE_CARDS=24 \
MAX_BACKFILL_ATTEMPTS=3 \
MIN_TRIANGULATION_RATE=0.35 \
MAX_DOMAIN_CONCENTRATION=0.25 \
MIN_CREDIBILITY=0.6 \
ENABLE_PRIMARY_CONNECTORS=true \
ENABLE_EXTRACT=true \
ENABLE_SNAPSHOT=false \
ENABLE_MINHASH_DEDUP=true \
ENABLE_DUCKDB_AGG=true \
ENABLE_SBERT_CLUSTERING=true \
ENABLE_AREX=true \
ENABLE_CONTROVERSY=true \
SEARCH_PROVIDERS="${SEARCH_PROVIDERS:-tavily,brave,serper}" \
CONCURRENCY=16 \
HTTP_TIMEOUT_SECONDS=30 \
WALL_TIMEOUT_SEC=1800 \
PROVIDER_TIMEOUT_SEC=20 \
MAX_COST_USD=2.50 \
python3.11 -m research_system \
    --topic "$TOPIC" \
    --strict \
    --output-dir "$OUTPUT_DIR" \
    --depth deep

echo ""
echo "=================================="
echo "Research Complete!"
echo "=================================="
echo "Results saved to: $OUTPUT_DIR"
echo ""
echo "Generated deliverables:"
ls -la "$OUTPUT_DIR"/*.md "$OUTPUT_DIR"/*.jsonl 2>/dev/null | awk '{print "  - " $NF}'
echo ""
echo "To view the report:"
echo "  cat $OUTPUT_DIR/final_report.md"