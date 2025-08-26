import argparse
from pathlib import Path
from research_system.config import Settings
from research_system.orchestrator import Orchestrator, OrchestratorSettings
import logging, os, sys, time, asyncio
import structlog
import random
import numpy as np

def _init_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level)
    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
        cache_logger_on_first_use=True,
    )

def main():
    # Set seeds for deterministic behavior
    random.seed(0)
    np.random.seed(0)
    os.environ["PYTHONHASHSEED"] = "0"
    
    _init_logging()
    p = argparse.ArgumentParser(prog="research-system", description="Research & Citations")
    p.add_argument("--topic", required=True, help="Research topic (required)")
    p.add_argument("--depth", choices=["rapid","standard","deep"], default="standard")
    p.add_argument("--output-dir", default="outputs")
    p.add_argument("--max-cost", type=float, default=None, help="Maximum cost in USD (defaults to MAX_COST_USD from settings)")
    p.add_argument("--strict", action="store_true", help="Enforce strict deliverable checks")
    p.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    p.add_argument("--verbose", action="store_true", help="Verbose output")
    args = p.parse_args()

    # Validate env per blueprint (provider gating)
    settings = Settings()  # instantiation triggers validators
    
    # max_cost is now managed globally via Settings.MAX_COST_USD
    if args.max_cost is not None:
        # Override the global setting if provided via CLI
        os.environ["MAX_COST_USD"] = str(args.max_cost)
        # Re-instantiate settings to pick up the new value
        settings = Settings()

    s = OrchestratorSettings(
        topic=args.topic,
        depth=args.depth,
        output_dir=Path(args.output_dir),
        strict=args.strict,
        resume=args.resume,
        verbose=args.verbose,
    )
    
    # Global timeout handler
    async def arun():
        orchestrator = Orchestrator(s)
        if hasattr(orchestrator, 'arun'):
            await orchestrator.arun()
        else:
            # Fallback for sync orchestrator
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, orchestrator.run)
    
    wall_timeout = int(os.getenv("WALL_TIMEOUT_SEC", "600"))
    t0 = time.time()
    try:
        asyncio.run(asyncio.wait_for(arun(), timeout=wall_timeout))
    except asyncio.TimeoutError:
        dur = time.time() - t0
        sys.stderr.write(f"\nGLOBAL TIMEOUT after {dur:.1f}s — wrote partial artifacts. Increase WALL_TIMEOUT_SEC.\n")
        sys.exit(2)
    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by user.\n")
        sys.exit(1)