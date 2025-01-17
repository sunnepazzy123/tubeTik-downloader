from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Middleware to add support for X-Forwarded-Proto header (if behind a proxy)
class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # If request came via HTTP, redirect to HTTPS
        if request.headers.get("x-forwarded-proto") == "http":
            url = f"https://{request.headers['host']}{request.url.path}"
            return RedirectResponse(url)
        response = await call_next(request)
        return response


def setUpMiddlewares(app: FastAPI):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Or specify your frontend URL
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
         )
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["staging-vhaye.com", "www.staging-vhaye.com", "localhost"])
        app.add_middleware(HTTPSRedirectMiddleware)
        
        