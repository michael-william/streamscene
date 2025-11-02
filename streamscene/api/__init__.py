"""FastAPI application for REST API endpoints."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI app
api = FastAPI(
    title="StreamScene API",
    version="1.0.0",
    description="REST API for StreamScene device communication and management",
)

# Configure CORS - adjust for production
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@api.get("/api/health")
async def health_check():
    """API health check endpoint."""
    return {
        "status": "ok",
        "service": "streamscene",
        "version": "1.0.0",
    }


# Import and include routers
from .routes import devices

api.include_router(devices.router, prefix="/api/devices", tags=["devices"])
