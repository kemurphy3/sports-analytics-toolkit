#!/usr/bin/env python3
"""
Main FastAPI application for multi-tenant fitness platform
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .auth import router as auth_router
from .sources import router as sources_router
from .workouts import router as workouts_router
from .biometrics import router as biometrics_router
from .analysis import router as analysis_router
from .chat import router as chat_router
from .export import router as export_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware to extract and validate tenant information"""
    
    async def dispatch(self, request: Request, call_next):
        # Extract tenant from subdomain, header, or JWT token
        tenant_id = self._extract_tenant_id(request)
        if tenant_id:
            request.state.tenant_id = tenant_id
        
        response = await call_next(request)
        return response
    
    def _extract_tenant_id(self, request: Request) -> str:
        """Extract tenant ID from various sources"""
        # Check subdomain first
        host = request.headers.get("host", "")
        if "." in host:
            subdomain = host.split(".")[0]
            if subdomain not in ["www", "api", "localhost"]:
                return subdomain
        
        # Check custom header
        tenant_header = request.headers.get("x-tenant-id")
        if tenant_header:
            return tenant_header
        
        # Check JWT token (will be validated in auth middleware)
        return None

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for rate limiting"""
    
    async def dispatch(self, request: Request, call_next):
        # TODO: Implement Redis-based rate limiting
        # For now, just pass through
        response = await call_next(request)
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting multi-tenant fitness platform API")
    
    # Initialize database connections
    # Initialize Redis connections
    # Initialize background workers
    
    yield
    
    # Shutdown
    logger.info("Shutting down multi-tenant fitness platform API")
    # Close database connections
    # Close Redis connections
    # Stop background workers

# Create FastAPI app
app = FastAPI(
    title="Multi-Tenant Fitness Platform API",
    description="API for multi-tenant fitness data platform with OAuth integrations",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "change-me"))
app.add_middleware(TenantMiddleware)
app.add_middleware(RateLimitMiddleware)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "request_id": request.headers.get("x-request-id", "unknown")
        }
    )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
    }

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(sources_router, prefix="/api/sources", tags=["Data Sources"])
app.include_router(workouts_router, prefix="/api/workouts", tags=["Workouts"])
app.include_router(biometrics_router, prefix="/api/biometrics", tags=["Biometrics"])
app.include_router(analysis_router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(chat_router, prefix="/api/chat", tags=["AI Chat"])
app.include_router(export_router, prefix="/api/export", tags=["Data Export"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
