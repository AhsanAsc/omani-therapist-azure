from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.logging import configure_logging
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.errors import ErrorMiddleware
from app.routes.http import router as http_router
from app.routes.ws import router as ws_router
from fastapi.staticfiles import StaticFiles

def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Omani Therapist Voice")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_headers=["*"], allow_methods=["*"])
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(ErrorMiddleware)
    app.include_router(http_router, tags=["http"])
    app.include_router(ws_router, tags=["ws"])
    app.mount("/", StaticFiles(directory="public", html=True), name="static")
    return app

app = create_app()
