from prometheus_client import Counter, Histogram

SEARCH_REQUESTS = Counter("search_requests_total", "Search requests", ["provider"])
SEARCH_ERRORS   = Counter("search_errors_total",   "Search errors",   ["provider"])
SEARCH_LATENCY  = Histogram("search_request_seconds", "Search latency", ["provider"])