"""FastAPI dependencies for authentication and database access."""

from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Generator

from streamscene.core.database import get_session
from streamscene.core.auth import verify_api_key
from streamscene.core.models import Device


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for database sessions.

    Yields:
        Session: SQLAlchemy database session
    """
    db = get_session()
    try:
        yield db
    finally:
        db.close()


async def verify_device_api_key(
    x_device_api_key: str = Header(..., description="Device API key for authentication"),
    db: Session = Depends(get_db),
) -> str:
    """
    Verify device API key and return device ID.

    Args:
        x_device_api_key: API key from X-Device-Api-Key header
        db: Database session

    Returns:
        str: Device ID if authentication successful

    Raises:
        HTTPException: 401 if API key is invalid
    """
    # Query all devices and check API key hash
    devices = db.query(Device).filter(Device.api_key_hash.isnot(None)).all()

    for device in devices:
        if verify_api_key(x_device_api_key, device.api_key_hash):
            return str(device.id)

    raise HTTPException(
        status_code=401,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )
