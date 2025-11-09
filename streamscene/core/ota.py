"""OTA (Over-The-Air) update business logic."""

import hashlib
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session
from packaging import version

from .models import Device, DeviceUpdate, UpdateDeployment, utc_now


def check_for_updates(db: Session, device_id: UUID) -> Optional[dict]:
    """
    Check if there are available updates for a device.

    Args:
        db: Database session
        device_id: Device ID

    Returns:
        Dictionary with update information, or None if no update available
    """
    # Get device
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        return None

    current_version = device.current_version

    # Find the latest active update
    latest_update = (
        db.query(DeviceUpdate)
        .filter(DeviceUpdate.is_active == True)
        .order_by(DeviceUpdate.release_date.desc())
        .first()
    )

    if not latest_update:
        return {
            "update_available": False,
            "current_version": current_version,
        }

    # Check if device is already on this version or newer
    try:
        if version.parse(current_version) >= version.parse(latest_update.version):
            return {
                "update_available": False,
                "current_version": current_version,
            }
    except Exception:
        # If version parsing fails, assume update is available
        pass

    # Check minimum version requirement
    if latest_update.min_version_required:
        try:
            if version.parse(current_version) < version.parse(latest_update.min_version_required):
                # Device version is too old for this update
                return {
                    "update_available": False,
                    "current_version": current_version,
                    "error": f"Update requires minimum version {latest_update.min_version_required}",
                }
        except Exception:
            pass

    # Check rollout percentage (staged rollout)
    if latest_update.rollout_percentage < 100:
        # Use device ID as seed for deterministic randomization
        device_hash = int(hashlib.md5(str(device_id).encode()).hexdigest(), 16)
        device_percentage = (device_hash % 100) + 1  # 1-100

        if device_percentage > latest_update.rollout_percentage:
            # Device is not in the rollout group yet
            return {
                "update_available": False,
                "current_version": current_version,
            }

    # Check if update is already deployed/completed
    existing_deployment = (
        db.query(UpdateDeployment)
        .filter(
            UpdateDeployment.device_id == device_id,
            UpdateDeployment.update_id == latest_update.id,
            UpdateDeployment.status == "completed",
        )
        .first()
    )

    if existing_deployment:
        return {
            "update_available": False,
            "current_version": current_version,
        }

    # Update is available!
    return {
        "update_available": True,
        "version": latest_update.version,
        "update_id": latest_update.id,
        "is_mandatory": latest_update.is_mandatory,
        "package_size": latest_update.package_size,
        "package_hash": latest_update.package_hash,
        "changelog": latest_update.changelog,
        "current_version": current_version,
    }


def create_update_deployment(
    db: Session,
    device_id: UUID,
    update_id: UUID,
) -> UpdateDeployment:
    """
    Create or update a deployment record for an update.

    Args:
        db: Database session
        device_id: Device ID
        update_id: Update ID

    Returns:
        UpdateDeployment instance
    """
    # Check if deployment already exists
    deployment = (
        db.query(UpdateDeployment)
        .filter(
            UpdateDeployment.device_id == device_id,
            UpdateDeployment.update_id == update_id,
        )
        .first()
    )

    if deployment:
        # Reset existing deployment
        deployment.status = "pending"
        deployment.started_at = None
        deployment.completed_at = None
        deployment.error_message = None
        deployment.rollback_reason = None
        deployment.download_progress = 0
    else:
        # Create new deployment
        deployment = UpdateDeployment(
            device_id=device_id,
            update_id=update_id,
            status="pending",
            download_progress=0,
        )
        db.add(deployment)

    return deployment


def update_deployment_status(
    db: Session,
    device_id: UUID,
    update_id: UUID,
    status: str,
    download_progress: Optional[int] = None,
    error_message: Optional[str] = None,
    rollback_reason: Optional[str] = None,
) -> Optional[UpdateDeployment]:
    """
    Update the status of an update deployment.

    Args:
        db: Database session
        device_id: Device ID
        update_id: Update ID
        status: New status (downloading, installing, completed, failed, rolled_back)
        download_progress: Download progress (0-100)
        error_message: Error message if failed
        rollback_reason: Reason for rollback

    Returns:
        Updated UpdateDeployment instance, or None if not found
    """
    deployment = (
        db.query(UpdateDeployment)
        .filter(
            UpdateDeployment.device_id == device_id,
            UpdateDeployment.update_id == update_id,
        )
        .first()
    )

    if not deployment:
        # Create deployment if it doesn't exist
        deployment = create_update_deployment(db, device_id, update_id)

    # Update status
    deployment.status = status

    # Set timestamps
    if status in ("downloading", "installing") and not deployment.started_at:
        deployment.started_at = utc_now()

    if status in ("completed", "failed", "rolled_back"):
        deployment.completed_at = utc_now()

    # Update optional fields
    if download_progress is not None:
        deployment.download_progress = download_progress

    if error_message:
        deployment.error_message = error_message

    if rollback_reason:
        deployment.rollback_reason = rollback_reason

    # If completed successfully, update device version
    if status == "completed":
        device = db.query(Device).filter(Device.id == device_id).first()
        update = db.query(DeviceUpdate).filter(DeviceUpdate.id == update_id).first()
        if device and update:
            device.current_version = update.version

    return deployment


def get_update_package_path(db: Session, update_id: UUID) -> Optional[str]:
    """
    Get the file path for an update package.

    Args:
        db: Database session
        update_id: Update ID

    Returns:
        Path to update package file, or None if not found
    """
    update = db.query(DeviceUpdate).filter(DeviceUpdate.id == update_id).first()
    if not update:
        return None

    return update.package_path


def verify_update_package(file_path: str, expected_hash: str) -> bool:
    """
    Verify the integrity of an update package using SHA256 hash.

    Args:
        file_path: Path to the update package file
        expected_hash: Expected SHA256 hash

    Returns:
        True if hash matches, False otherwise
    """
    sha256_hash = hashlib.sha256()

    try:
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        calculated_hash = sha256_hash.hexdigest()
        return calculated_hash == expected_hash

    except FileNotFoundError:
        return False
