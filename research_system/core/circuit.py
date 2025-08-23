from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

def external_call_guard(max_attempts=4):
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type((TimeoutError, ConnectionError))
    )