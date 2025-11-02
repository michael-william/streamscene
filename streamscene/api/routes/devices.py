"""Device-related API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from streamscene.api.dependencies import get_db, verify_device_api_key
from streamscene.api.schemas import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceContentResponse,
    DeviceConfigResponse,
    DeviceHeartbeatResponse,
)
from streamscene.core import streams as stream_ops
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
