"""Unit tests for OTA Update components."""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.ota_state import OTAStateManager, OTAStateData, OTAStatus
from services.ota_package import (
    OTAPackageHandler,
    OTAPackageError,
    VerificationError,
    ExtractionError,
)
from services.ota_installer import (
    OTAInstaller,
    BackupError,
    InstallError,
    RollbackError,
)
from services.ota_service import OTAService, UpdateInfo, UpdateResult


class TestOTAStateManager(unittest.TestCase):
    """Test cases for OTAStateManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.state_file = Path(self.temp_dir) / "test_state.json"
        self.manager = OTAStateManager(state_file=self.state_file)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_no_file(self):
        """Test loading state when file doesn't exist."""
        state = self.manager.load()
        self.assertEqual(state.current_status, OTAStatus.IDLE.value)
        self.assertIsNone(state.update_id)

    def test_save_and_load(self):
        """Test saving and loading state."""
        state = OTAStateData(
            current_status=OTAStatus.DOWNLOADING.value,
            update_id="test-update-id",
            update_version="1.2.3",
            download_progress=50,
        )

        self.assertTrue(self.manager.save(state))

        # Load fresh
        self.manager._state = None
        loaded = self.manager.load()

        self.assertEqual(loaded.current_status, OTAStatus.DOWNLOADING.value)
        self.assertEqual(loaded.update_id, "test-update-id")
        self.assertEqual(loaded.update_version, "1.2.3")
        self.assertEqual(loaded.download_progress, 50)

    def test_load_corrupted_file(self):
        """Test loading state from corrupted file."""
        # Write invalid JSON
        with open(self.state_file, 'w') as f:
            f.write("not valid json {{{")

        state = self.manager.load()

        # Should return default state
        self.assertEqual(state.current_status, OTAStatus.IDLE.value)

    def test_reset(self):
        """Test resetting state to idle."""
        # Set some state
        self.manager.start_update("id", "1.0.0", "hash", 1000)

        # Reset
        state = self.manager.reset()

        self.assertEqual(state.current_status, OTAStatus.IDLE.value)
        self.assertIsNone(state.update_id)

    def test_is_update_in_progress(self):
        """Test update in progress detection."""
        self.assertFalse(self.manager.is_update_in_progress())

        self.manager.set_status(OTAStatus.DOWNLOADING)
        self.assertTrue(self.manager.is_update_in_progress())

        self.manager.set_status(OTAStatus.IDLE)
        self.assertFalse(self.manager.is_update_in_progress())

    def test_pending_verification(self):
        """Test pending verification detection."""
        self.assertIsNone(self.manager.get_pending_verification())

        # Start and complete an update to pending state
        self.manager.start_update("update-123", "2.0.0", "hash", 1000)
        self.manager.mark_pending_verification("/backup/path")

        pending = self.manager.get_pending_verification()

        self.assertIsNotNone(pending)
        self.assertEqual(pending["update_id"], "update-123")
        self.assertEqual(pending["update_version"], "2.0.0")
        self.assertEqual(pending["backup_path"], "/backup/path")

    def test_start_update(self):
        """Test starting update tracking."""
        result = self.manager.start_update(
            update_id="upd-456",
            version="1.5.0",
            package_hash="abc123",
            package_size=5000,
            is_mandatory=True,
        )

        self.assertTrue(result)

        state = self.manager.load()
        self.assertEqual(state.current_status, OTAStatus.DOWNLOADING.value)
        self.assertEqual(state.update_id, "upd-456")
        self.assertEqual(state.update_version, "1.5.0")
        self.assertTrue(state.is_mandatory)

    def test_download_progress(self):
        """Test download progress updates."""
        self.manager.start_update("id", "1.0.0", "hash", 1000)

        self.manager.update_download_progress(25)
        self.assertEqual(self.manager.load().download_progress, 25)

        self.manager.update_download_progress(75)
        self.assertEqual(self.manager.load().download_progress, 75)

        # Test bounds
        self.manager.update_download_progress(150)
        self.assertEqual(self.manager.load().download_progress, 100)

        self.manager.update_download_progress(-10)
        self.assertEqual(self.manager.load().download_progress, 0)

    def test_mark_completed(self):
        """Test marking update as completed."""
        self.manager.start_update("id", "1.0.0", "hash", 1000)
        self.manager.mark_pending_verification("/backup")

        result = self.manager.mark_completed()

        self.assertTrue(result)
        self.assertEqual(self.manager.get_status(), OTAStatus.IDLE)

    def test_mark_failed(self):
        """Test marking update as failed with error history."""
        self.manager.start_update("id", "1.0.0", "hash", 1000)

        self.manager.mark_failed("Download timeout")

        state = self.manager.load()
        self.assertEqual(state.current_status, OTAStatus.FAILED.value)
        self.assertEqual(len(state.error_history), 1)
        self.assertEqual(state.error_history[0]["error"], "Download timeout")

    def test_should_check_for_updates(self):
        """Test update check timing."""
        # Should check if never checked
        self.assertTrue(self.manager.should_check_for_updates())

        # Update last check
        self.manager.update_last_check()

        # Should not check immediately after
        self.assertFalse(self.manager.should_check_for_updates())


