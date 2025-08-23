import argparse
from pathlib import Path
from research_system.config import Settings
from research_system.orchestrator import Orchestrator, OrchestratorSettings
import logging, os
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
    
    # Use settings default if max-cost not provided
    max_cost = args.max_cost if args.max_cost is not None else settings.MAX_COST_USD

    s = OrchestratorSettings(
        topic=args.topic,
        depth=args.depth,
        output_dir=Path(args.output_dir),
        max_cost_usd=max_cost,
        strict=args.strict,
        resume=args.resume,
        verbose=args.verbose,
    )
    Orchestrator(s).run()