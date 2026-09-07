"""OTA Update Service

Main orchestration service for OTA updates.
Coordinates state management, package handling, and installation.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .base import BaseService
from .ota_state import OTAStateManager, OTAStatus
from .ota_package import OTAPackageHandler, OTAPackageError
from .ota_installer import OTAInstaller, OTAInstallerError

try:
    from ..logging_config import ota_logger as logger
    from .. import config
except ImportError:
    import logging
    logger = logging.getLogger('streamscene.ota')
    import config


@dataclass
class UpdateInfo:
    """Information about an available update."""
    update_id: str
    version: str
    package_hash: str
    package_size: int
    is_mandatory: bool
    changelog: str
    current_version: str


@dataclass
class UpdateResult:
    """Result of an update operation."""
    success: bool
    update_installed: bool = False
    version: Optional[str] = None
    error: Optional[str] = None
    needs_reboot: bool = False


class OTAService(BaseService):
    """
    Main OTA update orchestration service.

    Responsibilities:
    - Check for available updates
    - Coordinate download, verification, installation
    - Handle boot verification after update
    - Manage rollbacks on failure
    - Report status to server
    """

    def __init__(self, api_client, config_service=None):
        """
        Initialize OTA service.

        Args:
            api_client: StreamSceneAPIClient instance
            config_service: Optional ConfigurationService for config refresh
        """
        super().__init__("streamscene.ota")

        self.api_client = api_client
        self.config_service = config_service

        # Initialize components
        self.state_manager = OTAStateManager()
        self.package_handler = OTAPackageHandler()
        self.installer = OTAInstaller()

    def initialize(self) -> bool:
        """
        Initialize the OTA service.

        Creates necessary directories and loads state.

        Returns:
            True if initialization successful
        """
        try:
            # Ensure directories exist
            if not self.package_handler.ensure_directories():
                logger.error("Failed to create package directories")
                return False

            if not self.installer.ensure_directories():
                logger.error("Failed to create installer directories")
                return False

            # Load current state
            state = self.state_manager.load()
            logger.info(f"OTA service initialized (status: {state.current_status})")

            return True

        except Exception as e:
            logger.error(f"OTA service initialization failed: {e}", exc_info=True)
            return False

    def shutdown(self) -> None:
        """Clean up OTA service resources."""
        # Clean up staging directory if not in the middle of an update
        if not self.state_manager.is_update_in_progress():
            self.package_handler.cleanup_staging()

    def should_check_for_updates(self) -> bool:
        """
        Check if we should check for updates now.

        Returns:
            True if enough time has passed since last check
        """
        return self.state_manager.should_check_for_updates()

    def check_for_updates(self) -> Optional[UpdateInfo]:
        """
        Check server for available updates.

        Returns:
            UpdateInfo if update available, None otherwise
        """
        try:
            self.state_manager.set_status(OTAStatus.CHECKING)

            response = self.api_client.check_for_updates()
            if response is None:
                logger.warning("Failed to check for updates (no response)")
                self.state_manager.set_status(OTAStatus.IDLE)
                return None

            self.state_manager.update_last_check()

            if not response.get("update_available"):
                logger.info("No update available")
                self.state_manager.set_status(OTAStatus.IDLE)
                return None

            # Parse update info
            update_info = UpdateInfo(
                update_id=response.get("update_id", ""),
                version=response.get("version", ""),
                package_hash=response.get("package_hash", ""),
                package_size=response.get("package_size", 0),
                is_mandatory=response.get("is_mandatory", False),
                changelog=response.get("changelog", ""),
                current_version=response.get("current_version", "0.0.0"),
            )

            logger.info(
                f"Update available: v{update_info.version} "
                f"(mandatory: {update_info.is_mandatory})"
            )

            return update_info

        except Exception as e:
            logger.error(f"Error checking for updates: {e}", exc_info=True)
            self.state_manager.set_status(OTAStatus.IDLE)
            return None

    def download_update(self, update_info: UpdateInfo) -> bool:
        """
        Download update package.

        Args:
            update_info: Update information from check_for_updates()

        Returns:
            True if download successful
        """
        try:
            # Check disk space
            if not self.package_handler.check_disk_space(update_info.package_size):
                logger.error("Insufficient disk space for update")
                self._report_failure(update_info, "Insufficient disk space")
                return False

            # Start tracking the update
            self.state_manager.start_update(
                update_id=update_info.update_id,
                version=update_info.version,
                package_hash=update_info.package_hash,
                package_size=update_info.package_size,
                is_mandatory=update_info.is_mandatory,
            )

            # Report download starting
            self.api_client.report_update_status(
                update_id=update_info.update_id,
                status="downloading",
                download_progress=0,
            )

            # Download with progress callback
            def on_progress(downloaded: int, total: int):
                progress = int((downloaded / total) * 100) if total > 0 else 0
                self.state_manager.update_download_progress(progress)
                # Report progress every 10%
                if progress % 10 == 0:
                    self.api_client.report_update_status(
                        update_id=update_info.update_id,
                        status="downloading",
                        download_progress=progress,
                    )

            data = self.api_client.download_update(
                version=update_info.version,
                progress_callback=on_progress,
            )

            if data is None:
                logger.error("Download failed (no data received)")
                self._report_failure(update_info, "Download failed")
                return False

            # Save package
            package_path = self.package_handler.write_package(
                version=update_info.version,
                data=data,
            )

            logger.info(f"Download complete: {package_path}")
            self.state_manager.update_download_progress(100)

            return True

        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            self._report_failure(update_info, str(e))
            return False

    def verify_package(self, update_info: UpdateInfo) -> bool:
        """
        Verify downloaded package hash.

        Args:
            update_info: Update information

        Returns:
            True if verification successful
        """
        try:
            self.state_manager.set_status(OTAStatus.VERIFYING)

            package_path = self.package_handler.get_package_path(update_info.version)

            if not self.package_handler.verify_hash(
                package_path, update_info.package_hash
            ):
                logger.error("Package hash verification failed")
                self._report_failure(update_info, "Hash verification failed")
                return False

            logger.info("Package verified successfully")
            return True

        except OTAPackageError as e:
            logger.error(f"Verification error: {e}")
            self._report_failure(update_info, str(e))
            return False

    def install_update(self, update_info: UpdateInfo) -> bool:
        """
        Install the update package.

        Creates backup, extracts package, runs update script.

        Args:
            update_info: Update information

        Returns:
            True if installation successful
        """
        backup_path = None

        try:
            self.state_manager.set_status(OTAStatus.INSTALLING)

            # Report installing
            self.api_client.report_update_status(
                update_id=update_info.update_id,
                status="installing",
            )

            # Create backup
            logger.info("Creating backup before update...")
            backup_path = self.installer.create_backup()
            logger.info(f"Backup created: {backup_path}")

            # Extract package
            package_path = self.package_handler.get_package_path(update_info.version)
            staging_dir = self.package_handler.extract_package(package_path)

            # Validate package structure
            is_valid, error_msg = self.package_handler.validate_package_structure(
                staging_dir
            )
            if not is_valid:
                logger.error(f"Invalid package structure: {error_msg}")
                self._rollback_and_report(update_info, backup_path, error_msg)
                return False

            # Run update script
            logger.info("Running update script...")
            success, output = self.installer.run_update_script(staging_dir)

            if not success:
                logger.error(f"Update script failed: {output}")
                self._rollback_and_report(update_info, backup_path, output)
                return False

            # Verify installation
            is_valid, error_msg = self.installer.verify_installation()
            if not is_valid:
                logger.error(f"Installation verification failed: {error_msg}")
                self._rollback_and_report(update_info, backup_path, error_msg)
                return False

            # Mark as pending verification (for after reboot)
            self.state_manager.mark_pending_verification(str(backup_path))

            # Clean up old backups
            self.installer.cleanup_old_backups()

            # Clean up staging and download
            self.package_handler.cleanup_staging()
            self.package_handler.cleanup_download(update_info.version)

            logger.info(f"Update to v{update_info.version} installed, reboot required")
            return True

        except (OTAPackageError, OTAInstallerError) as e:
            logger.error(f"Installation error: {e}", exc_info=True)
            if backup_path:
                self._rollback_and_report(update_info, backup_path, str(e))
            else:
                self._report_failure(update_info, str(e))
            return False

        except Exception as e:
            logger.error(f"Unexpected installation error: {e}", exc_info=True)
            if backup_path:
                self._rollback_and_report(update_info, backup_path, str(e))
            else:
                self._report_failure(update_info, str(e))
            return False

    def check_pending_verification(self) -> Optional[dict]:
        """
        Check if there's a pending update verification after reboot.

        Returns:
            Dict with update info if pending, None otherwise
        """
        return self.state_manager.get_pending_verification()

    def verify_boot_success(self) -> bool:
        """
        Verify that the new version booted successfully.

        Called on startup to confirm update worked.

        Returns:
            True if boot verification passed
        """
        pending = self.state_manager.get_pending_verification()
        if not pending:
            return True  # No pending verification

        try:
            update_version = pending.get("update_version")
            current_version = config.get_current_version()

            logger.info(
                f"Verifying boot: expected v{update_version}, "
                f"current v{current_version}"
            )

            # Check if version matches expected
            if current_version != update_version:
                logger.warning(
                    f"Version mismatch after update: expected {update_version}, "
                    f"got {current_version}"
                )
                return False

            # Basic health check - can we reach the API?
            if not self.api_client.health_check():
                logger.warning("API health check failed after update")
                # Don't fail boot verification for network issues
                # Device might be starting up before network is ready

            logger.info("Boot verification passed")
            return True

        except Exception as e:
            logger.error(f"Boot verification error: {e}", exc_info=True)
            return False

    def complete_pending_verification(self) -> bool:
        """
        Complete pending update verification after successful boot.

        Reports success to server and cleans up state.

        Returns:
            True if completion successful
        """
        pending = self.state_manager.get_pending_verification()
        if not pending:
            return True

        try:
            # Report success to server
            self.api_client.report_update_status(
                update_id=pending["update_id"],
                status="completed",
            )

            # Mark completed in state
            self.state_manager.mark_completed()

            logger.info(f"Update to v{pending['update_version']} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error completing verification: {e}", exc_info=True)
            return False

    def rollback_pending_update(self, reason: str) -> bool:
        """
        Rollback a pending update that failed boot verification.

        Args:
            reason: Reason for rollback

        Returns:
            True if rollback successful
        """
        pending = self.state_manager.get_pending_verification()
        if not pending:
            return True

        backup_path = pending.get("backup_path")
        if not backup_path:
            logger.error("No backup path for rollback")
            self.state_manager.mark_failed("No backup available for rollback")
            return False

        try:
            # Perform rollback
            self.installer.rollback(Path(backup_path))

            # Report to server
            self.api_client.report_update_status(
                update_id=pending["update_id"],
                status="rolled_back",
                rollback_reason=reason,
            )

            # Update state
            self.state_manager.mark_rolled_back(reason)

            logger.info(f"Rolled back update: {reason}")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            self.state_manager.mark_failed(f"Rollback failed: {e}")
            return False

    def run_update_cycle(self) -> UpdateResult:
        """
        Run a complete update cycle.

        Checks for updates, downloads, verifies, and installs.
        Returns result indicating if reboot is needed.

        Returns:
            UpdateResult with outcome details
        """
        try:
            # Check for updates
            update_info = self.check_for_updates()
            if not update_info:
                return UpdateResult(success=True, update_installed=False)

            # Download
            if not self.download_update(update_info):
                return UpdateResult(
                    success=False,
                    error="Download failed",
                )

            # Verify
            if not self.verify_package(update_info):
                return UpdateResult(
                    success=False,
                    error="Verification failed",
                )

            # Install
            if not self.install_update(update_info):
                return UpdateResult(
                    success=False,
                    error="Installation failed",
                )

            # Success - needs reboot
            return UpdateResult(
                success=True,
                update_installed=True,
                version=update_info.version,
                needs_reboot=True,
            )

        except Exception as e:
            logger.error(f"Update cycle error: {e}", exc_info=True)
            return UpdateResult(
                success=False,
                error=str(e),
            )

    def handle_mandatory_update(self) -> UpdateResult:
        """
        Check for and install mandatory updates.

        Should be called at startup before normal operation.

        Returns:
            UpdateResult indicating if mandatory update was installed
        """
        try:
            update_info = self.check_for_updates()

            if not update_info or not update_info.is_mandatory:
                return UpdateResult(success=True, update_installed=False)

            logger.warning(f"Mandatory update required: v{update_info.version}")

            # Run full update cycle
            return self.run_update_cycle()

        except Exception as e:
            logger.error(f"Mandatory update error: {e}", exc_info=True)
            return UpdateResult(success=False, error=str(e))

    def trigger_reboot(self) -> bool:
        """
        Trigger system reboot after update.

        Returns:
            True if reboot command was sent
        """
        try:
            logger.info("Triggering system reboot...")
            subprocess.run(
                ["sudo", "reboot"],
                timeout=30,
                check=True,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to trigger reboot: {e}")
            return False

    def _report_failure(self, update_info: UpdateInfo, error: str) -> None:
        """Report update failure to server and update state."""
        self.api_client.report_update_status(
            update_id=update_info.update_id,
            status="failed",
            error_message=error,
        )
        self.state_manager.mark_failed(error)

    def _rollback_and_report(
        self,
        update_info: UpdateInfo,
        backup_path: Path,
        reason: str,
    ) -> None:
        """Rollback installation and report to server."""
        try:
            self.installer.rollback(backup_path)
            self.api_client.report_update_status(
                update_id=update_info.update_id,
                status="rolled_back",
                rollback_reason=reason,
            )
            self.state_manager.mark_rolled_back(reason)
        except Exception as e:
            logger.error(f"Rollback failed: {e}", exc_info=True)
            self._report_failure(update_info, f"Rollback failed: {e}")