class TestOTAPackageHandler(unittest.TestCase):
    """Test cases for OTAPackageHandler."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.download_dir = Path(self.temp_dir) / "downloads"
        self.staging_dir = Path(self.temp_dir) / "staging"

        self.handler = OTAPackageHandler(
            download_dir=self.download_dir,
            staging_dir=self.staging_dir,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_directories(self):
        """Test directory creation."""
        self.assertFalse(self.download_dir.exists())

        result = self.handler.ensure_directories()

        self.assertTrue(result)
        self.assertTrue(self.download_dir.exists())
        self.assertTrue(self.staging_dir.exists())

    def test_get_package_path(self):
        """Test package path generation."""
        path = self.handler.get_package_path("1.2.3")
        self.assertEqual(path.name, "streamscene-update-1.2.3.tar.gz")

    def test_write_package(self):
        """Test writing package data."""
        data = b"test package data"

        path = self.handler.write_package("1.0.0", data)

        self.assertTrue(path.exists())
        self.assertEqual(path.read_bytes(), data)

    def test_verify_hash_success(self):
        """Test hash verification success."""
        import hashlib

        data = b"test package content"
        expected_hash = hashlib.sha256(data).hexdigest()

        self.handler.ensure_directories()
        path = self.handler.get_package_path("1.0.0")
        path.write_bytes(data)

        result = self.handler.verify_hash(path, expected_hash)
        self.assertTrue(result)

    def test_verify_hash_failure(self):
        """Test hash verification failure."""
        data = b"test package content"
        wrong_hash = "0" * 64

        self.handler.ensure_directories()
        path = self.handler.get_package_path("1.0.0")
        path.write_bytes(data)

        with self.assertRaises(VerificationError):
            self.handler.verify_hash(path, wrong_hash)

    def test_verify_hash_file_not_found(self):
        """Test hash verification with missing file."""
        path = Path("/nonexistent/package.tar.gz")

        with self.assertRaises(VerificationError):
            self.handler.verify_hash(path, "hash")

    def test_validate_package_structure_valid(self):
        """Test package structure validation with valid package."""
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        # Create required files
        (self.staging_dir / "update.sh").write_text("#!/bin/bash\necho test")
        (self.staging_dir / "VERSION").write_text("1.0.0")

        is_valid, error = self.handler.validate_package_structure(self.staging_dir)

        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_validate_package_structure_missing_files(self):
        """Test package structure validation with missing files."""
        self.staging_dir.mkdir(parents=True, exist_ok=True)

        # Only create VERSION, not update.sh
        (self.staging_dir / "VERSION").write_text("1.0.0")

        is_valid, error = self.handler.validate_package_structure(self.staging_dir)

        self.assertFalse(is_valid)
        self.assertIn("update.sh", error)

    def test_get_package_version(self):
        """Test reading version from package."""
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        (self.staging_dir / "VERSION").write_text("2.3.4")

        version = self.handler.get_package_version(self.staging_dir)

        self.assertEqual(version, "2.3.4")

    def test_cleanup_staging(self):
        """Test staging directory cleanup."""
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        (self.staging_dir / "test.txt").write_text("test")

        result = self.handler.cleanup_staging()

        self.assertTrue(result)
        self.assertFalse(self.staging_dir.exists())

    def test_get_download_progress(self):
        """Test download progress calculation."""
        self.handler.ensure_directories()

        # No file yet
        progress = self.handler.get_download_progress("1.0.0", 1000)
        self.assertEqual(progress, 0)

        # Write partial file
        path = self.handler.get_package_path("1.0.0")
        path.write_bytes(b"x" * 500)

        progress = self.handler.get_download_progress("1.0.0", 1000)
        self.assertEqual(progress, 50)

        # Complete file
        path.write_bytes(b"x" * 1000)
        progress = self.handler.get_download_progress("1.0.0", 1000)
        self.assertEqual(progress, 100)


class TestOTAInstaller(unittest.TestCase):
    """Test cases for OTAInstaller."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.install_dir = Path(self.temp_dir) / "install"
        self.backup_dir = Path(self.temp_dir) / "backups"

        # Create mock installation
        self.install_dir.mkdir(parents=True)
        (self.install_dir / "main.py").write_text("print('hello')")
        (self.install_dir / "VERSION").write_text("1.0.0")

        self.installer = OTAInstaller(
            install_dir=self.install_dir,
            backup_dir=self.backup_dir,
        )

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ensure_directories(self):
        """Test directory creation."""
        result = self.installer.ensure_directories()

        self.assertTrue(result)
        self.assertTrue(self.backup_dir.exists())

    def test_create_backup(self):
        """Test backup creation."""
        backup_path = self.installer.create_backup()

        self.assertTrue(backup_path.exists())
        self.assertTrue((backup_path / "main.py").exists())
        self.assertTrue((backup_path / "VERSION").exists())

    def test_create_backup_no_install_dir(self):
        """Test backup with missing install directory."""
        import shutil
        shutil.rmtree(self.install_dir)

        with self.assertRaises(BackupError):
            self.installer.create_backup()

    def test_run_update_script_success(self):
        """Test successful update script execution."""
        staging_dir = Path(self.temp_dir) / "staging"
        staging_dir.mkdir()

        # Create successful update script
        update_script = staging_dir / "update.sh"
        update_script.write_text("#!/bin/bash\necho 'Success'")

        success, output = self.installer.run_update_script(staging_dir)

        self.assertTrue(success)
        self.assertIn("Success", output)

    def test_run_update_script_failure(self):
        """Test failed update script execution."""
        staging_dir = Path(self.temp_dir) / "staging"
        staging_dir.mkdir()

        # Create failing update script
        update_script = staging_dir / "update.sh"
        update_script.write_text("#!/bin/bash\nexit 1")

        success, output = self.installer.run_update_script(staging_dir)

        self.assertFalse(success)

    def test_run_update_script_timeout(self):
        """Test update script timeout."""
        staging_dir = Path(self.temp_dir) / "staging"
        staging_dir.mkdir()

        # Create slow update script
        update_script = staging_dir / "update.sh"
        update_script.write_text("#!/bin/bash\nsleep 10")

        success, output = self.installer.run_update_script(staging_dir, timeout=1)

        self.assertFalse(success)
        self.assertIn("timed out", output)

    def test_rollback(self):
        """Test rollback to backup."""
        # Create backup
        backup_path = self.installer.create_backup()

        # Modify installation
        (self.install_dir / "main.py").write_text("print('modified')")

        # Rollback
        result = self.installer.rollback(backup_path)

        self.assertTrue(result)
        self.assertEqual(
            (self.install_dir / "main.py").read_text(),
            "print('hello')"
        )

    def test_rollback_missing_backup(self):
        """Test rollback with missing backup."""
        fake_backup = Path("/nonexistent/backup")

        with self.assertRaises(RollbackError):
            self.installer.rollback(fake_backup)

    def test_list_backups(self):
        """Test listing backups."""
        # Create multiple backups
        for i in range(3):
            self.installer.create_backup()

        backups = self.installer.list_backups()

        self.assertEqual(len(backups), 3)
        # Should be sorted newest first
        self.assertGreater(
            backups[0].stat().st_mtime,
            backups[2].stat().st_mtime
        )

    def test_cleanup_old_backups(self):
        """Test cleaning up old backups."""
        # Create 5 backups
        for i in range(5):
            self.installer.create_backup()

        # Keep only 2
        removed = self.installer.cleanup_old_backups(keep_count=2)

        self.assertEqual(removed, 3)
        self.assertEqual(len(self.installer.list_backups()), 2)

    def test_verify_installation_success(self):
        """Test installation verification success."""
        is_valid, error = self.installer.verify_installation()

        self.assertTrue(is_valid)
        self.assertEqual(error, "")

    def test_verify_installation_missing_version(self):
        """Test installation verification with missing VERSION."""
        (self.install_dir / "VERSION").unlink()

        is_valid, error = self.installer.verify_installation()

        self.assertFalse(is_valid)
        self.assertIn("VERSION", error)


