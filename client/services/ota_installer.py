"""OTA Installer

Handles backup, installation, and rollback of OTA updates.
"""

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

try:
    from ..logging_config import ota_logger as logger, log_subprocess_output
    from .. import config
except ImportError:
    import logging
    logger = logging.getLogger('streamscene.ota')
    import config

    def log_subprocess_output(logger, result, cmd):
        """Fallback for test context."""
        if hasattr(result, 'stdout') and result.stdout:
            logger.debug(f"stdout: {result.stdout}")
        if hasattr(result, 'stderr') and result.stderr:
            logger.debug(f"stderr: {result.stderr}")


class OTAInstallerError(Exception):
    """Base exception for OTA installer operations."""
    pass


class BackupError(OTAInstallerError):
    """Error during backup creation."""
    pass


class InstallError(OTAInstallerError):
    """Error during installation."""
    pass


class RollbackError(OTAInstallerError):
    """Error during rollback."""
    pass


class OTAInstaller:
    """
    Handles OTA installation operations.

    Responsibilities:
    - Create backups before updates
    - Execute update scripts
    - Rollback on failure
    - Cleanup old backups
    """

    def __init__(
        self,
        install_dir: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
    ):
        """
        Initialize installer.

        Args:
            install_dir: Target installation directory
            backup_dir: Directory for backups
        """
        self.install_dir = install_dir or config.OTA_INSTALL_DIR
        self.backup_dir = backup_dir or config.OTA_BACKUP_DIR

    def ensure_directories(self) -> bool:
        """
        Ensure required directories exist.

        Returns:
            True if directories exist or were created
        """
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directories: {e}")
            return False

    def get_current_version(self) -> str:
        """
        Get current installed version.

        Returns:
            Version string or "0.0.0" if not found
        """
        return config.get_current_version()

    def create_backup(self) -> Path:
        """
        Create backup of current installation.

        Returns:
            Path to backup directory

        Raises:
            BackupError: If backup fails
        """
        if not self.install_dir.exists():
            raise BackupError(f"Install directory not found: {self.install_dir}")

        try:
            self.ensure_directories()

            # Create timestamped backup directory
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            current_version = self.get_current_version()
            backup_name = f"backup-v{current_version}-{timestamp}"
            backup_path = self.backup_dir / backup_name

            logger.info(f"Creating backup at {backup_path}")

            # Copy entire installation directory
            shutil.copytree(
                self.install_dir,
                backup_path,
                symlinks=True,
                ignore_dangling_symlinks=True,
            )

            # Verify backup was created
            if not backup_path.exists():
                raise BackupError("Backup directory was not created")

            # Count files as basic verification
            file_count = sum(1 for _ in backup_path.rglob('*') if _.is_file())
            logger.info(f"Backup created successfully ({file_count} files)")

            return backup_path

        except BackupError:
            raise
        except Exception as e:
            raise BackupError(f"Failed to create backup: {e}")

    def run_update_script(
        self,
        staging_dir: Path,
        timeout: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Execute the update.sh script from staging directory.

        Args:
            staging_dir: Path to extracted update package
            timeout: Script timeout in seconds (default: config.OTA_INSTALL_TIMEOUT)

        Returns:
            Tuple of (success, output_or_error)

        Raises:
            InstallError: If script execution fails critically
        """
        update_script = staging_dir / "update.sh"
        timeout = timeout or config.OTA_INSTALL_TIMEOUT

        if not update_script.exists():
            raise InstallError("update.sh not found in staging directory")

        try:
            # Make script executable
            os.chmod(update_script, 0o755)

            logger.info(f"Executing update script (timeout: {timeout}s)")

            # Run the update script
            result = subprocess.run(
                ["/bin/bash", str(update_script)],
                cwd=str(staging_dir),
                capture_output=True,
                timeout=timeout,
                text=True,
            )

            # Log output
            log_subprocess_output(logger, result, "update.sh")

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error(f"Update script failed with exit code {result.returncode}")
                return False, f"Exit code {result.returncode}: {error_msg}"

            logger.info("Update script completed successfully")
            return True, result.stdout or "Success"

        except subprocess.TimeoutExpired:
            logger.error(f"Update script timed out after {timeout}s")
            return False, f"Script timed out after {timeout} seconds"

        except PermissionError as e:
            raise InstallError(f"Permission denied executing update script: {e}")

        except Exception as e:
            raise InstallError(f"Failed to run update script: {e}")

    def verify_installation(self) -> Tuple[bool, str]:
        """
        Verify the new installation is functional.

        Performs basic sanity checks:
        - VERSION file exists
        - Main Python file has valid syntax

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check VERSION file
        version_file = self.install_dir / "VERSION"
        if not version_file.exists():
            return False, "VERSION file not found after install"

        # Check main.py syntax
        main_file = self.install_dir / "main.py"
        if main_file.exists():
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(main_file)],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    error = result.stderr.decode() if result.stderr else "Syntax error"
                    return False, f"main.py has syntax errors: {error}"
            except Exception as e:
                logger.warning(f"Could not verify main.py syntax: {e}")

        logger.info("Installation verification passed")
        return True, ""

    def rollback(self, backup_path: Path) -> bool:
        """
        Restore installation from backup.

        Args:
            backup_path: Path to backup directory

        Returns:
            True if rollback successful

        Raises:
            RollbackError: If rollback fails
        """
        if not backup_path.exists():
            raise RollbackError(f"Backup not found: {backup_path}")

        try:
            logger.warning(f"Rolling back to backup: {backup_path.name}")

            # Remove current installation
            if self.install_dir.exists():
                shutil.rmtree(self.install_dir)

            # Restore from backup
            shutil.copytree(
                backup_path,
                self.install_dir,
                symlinks=True,
                ignore_dangling_symlinks=True,
            )

            # Verify restoration
            if not self.install_dir.exists():
                raise RollbackError("Installation directory not restored")

            logger.info("Rollback completed successfully")
            return True

        except RollbackError:
            raise
        except Exception as e:
            raise RollbackError(f"Rollback failed: {e}")

    def list_backups(self) -> List[Path]:
        """
        List all backups sorted by date (newest first).

        Returns:
            List of backup directory paths
        """
        if not self.backup_dir.exists():
            return []

        backups = []
        for path in self.backup_dir.iterdir():
            if path.is_dir() and path.name.startswith("backup-"):
                backups.append(path)

        # Sort by modification time (newest first)
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups

    def cleanup_old_backups(self, keep_count: Optional[int] = None) -> int:
        """
        Remove old backups, keeping only the most recent ones.

        Args:
            keep_count: Number of backups to keep (default: config.OTA_BACKUP_RETENTION)

        Returns:
            Number of backups removed
        """
        keep_count = keep_count or config.OTA_BACKUP_RETENTION
        backups = self.list_backups()

        if len(backups) <= keep_count:
            return 0

        removed = 0
        for backup in backups[keep_count:]:
            try:
                shutil.rmtree(backup)
                logger.info(f"Removed old backup: {backup.name}")
                removed += 1
            except Exception as e:
                logger.warning(f"Failed to remove backup {backup.name}: {e}")

        return removed

    def get_latest_backup(self) -> Optional[Path]:
        """
        Get the most recent backup.

        Returns:
            Path to latest backup or None if no backups exist
        """
        backups = self.list_backups()
        return backups[0] if backups else None

    def get_backup_info(self, backup_path: Path) -> dict:
        """
        Get information about a backup.

        Args:
            backup_path: Path to backup directory

        Returns:
            Dict with backup info (version, timestamp, size)
        """
        info = {
            "path": str(backup_path),
            "name": backup_path.name,
            "version": "unknown",
            "timestamp": None,
            "size_mb": 0,
        }

        try:
            # Get version from backup
            version_file = backup_path / "VERSION"
            if version_file.exists():
                info["version"] = version_file.read_text().strip()

            # Get timestamp from directory name or mtime
            info["timestamp"] = datetime.fromtimestamp(
                backup_path.stat().st_mtime
            ).isoformat()

            # Calculate size
            total_size = sum(
                f.stat().st_size
                for f in backup_path.rglob('*')
                if f.is_file()
            )
            info["size_mb"] = round(total_size / 1024 / 1024, 2)

        except Exception as e:
            logger.warning(f"Error getting backup info: {e}")

        return info
