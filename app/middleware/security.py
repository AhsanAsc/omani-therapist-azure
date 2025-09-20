from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.config import get_settings

SAFE_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "microphone=(self)",
}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if get_settings().SECURE_MODE:
            for k, v in SAFE_HEADERS.items():
                response.headers.setdefault(k, v)
        return response