class TestOTAService(unittest.TestCase):
    """Test cases for OTAService."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

        # Mock API client
        self.mock_api = Mock()

        # Create service with test paths
        with patch('services.ota_service.config') as mock_config:
            mock_config.OTA_STATE_FILE = Path(self.temp_dir) / "state.json"
            mock_config.OTA_DOWNLOAD_DIR = Path(self.temp_dir) / "downloads"
            mock_config.OTA_STAGING_DIR = Path(self.temp_dir) / "staging"
            mock_config.OTA_BACKUP_DIR = Path(self.temp_dir) / "backups"
            mock_config.OTA_INSTALL_DIR = Path(self.temp_dir) / "install"
            mock_config.OTA_MIN_DISK_SPACE = 1000
            mock_config.OTA_INSTALL_TIMEOUT = 60
            mock_config.OTA_BACKUP_RETENTION = 3
            mock_config.OTA_CHECK_INTERVAL = 3600
            mock_config.get_current_version = Mock(return_value="1.0.0")

            self.service = OTAService(api_client=self.mock_api)

            # Create mock install directory
            mock_config.OTA_INSTALL_DIR.mkdir(parents=True)
            (mock_config.OTA_INSTALL_DIR / "VERSION").write_text("1.0.0")
            (mock_config.OTA_INSTALL_DIR / "main.py").write_text("print('test')")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialize(self):
        """Test service initialization."""
        result = self.service.initialize()
        self.assertTrue(result)

    def test_check_for_updates_no_update(self):
        """Test checking for updates when none available."""
        self.mock_api.check_for_updates.return_value = {
            "update_available": False,
            "current_version": "1.0.0",
        }

        result = self.service.check_for_updates()

        self.assertIsNone(result)
        self.mock_api.check_for_updates.assert_called_once()

    def test_check_for_updates_available(self):
        """Test checking for updates when one is available."""
        self.mock_api.check_for_updates.return_value = {
            "update_available": True,
            "update_id": "upd-123",
            "version": "2.0.0",
            "package_hash": "abc123",
            "package_size": 5000,
            "is_mandatory": False,
            "changelog": "Bug fixes",
            "current_version": "1.0.0",
        }

        result = self.service.check_for_updates()

        self.assertIsNotNone(result)
        self.assertEqual(result.version, "2.0.0")
        self.assertEqual(result.update_id, "upd-123")
        self.assertFalse(result.is_mandatory)

    def test_check_for_updates_network_error(self):
        """Test checking for updates with network error."""
        self.mock_api.check_for_updates.return_value = None

        result = self.service.check_for_updates()

        self.assertIsNone(result)

    def test_download_update_success(self):
        """Test successful download."""
        self.service.initialize()

        update_info = UpdateInfo(
            update_id="upd-123",
            version="2.0.0",
            package_hash="abc",
            package_size=100,
            is_mandatory=False,
            changelog="",
            current_version="1.0.0",
        )

        self.mock_api.download_update.return_value = b"package data"
        self.mock_api.report_update_status.return_value = True

        result = self.service.download_update(update_info)

        self.assertTrue(result)
        self.mock_api.download_update.assert_called_once()

    def test_download_update_network_failure(self):
        """Test download with network failure."""
        self.service.initialize()

        update_info = UpdateInfo(
            update_id="upd-123",
            version="2.0.0",
            package_hash="abc",
            package_size=100,
            is_mandatory=False,
            changelog="",
            current_version="1.0.0",
        )

        self.mock_api.download_update.return_value = None
        self.mock_api.report_update_status.return_value = True

        result = self.service.download_update(update_info)

        self.assertFalse(result)

    def test_run_update_cycle_no_update(self):
        """Test update cycle when no update available."""
        self.mock_api.check_for_updates.return_value = {
            "update_available": False,
            "current_version": "1.0.0",
        }

        result = self.service.run_update_cycle()

        self.assertTrue(result.success)
        self.assertFalse(result.update_installed)

    def test_handle_mandatory_update_not_mandatory(self):
        """Test mandatory update check when update is optional."""
        self.mock_api.check_for_updates.return_value = {
            "update_available": True,
            "update_id": "upd-123",
            "version": "2.0.0",
            "package_hash": "abc",
            "package_size": 100,
            "is_mandatory": False,
            "changelog": "",
            "current_version": "1.0.0",
        }

        # Optional update should still trigger full cycle
        # but this test is about the initial mandatory check
        self.mock_api.check_for_updates.return_value = {
            "update_available": False,
            "current_version": "1.0.0",
        }

        result = self.service.handle_mandatory_update()

        self.assertTrue(result.success)
        self.assertFalse(result.update_installed)

    def test_check_pending_verification_none(self):
        """Test pending verification when none exists."""
        result = self.service.check_pending_verification()
        self.assertIsNone(result)

    def test_verify_boot_success(self):
        """Test boot verification success."""
        # No pending verification
        result = self.service.verify_boot_success()
        self.assertTrue(result)


class TestUpdateInfo(unittest.TestCase):
    """Test cases for UpdateInfo dataclass."""

    def test_creation(self):
        """Test UpdateInfo creation."""
        info = UpdateInfo(
            update_id="123",
            version="1.0.0",
            package_hash="abc",
            package_size=1000,
            is_mandatory=True,
            changelog="Test",
            current_version="0.9.0",
        )

        self.assertEqual(info.update_id, "123")
        self.assertEqual(info.version, "1.0.0")
        self.assertTrue(info.is_mandatory)


class TestUpdateResult(unittest.TestCase):
    """Test cases for UpdateResult dataclass."""

    def test_success_no_update(self):
        """Test successful result with no update."""
        result = UpdateResult(success=True, update_installed=False)

        self.assertTrue(result.success)
        self.assertFalse(result.update_installed)
        self.assertIsNone(result.error)

    def test_success_with_update(self):
        """Test successful result with update."""
        result = UpdateResult(
            success=True,
            update_installed=True,
            version="2.0.0",
            needs_reboot=True,
        )

        self.assertTrue(result.success)
        self.assertTrue(result.update_installed)
        self.assertEqual(result.version, "2.0.0")
        self.assertTrue(result.needs_reboot)

    def test_failure(self):
        """Test failure result."""
        result = UpdateResult(
            success=False,
            error="Download failed",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Download failed")


if __name__ == '__main__':
    unittest.main()
