import time
from collections import defaultdict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 100):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.ip_records = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for docs, redoc, openapi.json to make swagger work
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        
        # In-memory sliding window
        self.ip_records[client_ip] = [t for t in self.ip_records[client_ip] if now - t < 60]
        
        if len(self.ip_records[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429, 
                content={"detail": "Too Many Requests"}
            )
            
        self.ip_records[client_ip].append(now)
        
        response = await call_next(request)
        return response
