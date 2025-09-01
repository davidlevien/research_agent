import argparse
from pathlib import Path
from research_system.config.settings import Settings
from research_system.orchestrator import Orchestrator, OrchestratorSettings
from research_system.utils.deterministic import set_global_seeds
from research_system.utils.datetime_safe import safe_strftime
import logging, os, sys, time, asyncio
import structlog

def _init_logging():
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=level)
    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.TimeStamper(fmt="iso"), structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level, logging.INFO)),
        cache_logger_on_first_use=True,
    )

def main():
    # Set seeds for deterministic behavior using our centralized seeding module
    set_global_seeds(os.environ.get("RA_GLOBAL_SEED", "20230817"))
    
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
    
    # Create a proper subdirectory for this run
    import re
    
    # Generate subdirectory name from topic and timestamp
    topic_slug = re.sub(r'[^\w\s-]', '', args.topic.lower())
    topic_slug = re.sub(r'[\s_-]+', '_', topic_slug)[:50]  # Limit length
    timestamp = safe_strftime(time.time(), "%Y%m%d_%H%M%S")
    
    # Create subdirectory path
    base_output_dir = Path(args.output_dir)
    run_output_dir = base_output_dir / f"{topic_slug}_{timestamp}"
    
    # Ensure base directory exists
    base_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Log where outputs will be saved
    print(f"Output directory: {run_output_dir}", file=sys.stderr)
    
    s = OrchestratorSettings(
        topic=args.topic,
        depth=args.depth,
        output_dir=run_output_dir,  # Use the subdirectory
        strict=args.strict,
        resume=args.resume,
        verbose=args.verbose,
        max_cost_usd=args.max_cost,  # Will use Settings.MAX_COST_USD if None
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
    except RuntimeError as e:
        # Handle strict mode degradation - report was generated but quality gates failed
        if "quality gates not met" in str(e):
            sys.stderr.write(f"\nStrict mode: {e}\n")
            sys.exit(1)  # Exit with error code but report was generated
        else:
            raise  # Re-raise other RuntimeErrors
    except SystemExit:
        raise  # Let SystemExit pass through
    except Exception as e:
        sys.stderr.write(f"\nUnexpected error: {e}\n")
        sys.exit(1)