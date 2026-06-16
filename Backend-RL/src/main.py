from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import Request
import os
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Inventory Optimization API",
    description="REST endpoints for DQN-based inventory optimization",
    version="1.0.0",
    debug=False,
)

_CORS_ORIGINS_RAW = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
_CORS_ORIGINS = [o.strip() for o in _CORS_ORIGINS_RAW.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

from api.routers.legacy_routes import router as legacy_router

app.include_router(legacy_router)
