"""
Main FastAPI application entry point for the Replenix backend.

This module initializes the FastAPI server, configures CORS middleware,
sets up global exception handlers, and registers the Prometheus metrics
instrumentator for observability.
"""

from prometheus_fastapi_instrumentator import Instrumentator
from core.security import verify_api_key
from api.routers.legacy_routes import router as legacy_router
from core.rate_limiter import RateLimitMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request, Depends
import os
import logging
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis

import sys
try:
    import rl.dqn as dqn_module
    sys.modules['dqn'] = dqn_module
except ImportError:
    pass

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Inventory Optimization API",
    description="REST endpoints for DQN-based inventory optimization",
    version="1.0.0",
    debug=False,
)


_CORS_ORIGINS_RAW = os.environ.get("CORS_ORIGINS")
if not _CORS_ORIGINS_RAW:
    raise ValueError("CORS_ORIGINS environment variable is required.")
_CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization",
                   "X-Request-ID", "X-API-Key"],
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=100)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for the FastAPI application.

    Logs unhandled exceptions with full tracebacks and returns a generic 500
    Internal Server Error response to prevent leaking sensitive information.

    Args:
        request: The incoming FastAPI request.
        exc: The unhandled exception.

    Returns:
        JSONResponse: A generic 500 error response.
    """
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


class LoggingRedisBackend(RedisBackend):
    async def get_with_ttl(self, key: str) -> tuple[int, bytes | None]:
        ttl, val = await super().get_with_ttl(key)
        if val is not None:
            print(f"[CACHE HIT] Key: {key}", flush=True)
        else:
            print(f"[CACHE MISS] Key: {key}", flush=True)
        return ttl, val

def custom_key_builder(
    func,
    namespace: str = "",
    request: Request = None,
    response: "Response" = None,
    *args,
    **kwargs,
):
    from fastapi_cache import FastAPICache
    import hashlib
    from sqlalchemy.orm import Session
    from fastapi import Response
    
    prefix = FastAPICache.get_prefix()
    
    # fastapi_cache passes the route's kwargs as a keyword argument named 'kwargs'
    route_kwargs = kwargs.get("kwargs", {})
    if isinstance(route_kwargs, dict):
        route_kwargs = {k: str(v) for k, v in route_kwargs.items() if k != "db" and not isinstance(v, Session)}
    
    # Same for args
    route_args = kwargs.get("args", args)
    
    cache_key = f"{prefix}:{namespace}:{func.__module__}:{func.__name__}:{route_args}:{route_kwargs}"
    return hashlib.md5(cache_key.encode()).hexdigest()

# ── Prometheus metrics — auto-instruments all routes, exposes /metrics ──
app.include_router(legacy_router, dependencies=[Depends(verify_api_key)])

@app.on_event("startup")
async def startup():
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    try:
        redis = aioredis.from_url(redis_url, encoding="utf8", decode_responses=False)
        FastAPICache.init(LoggingRedisBackend(redis), prefix="fastapi-cache", key_builder=custom_key_builder)
        print("FastAPI-Cache initialized with LoggingRedisBackend.", flush=True)
    except Exception as e:
        print(f"Failed to initialize Redis cache: {e}", flush=True)

# ── Prometheus metrics — auto-instruments all routes, exposes /metrics ──
for route in app.routes:
    if not hasattr(route, "path"):
        route.path = ""

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_round_latency_decimals=True,
    excluded_handlers=["/metrics"],
).instrument(app).expose(app, include_in_schema=False)
