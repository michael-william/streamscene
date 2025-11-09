"""Device-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from uuid import UUID
import os

from streamscene.api.dependencies import get_db, verify_device_api_key
from streamscene.api.schemas import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceContentResponse,
    DeviceConfigResponse,
    DeviceHeartbeatResponse,
    UpdateCheckResponse,
    UpdateReportRequest,
    UpdateReportResponse,
)
from streamscene.core import streams as stream_ops
from streamscene.core import ota as ota_ops
from streamscene.core.streams import utc_now

router = APIRouter()


@router.post("/register", response_model=DeviceRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_device(
    request: DeviceRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Register a new device.

    This endpoint requires user authentication (to be implemented).
    For MVP, we'll accept device_uuid and create the registration.

    Args:
        request: Device registration request
        db: Database session

    Returns:
        DeviceRegisterResponse: Device info with API key (shown once)

    Raises:
        HTTPException: 409 if device is already registered
    """
    # TODO: Add user authentication check here
    # For MVP, we'll use a hardcoded user_id or create a test user
    # user_id = get_current_user_id_from_token()

    # For now, get the first user in the database as a workaround
    from streamscene.core.models import User
    user = db.query(User).first()
    if not user:
        raise HTTPException(
            status_code=400,
            detail="No users found. Please create a user account first.",
        )

    try:
        device, api_key = stream_ops.register_device(
            db,
            device_uuid=request.device_uuid,
            user_id=user.id,
            nickname=request.nickname,
        )
        db.commit()

        return DeviceRegisterResponse(
            device_id=device.id,
            device_uuid=device.device_uuid,
            api_key=api_key,
            nickname=device.nickname,
            message="Device registered successfully. Save your API key - it will not be shown again!",
        )

    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/{device_id}/content", response_model=DeviceContentResponse)
