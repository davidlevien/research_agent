#!/usr/bin/env python3.11
"""Benchmark suite for testing research system across multiple topics."""
import subprocess
import json
import pathlib
import sys
import time
from typing import List, Dict, Any

# Benchmark topics covering different domains
BENCHMARK_TOPICS = [
    # Economics
    "global tourism recovery trends 2025",
    
    # Health
    "mRNA vaccine efficacy against new variants",
    
    # Science
    "quantum computing breakthroughs 2024",
    
    # Policy
    "carbon tax implementation effectiveness",
    
    # Technology
    "artificial intelligence regulation frameworks",
    
    # Environment
    "ocean plastic pollution solutions",
    
    # Finance
    "cryptocurrency adoption in emerging markets",
    
    # Energy
    "renewable energy storage technologies",
    
    # Social
    "remote work impact on urban development",
    
    # Industry
    "electric vehicle battery recycling methods"
]


def run_topic(topic: str, output_base: pathlib.Path) -> Dict[str, Any]:
    """Run research on a single topic.
    
    Args:
        topic: Research topic
        output_base: Base output directory
        
    Returns:
        Result dictionary with metrics and status
    """
    # Create safe directory name
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in topic)[:50]
    output_dir = output_base / safe_name
    
    print(f"\n📊 Testing: {topic}")
    print(f"   Output: {output_dir}")
    
    start_time = time.time()
    
    # Run the research
    cmd = [
        "python", "-m", "research_system",
        "--topic", topic,
        "--output-dir", str(output_dir),
        "--strict"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        wall_time = time.time() - start_time
        
        # Load metrics if available
        metrics_path = output_dir / "metrics.json"
        if metrics_path.exists():
            metrics = json.loads(metrics_path.read_text())
            metrics["wall_time_seconds"] = wall_time
        else:
            metrics = {"wall_time_seconds": wall_time}
        
        # Check quality gates
        from quality_gate import check_quality_gates
        errors = check_quality_gates(metrics_path) if metrics_path.exists() else ["No metrics generated"]
        
        return {
            "topic": topic,
            "status": "success" if result.returncode == 0 and not errors else "failed",
            "metrics": metrics,
            "errors": errors,
            "wall_time": wall_time,
            "output_dir": str(output_dir)
        }
        
    except subprocess.TimeoutExpired:
        return {
            "topic": topic,
            "status": "timeout",
            "metrics": {},
            "errors": ["Execution timeout (600s)"],
            "wall_time": 600,
            "output_dir": str(output_dir)
        }
    except Exception as e:
        return {
            "topic": topic,
            "status": "error",
            "metrics": {},
            "errors": [str(e)],
            "wall_time": time.time() - start_time,
            "output_dir": str(output_dir)
        }


def main():
    """Run benchmark suite."""
    # Setup output directory
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_base = pathlib.Path(f"benchmark_{timestamp}")
    output_base.mkdir(exist_ok=True)
    
    print(f"🚀 Running benchmark suite with {len(BENCHMARK_TOPICS)} topics")
    print(f"📁 Output directory: {output_base}")
    
    # Run all topics
    results = []
    for topic in BENCHMARK_TOPICS:
        result = run_topic(topic, output_base)
        results.append(result)
        
        # Print immediate feedback
        if result["status"] == "success":
            print(f"   ✅ PASSED")
        else:
            print(f"   ❌ FAILED: {', '.join(result['errors'][:2])}")
    
    # Generate summary report
    summary = {
        "timestamp": timestamp,
        "total_topics": len(BENCHMARK_TOPICS),
        "passed": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "timeout": sum(1 for r in results if r["status"] == "timeout"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "results": results
    }
    
    # Write summary
    summary_path = output_base / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    
    # Print final summary
    print("\n" + "="*60)
    print("📊 BENCHMARK SUMMARY")
    print("="*60)
    print(f"Total topics: {summary['total_topics']}")
    print(f"✅ Passed: {summary['passed']}")
    print(f"❌ Failed: {summary['failed']}")
    print(f"⏱️ Timeout: {summary['timeout']}")
    print(f"💥 Error: {summary['error']}")
    
    # Calculate aggregate metrics
    all_metrics = [r["metrics"] for r in results if r["status"] == "success" and r["metrics"]]
    if all_metrics:
        print("\n📈 Aggregate Metrics (successful runs):")
        for key in ["quote_coverage", "union_triangulation", "provider_entropy", "top_domain_share"]:
            values = [m.get(key, 0) for m in all_metrics if key in m]
            if values:
                avg = sum(values) / len(values)
                print(f"  {key}: {avg:.3f} (avg)")
    
    print(f"\n📁 Full results: {summary_path}")
    
    # Exit with error if any failed
    if summary["failed"] + summary["timeout"] + summary["error"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()