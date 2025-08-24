from slowapi import Limiter
from slowapi.util import get_remote_address
import os

RPS = float(os.getenv("API_RPS", "2.0"))
BURST = int(os.getenv("API_BURST", "10"))

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{RPS}/second", f"{BURST}/minute"]
)

# Export configured limits for inspection
CONFIGURED_LIMITS = [f"{RPS}/second", f"{BURST}/minute"]