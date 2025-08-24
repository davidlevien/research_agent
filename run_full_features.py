#!/usr/bin/env python3.11
import asyncio
import json, os, sys, time
from pathlib import Path
from research_system.orchestrator import Orchestrator, OrchestratorSettings
from research_system.tools.aggregates import source_quality, triangulate_claims, calculate_provider_diversity
from research_system.tools.evidence_io import read_jsonl

# Parse command line arguments
import argparse
parser = argparse.ArgumentParser(description="Research System with All Features")
parser.add_argument("--topic", required=True, help="Research topic")
parser.add_argument("--depth", choices=["rapid", "standard", "deep"], default="deep")
parser.add_argument("--output-dir", default="full_features_output")
parser.add_argument("--strict", action="store_true", help="Enforce all deliverables")
args = parser.parse_args()

# Configure with ALL features
settings = OrchestratorSettings(
    topic=args.topic,
    depth=args.depth,
    output_dir=Path(args.output_dir),
    strict=args.strict,
    max_cost_usd=5.00,  # Increase for deep research
    verbose=True
)

# Add explore_related flag
settings.explore_related = True  # Enable related topics extraction

# Global timeout handler
async def arun():
    orchestrator = Orchestrator(settings)
    if hasattr(orchestrator, 'arun'):
        await orchestrator.arun()
    else:
        # Fallback for sync orchestrator
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, orchestrator.run)

# Run orchestrator with timeout protection
print(f"🔍 Starting research: {args.topic}")
depth_map = {'rapid': 5, 'standard': 8, 'deep': 20}
print(f"📊 Depth: {args.depth} ({depth_map[args.depth]} results per provider)")
print(f"✨ Features: All enhancements active (including related topics)")
print("-" * 60)

wall_timeout = int(os.getenv("WALL_TIMEOUT_SEC", "600"))
t0 = time.time()
try:
    asyncio.run(asyncio.wait_for(arun(), timeout=wall_timeout))
except asyncio.TimeoutError:
    dur = time.time() - t0
    sys.stderr.write(f"\nGLOBAL TIMEOUT after {dur:.1f}s — wrote partial artifacts. Increase WALL_TIMEOUT_SEC.\n")
    # Don't exit, continue with post-processing of partial results
except KeyboardInterrupt:
    sys.stderr.write("\nInterrupted by user.\n")
    sys.exit(1)

# Post-process with additional aggregates
evidence_path = settings.output_dir / "evidence_cards.jsonl"
if evidence_path.exists():
    print("\n" + "="*60)
    print("📈 ENHANCED ANALYTICS")
    print("="*60)
    
    cards = read_jsonl(str(evidence_path))
    
    # Provider diversity analysis
    diversity = calculate_provider_diversity(cards)
    print(f"\n🌐 Provider Diversity:")
    print(f"   - Entropy: {diversity['entropy']:.2f} (normalized: {diversity['normalized_entropy']:.1%})")
    print(f"   - Providers used: {', '.join(diversity['provider_counts'].keys())}")
    for provider, count in diversity['provider_counts'].items():
        print(f"   - {provider}: {count} cards, {diversity['domains_per_provider'][provider]} unique domains")
    
    # Triangulation summary
    triangulation = triangulate_claims(cards)
    triangulated = sum(1 for c in triangulation.values() if c["is_triangulated"])
    print(f"\n🔺 Triangulation Summary:")
    print(f"   - Total claims: {len(triangulation)}")
    print(f"   - Triangulated (2+ sources): {triangulated} ({triangulated*100//max(len(triangulation),1)}%)")
    print(f"   - High confidence (>0.7): {sum(1 for c in triangulation.values() if c['confidence'] > 0.7)}")
    
    # Top sources by quality
    quality = source_quality(cards)
    print(f"\n⭐ Top 5 Sources by Quality:")
    for i, source in enumerate(quality[:5], 1):
        print(f"   {i}. {source['domain']}: {source['avg_credibility']:.2f} credibility, "
              f"{source['corroborated_rate']:.1%} corroboration")
    
    # Check for NPS filtering effectiveness
    nps_cards = [c for c in cards if c.provider == "nps"]
    print(f"\n🏞️ NPS Provider Analysis:")
    print(f"   - NPS results: {len(nps_cards)} (should be 0 for non-park topics)")
    if nps_cards and "park" not in args.topic.lower():
        print(f"   ⚠️ Warning: NPS results found for non-park topic")

print(f"\n✅ Complete! Results in: {settings.output_dir}/")
print(f"📁 Files generated: {', '.join([f.name for f in settings.output_dir.glob('*')])}")