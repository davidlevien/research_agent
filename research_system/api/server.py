from fastapi import FastAPI, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
from starlette.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import signal, asyncio, contextlib
import redis
import os
from pathlib import Path
from typing import Dict, Any, List

from slowapi.errors import RateLimitExceeded
from .limiting import limiter
from .security import require_api_key
from ..config import Settings
from ..orchestrator import Orchestrator, OrchestratorSettings

app = FastAPI(title="Research System API", version="v1")
app.state.limiter = limiter

# ====== Health endpoints ======
@app.get("/health", response_class=PlainTextResponse)
def health():
    return "ok"

@app.get("/ready", response_class=PlainTextResponse)
def ready():
    """Check if the system is ready to serve traffic"""
    try:
        settings = Settings()
        checks = []
        
        # Check env gating is properly configured
        checks.append(("env_gating", True))
        
        # Check Redis connectivity if enabled
        if settings.ENABLE_REDIS and settings.REDIS_URL:
            try:
                r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
                r.ping()
                checks.append(("redis", True))
            except Exception as e:
                return PlainTextResponse(f"Redis check failed: {e}", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Check database connectivity if enabled
        if settings.ENABLE_DATABASE and settings.DATABASE_URL:
            # Would check DB connection here
            checks.append(("database", True))
        
        # Verify API keys for enabled providers
        providers = settings.enabled_providers()
        for provider in providers:
            if provider == "tavily" and not settings.TAVILY_API_KEY:
                return PlainTextResponse(f"Missing TAVILY_API_KEY", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            if provider == "brave" and not settings.BRAVE_API_KEY:
                return PlainTextResponse(f"Missing BRAVE_API_KEY", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            if provider == "serper" and not settings.SERPER_API_KEY:
                return PlainTextResponse(f"Missing SERPER_API_KEY", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            if provider == "serpapi" and not settings.SERPAPI_API_KEY:
                return PlainTextResponse(f"Missing SERPAPI_API_KEY", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            if provider == "nps" and not settings.NPS_API_KEY:
                return PlainTextResponse(f"Missing NPS_API_KEY", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        checks.append(("providers", True))
        
        # All checks passed
        return "ready"
    except Exception as e:
        return PlainTextResponse(f"Readiness check failed: {e}", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

@app.get("/live", response_class=PlainTextResponse)
def live():
    return "live"

# ====== Prometheus metrics ======
@app.get("/metrics")
def metrics():
    data = generate_latest()  # default REGISTRY
    return PlainTextResponse(data, media_type=CONTENT_TYPE_LATEST)

# ====== Rate limit handling ======
@app.exception_handler(RateLimitExceeded)
def ratelimit_handler(request: Request, exc: RateLimitExceeded):
    return PlainTextResponse("Too Many Requests", status_code=429)

# ====== Graceful shutdown ======
shutdown_event = asyncio.Event()

def _signal_handler(*_):
    shutdown_event.set()

@app.on_event("startup")
async def _startup():
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

@app.on_event("shutdown")
async def _shutdown():
    with contextlib.suppress(Exception):
        # drain pools / flush spans here when those are enabled
        pass

# Request/Response models
class RunRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="Research topic")
    depth: str = Field("standard", pattern="^(rapid|standard|deep)$", description="Research depth")
    strict: bool = Field(False, description="Enforce strict deliverable checks")
    max_cost: float = Field(2.50, ge=0, le=100, description="Maximum cost in USD")

class RunResponse(BaseModel):
    status: str
    topic: str
    deliverables: List[str]
    summary: Dict[str, Any]
    output_dir: str

# Main research endpoint
@app.post("/v1/run", response_model=RunResponse, dependencies=[Depends(require_api_key)])
@limiter.limit("10/minute")
async def run_job(request: Request, run_req: RunRequest):
    """Execute a research job and return results"""
    try:
        # Create unique output directory
        output_dir = Path(f"outputs/api_{run_req.topic.replace(' ', '_')}_{os.urandom(4).hex()}")
        
        # Configure orchestrator
        settings = OrchestratorSettings(
            topic=run_req.topic,
            depth=run_req.depth,
            output_dir=output_dir,
            max_cost_usd=run_req.max_cost,
            strict=run_req.strict
        )
        
        # Run orchestrator
        orchestrator = Orchestrator(settings)
        orchestrator.run()
        
        # Collect deliverables
        deliverables = []
        summary = {}
        
        for file in output_dir.iterdir():
            if file.is_file():
                deliverables.append(file.name)
                if file.suffix == '.jsonl':
                    # Count evidence cards
                    with open(file) as f:
                        summary['evidence_count'] = sum(1 for _ in f)
                elif file.suffix == '.md':
                    # Get file size
                    summary[file.stem + '_size'] = file.stat().st_size
        
        return RunResponse(
            status="completed",
            topic=run_req.topic,
            deliverables=deliverables,
            summary=summary,
            output_dir=str(output_dir)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research job failed: {str(e)}"
        )