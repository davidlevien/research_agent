import os
import yaml
import functools

@functools.lru_cache(maxsize=1)
def load_guardrails():
    p = os.getenv("RA_GUARDRAILS", "config/guardrails.yml")
    with open(p, "r") as f:
        return yaml.safe_load(f) or {}