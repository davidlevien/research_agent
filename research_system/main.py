"""
Main entry point for the research system
"""

import asyncio
import click
import structlog
from pathlib import Path
from typing import Optional
import json

from .models import ResearchRequest, ResearchDepth
from .research_engine import ResearchEngine
from .config import Config

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@click.command()
@click.option(
    '--topic',
    '-t',
    required=True,
    help='Research topic'
)
@click.option(
    '--depth',
    '-d',
    type=click.Choice(['rapid', 'standard', 'deep']),
    default='standard',
    help='Research depth'
)
@click.option(
    '--output-dir',
    '-o',
    type=click.Path(),
    default='outputs',
    help='Output directory for all deliverables'
)
@click.option(
    '--config',
    '-c',
    type=click.Path(exists=True),
    help='Configuration file path'
)
@click.option(
    '--strict',
    '-s',
    is_flag=True,
    help='Strict mode - fail if any deliverable cannot be produced'
)
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    help='Verbose output'
)
def main(
    topic: str,
    depth: str,
    output_dir: str,
    config: Optional[str],
    strict: bool,
    verbose: bool
):
    """Research System - Production-ready research automation
    
    Produces 7 deliverables:
    1. plan.md - Research plan
    2. source_strategy.md - Source collection strategy  
    3. acceptance_guardrails.md - Quality acceptance criteria
    4. evidence_cards.jsonl - Collected evidence
    5. source_quality_table.md - Source quality assessment
    6. final_report.md - Final research report
    7. citation_checklist.md - Citation verification checklist
    """
    
    # Set log level
    if verbose:
        structlog.configure(
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    
    logger.info("Starting research system", topic=topic, depth=depth, output_dir=output_dir)
    
    # Run async main
    asyncio.run(async_main(topic, depth, output_dir, config, strict))


async def async_main(
    topic: str,
    depth: str,
    output_dir: str,
    config_path: Optional[str],
    strict_mode: bool
):
    """Async main function"""
    
    try:
        # Load configuration
        if config_path:
            config = Config(config_path)
        else:
            config = Config()
        
        # Create research request
        request = ResearchRequest(
            topic=topic,
            depth=ResearchDepth(depth)
        )
        
        logger.info("Created research request", request_id=request.request_id)
        
        # Initialize research engine
        engine = ResearchEngine(config=config, output_dir=output_dir)
        
        # Execute research and produce all deliverables
        logger.info("Starting research execution")
        report, deliverables = await engine.execute_research(request, strict_mode=strict_mode)
        
        # Print summary
        print_summary(report, deliverables)
        
        logger.info(
            "Research completed successfully",
            request_id=request.request_id,
            evidence_count=len(report.evidence),
            execution_time=report.metrics.execution_time_seconds,
            cost=report.metrics.total_cost_usd,
            deliverables=list(deliverables.keys())
        )
        
    except Exception as e:
        logger.error("Research failed", error=str(e), exc_info=True)
        raise click.ClickException(str(e))


def print_summary(report, deliverables):
    """Print report summary to console"""
    
    click.echo("\n" + "="*60)
    click.echo(f"RESEARCH COMPLETE: {report.topic}")
    click.echo("="*60)
    
    click.echo(f"\n📊 METRICS:")
    click.echo(f"  • Evidence collected: {len(report.evidence)}")
    click.echo(f"  • Unique sources: {report.metrics.unique_domains}")
    click.echo(f"  • Avg credibility: {report.metrics.avg_credibility_score:.0%}")
    click.echo(f"  • Execution time: {report.metrics.execution_time_seconds:.1f}s")
    click.echo(f"  • Total cost: ${report.metrics.total_cost_usd:.2f}")
    
    click.echo(f"\n📝 DELIVERABLES PRODUCED:")
    for name, path in deliverables.items():
        filepath = Path(path)
        size_kb = filepath.stat().st_size / 1024
        click.echo(f"  ✓ {name:<25} {filepath.name:<30} ({size_kb:.1f} KB)")
    
    click.echo(f"\n📁 OUTPUT DIRECTORY: {Path(deliverables['final_report']).parent}")
    
    if report.limitations:
        click.echo(f"\n⚠️  LIMITATIONS:")
        for limitation in report.limitations[:3]:
            click.echo(f"  • {limitation}")
    
    if report.recommendations:
        click.echo(f"\n💡 RECOMMENDATIONS:")
        for rec in report.recommendations[:3]:
            click.echo(f"  • {rec}")
    
    click.echo("\n" + "="*60)
    click.echo("All deliverables have been saved to the output directory.")
    click.echo("="*60 + "\n")


if __name__ == "__main__":
    main()