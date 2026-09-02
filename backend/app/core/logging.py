"""Centralized logging: a consistent format for every module's logger, plus a
request-logging middleware. Replaces the previous state of ad hoc
`logging.getLogger(__name__)` calls with no shared configuration.
"""

import logging
import time

from fastapi import Request

request_logger = logging.getLogger("app.request")


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    request_logger.info(
        "%s %s -> %s (%.1fms)",
        request.method, request.url.path, response.status_code, duration_ms,
    )
    return response
