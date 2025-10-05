"""
Main FastAPI application entry point.
Production-ready with proper error handling, logging, and middleware.
"""
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uvicorn

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.config.settings import get_settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import ChartAIException
from app.routes.rag_routes import router as rag_router
from app.routes.chart_routes import router as chart_router
from app.services.rag_service import initialize_rag_service

# Initialize settings and logging
settings = get_settings()
setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file,
    log_to_console=True
)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("=" * 80)
    logger.info("Starting ChartAI Application")
    logger.info("=" * 80)
    
    try:
        # Create necessary directories
        Path(settings.temp_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.metadata_dir).mkdir(parents=True, exist_ok=True)
        Path(settings.chroma_persist_directory).mkdir(parents=True, exist_ok=True)
        logger.info("Created necessary directories")
        
        # Initialize RAG service
        initialize_rag_service()
        logger.info("RAG service initialized")
        
        logger.info("Application startup complete")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        raise
    
    yield
    
    # Shutdown
    logger.info("=" * 80)
    logger.info("Shutting down ChartAI Application")
    logger.info("=" * 80)


# Create FastAPI app
app = FastAPI(
    title="ChartAI Backend",
    description="AI-Powered Data Extraction and RAG System for PDFs",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing."""
    import time
    
    # Generate request ID
    request_id = request.headers.get("X-Request-ID", str(id(request)))
    
    # Log request
    logger.info(
        f"Request started: {request.method} {request.url.path} "
        f"[{request_id}]"
    )
    
    start_time = time.time()
    
    try:
        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"[{request_id}] - {response.status_code} in {duration:.2f}ms"
        )
        
        return response
        
    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(
            f"Request failed: {request.method} {request.url.path} "
            f"[{request_id}] - Error after {duration:.2f}ms: {str(e)}"
        )
        raise


# Global exception handler
@app.exception_handler(ChartAIException)
async def chartai_exception_handler(request: Request, exc: ChartAIException):
    """Handle custom ChartAI exceptions."""
    logger.error(f"ChartAI exception: {exc.error_code} - {exc.message}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=exc.to_dict()
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred",
            "details": str(exc) if settings.debug else None
        }
    )


# Include routers
app.include_router(rag_router)
app.include_router(chart_router)
# Root endpoint
@app.get("/api", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "message": "ChartAI Backend API",
        "version": "2.0.0",
        "docs": "/api/docs",
        "health": "/api/rag/health"
    }


# Serve static files (frontend) if available
# Path structure: python_backend/app/main.py -> go up 2 levels to reach client/
client_path = Path(__file__).parent.parent.parent / "client"

if client_path.exists() and client_path.is_dir():
    # Mount static files at root AFTER API routes
    # This ensures API routes take precedence
    app.mount("/", StaticFiles(directory=str(client_path), html=True), name="static")
    logger.info(f"Serving static files from: {client_path}")
    logger.info(f"Frontend available at: http://{settings.host}:{settings.port}/")
else:
    logger.warning(f"Client directory not found: {client_path}")
    logger.info(f"Expected client directory at: {client_path.absolute()}")


def main():
    """Run the application."""
    logger.info(f"Starting server on {settings.host}:{settings.port}")
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()