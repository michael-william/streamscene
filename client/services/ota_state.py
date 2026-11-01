"""OTA Update State Management

Persistent state management for resumable OTA updates.
State is saved to disk and survives reboots.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from ..logging_config import ota_logger as logger
    from .. import config
except ImportError:
    # Running directly or in test context
    import logging
    logger = logging.getLogger('streamscene.ota')
    import config


class OTAStatus(Enum):
    """OTA update status states."""
    IDLE = "idle"
    CHECKING = "checking"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    INSTALLING = "installing"
    PENDING_VERIFICATION = "pending_verification"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class OTAStateData:
    """
    Persistent OTA state data.

    This data survives reboots and is used to:
    - Resume interrupted downloads
    - Verify boot success after update
    - Track update history
    """
    current_status: str = OTAStatus.IDLE.value
    update_id: Optional[str] = None
    update_version: Optional[str] = None
    package_hash: Optional[str] = None
    package_size: Optional[int] = None
    download_progress: int = 0
    backup_path: Optional[str] = None
    started_at: Optional[str] = None
    last_check_at: Optional[str] = None
    reboot_count: int = 0
    is_mandatory: bool = False
    error_history: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OTAStateData":
        """Create from dictionary."""
        return cls(
            current_status=data.get("current_status", OTAStatus.IDLE.value),
            update_id=data.get("update_id"),
            update_version=data.get("update_version"),
            package_hash=data.get("package_hash"),
            package_size=data.get("package_size"),
            download_progress=data.get("download_progress", 0),
            backup_path=data.get("backup_path"),
            started_at=data.get("started_at"),
            last_check_at=data.get("last_check_at"),
            reboot_count=data.get("reboot_count", 0),
            is_mandatory=data.get("is_mandatory", False),
            error_history=data.get("error_history", []),
        )


class OTAStateManager:
    """
    Manages persistent OTA update state.

    State is stored in JSON format at OTA_STATE_FILE.
    All operations are atomic - partial writes won't corrupt state.
    """

    MAX_ERROR_HISTORY = 10

    def __init__(self, state_file: Optional[Path] = None):
        """
        Initialize state manager.

        Args:
            state_file: Path to state file (default: config.OTA_STATE_FILE)
        """
        self.state_file = state_file or config.OTA_STATE_FILE
        self._state: Optional[OTAStateData] = None

    def load(self) -> OTAStateData:
        """
        Load state from disk.

        Returns:
            OTAStateData instance (default state if file doesn't exist)
        """
        if self._state is not None:
            return self._state

        if not self.state_file.exists():
            logger.debug("No state file found, using default state")
            self._state = OTAStateData()
            return self._state

        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            self._state = OTAStateData.from_dict(data)
            logger.debug(f"Loaded OTA state: status={self._state.current_status}")
            return self._state
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted state file, resetting: {e}")
            self._state = OTAStateData()
            self.save(self._state)
            return self._state
        except Exception as e:
            logger.error(f"Error loading state file: {e}", exc_info=True)
            self._state = OTAStateData()
            return self._state

    def save(self, state: OTAStateData) -> bool:
        """
        Save state to disk atomically.

        Uses write-to-temp + rename for atomicity.

        Args:
            state: State to save

        Returns:
            True if saved successfully
        """
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first
            temp_file = self.state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state.to_dict(), f, indent=2)

            # Atomic rename
            temp_file.rename(self.state_file)

            self._state = state
            logger.debug(f"Saved OTA state: status={state.current_status}")
            return True

        except Exception as e:
            logger.error(f"Error saving state: {e}", exc_info=True)
            return False

    def reset(self) -> OTAStateData:
        """
        Reset state to idle.

        Returns:
            Fresh OTAStateData instance
        """
        # Keep last_check_at: wiping it made should_check_for_updates() true on
        # the very next loop, so a failing update was re-downloaded, backed up
        # and rolled back every ~minute instead of once per OTA_CHECK_INTERVAL.
        previous = self.load()
        state = OTAStateData(last_check_at=previous.last_check_at)
        self.save(state)
        logger.info("OTA state reset to idle")
        return state

    def get_status(self) -> OTAStatus:
        """Get current OTA status."""
        state = self.load()
        try:
            return OTAStatus(state.current_status)
        except ValueError:
            logger.warning(f"Unknown status '{state.current_status}', defaulting to IDLE")
            return OTAStatus.IDLE

    def set_status(self, status: OTAStatus, **kwargs) -> bool:
        """
        Update status and optionally other fields.

        Args:
            status: New status
            **kwargs: Additional fields to update

        Returns:
            True if saved successfully
        """
        state = self.load()
        state.current_status = status.value

        # Update additional fields
        for key, value in kwargs.items():
            if hasattr(state, key):
                setattr(state, key, value)

        return self.save(state)

    def is_update_in_progress(self) -> bool:
        """Check if an update is currently in progress."""
        status = self.get_status()
        return status in (
            OTAStatus.CHECKING,
            OTAStatus.DOWNLOADING,
            OTAStatus.VERIFYING,
            OTAStatus.INSTALLING,
            OTAStatus.PENDING_VERIFICATION,
        )

    def get_pending_verification(self) -> Optional[Dict[str, Any]]:
        """
        Get pending update verification info if device just rebooted after update.

        Returns:
            Dict with update_id, update_version, backup_path if pending, else None
        """
        state = self.load()
        if state.current_status == OTAStatus.PENDING_VERIFICATION.value:
            return {
                "update_id": state.update_id,
                "update_version": state.update_version,
                "backup_path": state.backup_path,
                "reboot_count": state.reboot_count,
            }
        return None

    def increment_reboot_count(self) -> int:
        """
        Increment reboot counter (for boot verification).

        Returns:
            New reboot count
        """
        state = self.load()
        state.reboot_count += 1
        self.save(state)
        return state.reboot_count

    def start_update(
        self,
        update_id: str,
        version: str,
        package_hash: str,
        package_size: int,
        is_mandatory: bool = False,
    ) -> bool:
        """
        Start tracking a new update.

        Args:
            update_id: Server update ID
            version: Target version
            package_hash: Expected SHA256 hash
            package_size: Expected package size in bytes
            is_mandatory: Whether update is mandatory

        Returns:
            True if saved successfully
        """
        state = OTAStateData(
            current_status=OTAStatus.DOWNLOADING.value,
            update_id=update_id,
            update_version=version,
            package_hash=package_hash,
            package_size=package_size,
            download_progress=0,
            started_at=datetime.now().isoformat(),
            is_mandatory=is_mandatory,
        )
        if self.save(state):
            logger.info(f"Started tracking update to v{version}")
            return True
        return False

    def update_download_progress(self, progress: int) -> bool:
        """
        Update download progress percentage.

        Args:
            progress: Progress 0-100

        Returns:
            True if saved successfully
        """
        state = self.load()
        state.download_progress = min(100, max(0, progress))
        return self.save(state)

    def mark_pending_verification(self, backup_path: str) -> bool:
        """
        Mark update as pending verification after install.

        This is set just before reboot. On next boot, we check
        if the new version works correctly.

        Args:
            backup_path: Path to backup for rollback

        Returns:
            True if saved successfully
        """
        state = self.load()
        state.current_status = OTAStatus.PENDING_VERIFICATION.value
        state.backup_path = backup_path
        state.reboot_count = 0
        return self.save(state)

    def mark_completed(self) -> bool:
        """
        Mark update as completed successfully.

        Returns:
            True if saved successfully
        """
        state = self.load()
        version = state.update_version
        state.current_status = OTAStatus.COMPLETED.value
        state.backup_path = None
        state.reboot_count = 0
        if self.save(state):
            logger.info(f"Update to v{version} completed successfully")
            # Reset to idle after completion
            return self.reset() is not None
        return False

    def mark_failed(self, error_message: str) -> bool:
        """
        Mark update as failed.

        Args:
            error_message: Error description

        Returns:
            True if saved successfully
        """
        state = self.load()
        state.current_status = OTAStatus.FAILED.value

        # Add to error history
        state.error_history.append({
            "timestamp": datetime.now().isoformat(),
            "version": state.update_version,
            "error": error_message,
        })

        # Keep only last N errors
        if len(state.error_history) > self.MAX_ERROR_HISTORY:
            state.error_history = state.error_history[-self.MAX_ERROR_HISTORY:]

        logger.error(f"Update failed: {error_message}")
        return self.save(state)

    def mark_rolled_back(self, reason: str) -> bool:
        """
        Mark update as rolled back.

        Args:
            reason: Rollback reason

        Returns:
            True if saved successfully
        """
        state = self.load()
        version = state.update_version
        state.current_status = OTAStatus.ROLLED_BACK.value

        # Add to error history
        state.error_history.append({
            "timestamp": datetime.now().isoformat(),
            "version": version,
            "rollback_reason": reason,
        })

        if len(state.error_history) > self.MAX_ERROR_HISTORY:
            state.error_history = state.error_history[-self.MAX_ERROR_HISTORY:]

        logger.warning(f"Update to v{version} rolled back: {reason}")
        if self.save(state):
            # Reset to idle after rollback
            return self.reset() is not None
        return False

    def update_last_check(self) -> bool:
        """
        Update last check timestamp.

        Returns:
            True if saved successfully
        """
        state = self.load()
        state.last_check_at = datetime.now().isoformat()
        return self.save(state)

    def should_check_for_updates(self) -> bool:
        """
        Check if enough time has passed since last update check.

        Returns:
            True if should check for updates
        """
        state = self.load()

        # Don't check if update in progress
        if self.is_update_in_progress():
            return False

        # Always check if never checked
        if not state.last_check_at:
            return True

        try:
            last_check = datetime.fromisoformat(state.last_check_at)
            elapsed = (datetime.now() - last_check).total_seconds()
            return elapsed >= config.OTA_CHECK_INTERVAL
        except (ValueError, TypeError):
            return True