async def get_device_content(
    device_id: UUID,
    verified_device_id: str = Depends(verify_device_api_key),
    db: Session = Depends(get_db),
):
    """
    Get the current content that should be displayed on the device.

    Requires device API key authentication via X-Device-Api-Key header.

    Args:
        device_id: Device UUID
        verified_device_id: Device ID from API key verification
        db: Database session

    Returns:
        DeviceContentResponse: Content to display

    Raises:
        HTTPException: 403 if device_id doesn't match authenticated device
        HTTPException: 404 if device not found
    """
    # Verify the device owns this ID
    if str(device_id) != verified_device_id:
        raise HTTPException(
            status_code=403,
            detail="Device ID mismatch - you can only access your own content",
        )

    content = stream_ops.get_device_content(db, device_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceContentResponse(**content)


@router.post("/{device_id}/heartbeat", response_model=DeviceHeartbeatResponse)
async def device_heartbeat(
    device_id: UUID,
    verified_device_id: str = Depends(verify_device_api_key),
    db: Session = Depends(get_db),
):
    """
    Update device's last_seen timestamp.

    Devices should call this endpoint periodically to indicate they are online.

    Args:
        device_id: Device UUID
        verified_device_id: Device ID from API key verification
        db: Database session

    Returns:
        DeviceHeartbeatResponse: Confirmation with timestamp

    Raises:
        HTTPException: 403 if device_id doesn't match authenticated device
        HTTPException: 404 if device not found
    """
    if str(device_id) != verified_device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    success = stream_ops.update_device_heartbeat(db, device_id)
    if not success:
        raise HTTPException(status_code=404, detail="Device not found")

    db.commit()

    return DeviceHeartbeatResponse(
        status="ok",
        timestamp=utc_now(),
    )


@router.get("/{device_id}/config", response_model=DeviceConfigResponse)
async def get_device_config(
    device_id: UUID,
    verified_device_id: str = Depends(verify_device_api_key),
    db: Session = Depends(get_db),
):
    """
    Get device configuration settings.

    Args:
        device_id: Device UUID
        verified_device_id: Device ID from API key verification
        db: Database session

    Returns:
        DeviceConfigResponse: Device configuration

    Raises:
        HTTPException: 403 if device_id doesn't match authenticated device
        HTTPException: 404 if device not found
    """
    if str(device_id) != verified_device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    device = stream_ops.get_device_by_id(db, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    return DeviceConfigResponse(
        device_id=device.id,
        nickname=device.nickname,
        current_stream_id=device.current_stream_id,
        rotation_enabled=device.rotation_enabled,
        rotation_interval=device.rotation_interval,
        current_version=device.current_version,
        config=device.config,
    )


@router.get("/{device_id}/updates/check", response_model=UpdateCheckResponse)
async def check_for_updates(
    device_id: UUID,
    verified_device_id: str = Depends(verify_device_api_key),
    db: Session = Depends(get_db),
):
    """
    Check if there are available updates for the device.

    Args:
        device_id: Device UUID
        verified_device_id: Device ID from API key verification
        db: Database session

    Returns:
        UpdateCheckResponse: Update availability information

    Raises:
        HTTPException: 403 if device_id doesn't match authenticated device
        HTTPException: 404 if device not found
    """
    if str(device_id) != verified_device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    update_info = ota_ops.check_for_updates(db, device_id)
    if update_info is None:
        raise HTTPException(status_code=404, detail="Device not found")

    # If update is available, create a deployment record
    if update_info.get("update_available") and "update_id" in update_info:
        ota_ops.create_update_deployment(
            db,
            device_id=device_id,
            update_id=update_info["update_id"],
        )
        db.commit()

    return UpdateCheckResponse(**update_info)


@router.get("/{device_id}/updates/{version}/download")
async def download_update(
    device_id: UUID,
    version: str,
    verified_device_id: str = Depends(verify_device_api_key),
    db: Session = Depends(get_db),
):
    """
    Download an update package.

    Args:
        device_id: Device UUID
        version: Version to download
        verified_device_id: Device ID from API key verification
        db: Database session

    Returns:
        FileResponse: Update package file

    Raises:
        HTTPException: 403 if device_id doesn't match authenticated device
        HTTPException: 404 if update not found
    """
    if str(device_id) != verified_device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    # Get update by version
    from streamscene.core.models import DeviceUpdate
    update = db.query(DeviceUpdate).filter(DeviceUpdate.version == version).first()

    if not update or not update.is_active:
        raise HTTPException(status_code=404, detail="Update not found or not available")

    # Check if package file exists
    package_path = update.package_path
    if not os.path.exists(package_path):
        raise HTTPException(status_code=404, detail="Update package file not found")

    # Return file for download
    return FileResponse(
        path=package_path,
        media_type="application/gzip",
        filename=f"streamscene-{version}.tar.gz",
    )


@router.post("/{device_id}/updates/report", response_model=UpdateReportResponse)
async def report_update_status(
    device_id: UUID,
    request: UpdateReportRequest,
    verified_device_id: str = Depends(verify_device_api_key),
    db: Session = Depends(get_db),
):
    """
    Report the status of an update installation.

    Devices should call this endpoint to report progress during update installation.

    Args:
        device_id: Device UUID
        request: Update status report
        verified_device_id: Device ID from API key verification
        db: Database session

    Returns:
        UpdateReportResponse: Confirmation

    Raises:
        HTTPException: 403 if device_id doesn't match authenticated device
    """
    if str(device_id) != verified_device_id:
        raise HTTPException(status_code=403, detail="Device ID mismatch")

    # Update deployment status
    deployment = ota_ops.update_deployment_status(
        db,
        device_id=device_id,
        update_id=request.update_id,
        status=request.status,
        download_progress=request.download_progress,
        error_message=request.error_message,
        rollback_reason=request.rollback_reason,
    )

    db.commit()

    # Generate appropriate response message
    status_messages = {
        "downloading": f"Update download in progress ({request.download_progress}%)",
        "installing": "Update installation in progress",
        "completed": "Update completed successfully",
        "failed": "Update failed",
        "rolled_back": "Update rolled back",
    }

    message = status_messages.get(request.status, "Update status recorded")

    return UpdateReportResponse(
        status="ok",
        message=message,
    )
