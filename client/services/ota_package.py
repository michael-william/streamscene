"""OTA Package Handler

Handles download, verification, and extraction of OTA update packages.
"""

import hashlib
import shutil
import tarfile
from pathlib import Path
from typing import Optional, Callable, Tuple

try:
    from ..logging_config import ota_logger as logger
    from .. import config
except ImportError:
    import logging
    logger = logging.getLogger('streamscene.ota')
    import config


class OTAPackageError(Exception):
    """Base exception for OTA package operations."""
    pass


class DownloadError(OTAPackageError):
    """Error during package download."""
    pass


class VerificationError(OTAPackageError):
    """Error during package verification."""
    pass


class ExtractionError(OTAPackageError):
    """Error during package extraction."""
    pass


class OTAPackageHandler:
    """
    Handles OTA package operations.

    Responsibilities:
    - Download update packages (with resume support)
    - Verify SHA256 hash
    - Extract tar.gz packages
    - Validate package structure
    """

    REQUIRED_FILES = ["update.sh", "VERSION"]
    CHUNK_SIZE = 8192  # 8KB chunks for download/hash

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        staging_dir: Optional[Path] = None,
    ):
        """
        Initialize package handler.

        Args:
            download_dir: Directory for downloaded packages
            staging_dir: Directory for extracted packages
        """
        self.download_dir = download_dir or config.OTA_DOWNLOAD_DIR
        self.staging_dir = staging_dir or config.OTA_STAGING_DIR

    def ensure_directories(self) -> bool:
        """
        Ensure required directories exist.

        Returns:
            True if directories exist or were created
        """
        try:
            self.download_dir.mkdir(parents=True, exist_ok=True)
            self.staging_dir.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directories: {e}")
            return False

    def get_package_path(self, version: str) -> Path:
        """
        Get path for a package version.

        Args:
            version: Package version

        Returns:
            Path to package file
        """
        return self.download_dir / f"streamscene-update-{version}.tar.gz"

    def check_disk_space(self, required_bytes: int) -> bool:
        """
        Check if sufficient disk space is available.

        Args:
            required_bytes: Required space in bytes

        Returns:
            True if enough space available
        """
        try:
            # Check download directory mount point
            stat = shutil.disk_usage(self.download_dir.parent)
            # Require 2x the package size (for download + extraction)
            required = max(required_bytes * 2, config.OTA_MIN_DISK_SPACE)

            if stat.free < required:
                logger.warning(
                    f"Insufficient disk space: {stat.free / 1024 / 1024:.1f}MB free, "
                    f"{required / 1024 / 1024:.1f}MB required"
                )
                return False

            return True
        except Exception as e:
            logger.error(f"Error checking disk space: {e}")
            return False

    def save_package_chunk(
        self,
        version: str,
        chunk: bytes,
        offset: int,
    ) -> bool:
        """
        Save a chunk of package data (for streaming downloads).

        Args:
            version: Package version
            chunk: Data chunk
            offset: File offset to write at

        Returns:
            True if saved successfully
        """
        try:
            package_path = self.get_package_path(version)
            mode = 'r+b' if package_path.exists() else 'wb'

            with open(package_path, mode) as f:
                f.seek(offset)
                f.write(chunk)

            return True
        except Exception as e:
            logger.error(f"Error saving package chunk: {e}")
            return False

    def write_package(self, version: str, data: bytes) -> Path:
        """
        Write complete package data to file.

        Args:
            version: Package version
            data: Complete package data

        Returns:
            Path to saved package

        Raises:
            DownloadError: If write fails
        """
        try:
            self.ensure_directories()
            package_path = self.get_package_path(version)

            with open(package_path, 'wb') as f:
                f.write(data)

            logger.info(f"Saved package to {package_path}")
            return package_path

        except Exception as e:
            raise DownloadError(f"Failed to save package: {e}")

    def get_download_progress(self, version: str, expected_size: int) -> int:
        """
        Get download progress percentage.

        Args:
            version: Package version
            expected_size: Expected total size in bytes

        Returns:
            Progress percentage 0-100
        """
        package_path = self.get_package_path(version)
        if not package_path.exists():
            return 0

        try:
            current_size = package_path.stat().st_size
            if expected_size <= 0:
                return 0
            return min(100, int((current_size / expected_size) * 100))
        except Exception:
            return 0

    def verify_hash(self, package_path: Path, expected_hash: str) -> bool:
        """
        Verify SHA256 hash of package.

        Args:
            package_path: Path to package file
            expected_hash: Expected SHA256 hash (hex string)

        Returns:
            True if hash matches

        Raises:
            VerificationError: If file not found or hash mismatch
        """
        if not package_path.exists():
            raise VerificationError(f"Package not found: {package_path}")

        try:
            sha256 = hashlib.sha256()
            with open(package_path, 'rb') as f:
                while chunk := f.read(self.CHUNK_SIZE):
                    sha256.update(chunk)

            actual_hash = sha256.hexdigest()

            if actual_hash.lower() != expected_hash.lower():
                logger.error(
                    f"Hash mismatch: expected {expected_hash[:16]}..., "
                    f"got {actual_hash[:16]}..."
                )
                raise VerificationError("Package hash verification failed")

            logger.info("Package hash verified successfully")
            return True

        except VerificationError:
            raise
        except Exception as e:
            raise VerificationError(f"Error verifying hash: {e}")

    def extract_package(self, package_path: Path) -> Path:
        """
        Extract tar.gz package to staging directory.

        Args:
            package_path: Path to package file

        Returns:
            Path to extracted directory

        Raises:
            ExtractionError: If extraction fails
        """
        if not package_path.exists():
            raise ExtractionError(f"Package not found: {package_path}")

        try:
            # Clean staging directory
            if self.staging_dir.exists():
                shutil.rmtree(self.staging_dir)
            self.staging_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Extracting {package_path.name} to {self.staging_dir}")

            with tarfile.open(package_path, 'r:gz') as tar:
                # Security: check for path traversal
                for member in tar.getmembers():
                    if member.name.startswith('/') or '..' in member.name:
                        raise ExtractionError(
                            f"Unsafe path in archive: {member.name}"
                        )

                tar.extractall(self.staging_dir)

            logger.info("Package extracted successfully")
            return self.staging_dir

        except tarfile.TarError as e:
            raise ExtractionError(f"Invalid tar.gz file: {e}")
        except ExtractionError:
            raise
        except Exception as e:
            raise ExtractionError(f"Extraction failed: {e}")

    def validate_package_structure(self, extract_dir: Path) -> Tuple[bool, str]:
        """
        Validate that extracted package has required structure.

        Args:
            extract_dir: Path to extracted package

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not extract_dir.exists():
            return False, f"Extract directory not found: {extract_dir}"

        # Check for required files
        missing = []
        for required in self.REQUIRED_FILES:
            if not (extract_dir / required).exists():
                missing.append(required)

        if missing:
            return False, f"Missing required files: {', '.join(missing)}"

        # Check update.sh is executable or we can make it so
        update_script = extract_dir / "update.sh"
        if not update_script.exists():
            return False, "update.sh not found"

        # Verify it's a valid shell script (basic check)
        try:
            with open(update_script, 'r') as f:
                first_line = f.readline()
                if not first_line.startswith('#!'):
                    logger.warning("update.sh missing shebang, will use /bin/bash")
        except Exception as e:
            return False, f"Cannot read update.sh: {e}"

        logger.info("Package structure validated successfully")
        return True, ""

    def get_package_version(self, extract_dir: Path) -> Optional[str]:
        """
        Read version from extracted VERSION file.

        Args:
            extract_dir: Path to extracted package

        Returns:
            Version string or None if not found
        """
        version_file = extract_dir / "VERSION"
        try:
            if version_file.exists():
                return version_file.read_text().strip()
        except Exception as e:
            logger.error(f"Error reading VERSION file: {e}")
        return None

    def cleanup_staging(self) -> bool:
        """
        Remove staging directory.

        Returns:
            True if cleanup successful
        """
        try:
            if self.staging_dir.exists():
                shutil.rmtree(self.staging_dir)
                logger.debug("Staging directory cleaned up")
            return True
        except Exception as e:
            logger.warning(f"Error cleaning staging directory: {e}")
            return False

    def cleanup_download(self, version: str) -> bool:
        """
        Remove downloaded package.

        Args:
            version: Package version to remove

        Returns:
            True if cleanup successful
        """
        try:
            package_path = self.get_package_path(version)
            if package_path.exists():
                package_path.unlink()
                logger.debug(f"Removed downloaded package: {package_path.name}")
            return True
        except Exception as e:
            logger.warning(f"Error removing package: {e}")
            return False

    def cleanup_all(self) -> bool:
        """
        Remove all downloaded packages and staging.

        Returns:
            True if cleanup successful
        """
        success = True

        # Clean staging
        if not self.cleanup_staging():
            success = False

        # Clean downloads
        try:
            if self.download_dir.exists():
                for f in self.download_dir.glob("*.tar.gz"):
                    try:
                        f.unlink()
                    except Exception as e:
                        logger.warning(f"Error removing {f}: {e}")
                        success = False
        except Exception as e:
            logger.warning(f"Error cleaning downloads: {e}")
            success = False

        return success
