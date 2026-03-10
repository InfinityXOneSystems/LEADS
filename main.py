"""LEADS System - Main Application Entry Point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.webhooks import webhook_router
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)

app = FastAPI(
    title="LEADS System",
    description="Lead normalization, validation, ingestion, and scoring system for XPS Intelligence",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(webhook_router)


@app.get("/")
async def root():
    return {
        "service": "LEADS System",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting LEADS System on {settings.app_host}:{settings.app_port}")
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
