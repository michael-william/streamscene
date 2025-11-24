"""FastAPI application for REST API endpoints."""

import uuid
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import reflex as rx

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


# Custom upload endpoint - bypasses Reflex's broken upload system
@api.post("/api/custom-upload")
async def custom_upload(
    file: UploadFile = File(...),
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    Custom file upload endpoint that bypasses Reflex's upload handler system.

    This endpoint was created to work around Reflex's upload handler path resolution
    issues with nested state classes. It provides a direct FastAPI POST endpoint for
    file uploads.

    Args:
        file: The uploaded file (UploadFile instance)
        x_user_id: Optional user ID from header for logging/auth

    Returns:
        JSONResponse with success status, filename, and URL
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read and validate file size (5MB max)
        contents = await file.read()
        if len(contents) > 5_000_000:
            raise HTTPException(status_code=400, detail="File too large (max 5MB)")

        # Save to both public (for persistence) and build (for immediate access)
        public_dir = Path("/root/streamscene/.web/public/uploads")
        build_dir = Path("/root/streamscene/.web/build/client/uploads")
        public_dir.mkdir(parents=True, exist_ok=True)
        build_dir.mkdir(parents=True, exist_ok=True)

        # Generate safe unique filename (extension for filesystem)
        file_extension = Path(file.filename).suffix if file.filename else '.jpg'
        file_uuid = str(uuid.uuid4())
        safe_filename = f"{file_uuid}{file_extension}"

        # Save to both locations
        public_path = public_dir / safe_filename
        build_path = build_dir / safe_filename

        with public_path.open("wb") as buffer:
            buffer.write(contents)
        with build_path.open("wb") as buffer:
            buffer.write(contents)

        # Construct URL without extension (Nginx blocks .jpg in /api/ routes)
        file_url = f"/api/_upload/{file_uuid}"

        print(f"[CUSTOM_UPLOAD] Success: {safe_filename} ({len(contents)} bytes)")
        if x_user_id:
            print(f"[CUSTOM_UPLOAD] User ID: {x_user_id}")

        return JSONResponse({
            "success": True,
            "filename": safe_filename,
            "url": file_url,
            "size": len(contents)
        })

    except HTTPException:
        raise
    except Exception as e:
        print(f"[CUSTOM_UPLOAD] Error: {e}")
        return JSONResponse(
            {"success": False, "error": str(e)},
            status_code=500
        )


# Serve uploaded files directly from backend (avoids sirv caching issues)
@api.get("/api/_upload/{file_uuid}")
async def serve_upload(file_uuid: str):
    """
    Serve uploaded files directly from the backend.

    This endpoint serves files immediately after upload, avoiding the issue where
    sirv (frontend server) only serves files that existed when it started.
    Uses /api/ prefix so Nginx routes it to backend automatically.

    Note: file_uuid is passed without extension (Nginx blocks .jpg in /api/ routes).
    We try common image extensions to find the actual file.
    """
    # Try common image extensions
    extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']

    for ext in extensions:
        filename = f"{file_uuid}{ext}"
        # Try build directory first (for immediate access)
        build_path = Path(f"/root/streamscene/.web/build/client/uploads/{filename}")
        public_path = Path(f"/root/streamscene/.web/public/uploads/{filename}")

        # Check build directory first, then public as fallback
        if build_path.exists():
            return FileResponse(build_path)
        elif public_path.exists():
            return FileResponse(public_path)

    # No file found with any extension
    raise HTTPException(status_code=404, detail="File not found")


# Import and include routers
from .routes import devices

api.include_router(devices.router, prefix="/api/devices", tags=["devices"])
