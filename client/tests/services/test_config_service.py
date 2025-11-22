"""Unit tests for ConfigurationService."""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import time

import sys
from pathlib import Path

# Add parent directory to path so we can import services
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.config_service import ConfigurationService, DeviceConfiguration


class TestDeviceConfiguration(unittest.TestCase):
    """Test cases for DeviceConfiguration dataclass."""

    def test_from_dict_with_valid_config(self):
        """Test creating DeviceConfiguration from valid dictionary."""
        config_dict = {
            "rotation_enabled": True,
            "rotation_interval": 90,
            "rotation_post_count": 15,
            "extra_field": "ignored"
        }

        config = DeviceConfiguration.from_dict(config_dict)

        self.assertIsNotNone(config)
        self.assertTrue(config.rotation_enabled)
        self.assertEqual(config.rotation_interval, 90)
        self.assertEqual(config.rotation_post_count, 15)
        self.assertEqual(config.raw_config, config_dict)

    def test_from_dict_with_partial_config(self):
        """Test creating DeviceConfiguration with missing fields (uses defaults)."""
        config_dict = {
            "rotation_enabled": True
            # rotation_interval and rotation_post_count missing
        }

        config = DeviceConfiguration.from_dict(config_dict)

        self.assertIsNotNone(config)
        self.assertTrue(config.rotation_enabled)
        self.assertEqual(config.rotation_interval, 60)  # Default
        self.assertEqual(config.rotation_post_count, 10)  # Default

    def test_from_dict_with_none(self):
        """Test creating DeviceConfiguration from None."""
        config = DeviceConfiguration.from_dict(None)
        self.assertIsNone(config)


class TestConfigurationService(unittest.TestCase):
    """Test cases for ConfigurationService."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_api_client = Mock()
        self.service = ConfigurationService(
            api_client=self.mock_api_client,
            refresh_interval=120
        )

    @patch('services.config_service.load_api_key')
    def test_initialize_not_registered(self, mock_load_api_key):
        """Test service initialization when device is not registered."""
        mock_load_api_key.return_value = ""

        result = self.service.initialize()

        self.assertTrue(result)
        # Should not call API if not registered
        self.mock_api_client.get_config.assert_not_called()

    @patch('services.config_service.load_api_key')
    def test_initialize_registered(self, mock_load_api_key):
        """Test service initialization when device is registered."""
        mock_load_api_key.return_value = "test-api-key"
        self.mock_api_client.get_config.return_value = {
            "rotation_enabled": True,
            "rotation_interval": 60,
            "rotation_post_count": 10
        }

        result = self.service.initialize()

        self.assertTrue(result)
        # Should fetch config if registered
        self.mock_api_client.get_config.assert_called_once()

    @patch('services.config_service.load_api_key')
    def test_is_registered_true(self, mock_load_api_key):
        """Test is_registered when API key exists."""
        mock_load_api_key.return_value = "test-api-key"

        result = self.service.is_registered()

        self.assertTrue(result)

    @patch('services.config_service.load_api_key')
    def test_is_registered_false(self, mock_load_api_key):
        """Test is_registered when API key does not exist."""
        mock_load_api_key.return_value = ""

        result = self.service.is_registered()

        self.assertFalse(result)

    @patch('services.config_service.save_api_key')
    def test_save_api_key_to_file(self, mock_save_api_key):
        """Test saving API key to file."""
        mock_save_api_key.return_value = True

        result = self.service.save_api_key_to_file("new-api-key")

        self.assertTrue(result)
        mock_save_api_key.assert_called_once_with("new-api-key")

    @patch('services.config_service.load_api_key')
    def test_fetch_initial_config_not_registered(self, mock_load_api_key):
        """Test fetching initial config when device is not registered."""
        mock_load_api_key.return_value = ""

        result = self.service.fetch_initial_config()

        self.assertIsNone(result)
        self.mock_api_client.get_config.assert_not_called()

    @patch('services.config_service.load_api_key')
    def test_fetch_initial_config_success(self, mock_load_api_key):
        """Test fetching initial config successfully."""
        mock_load_api_key.return_value = "test-api-key"
        self.mock_api_client.get_config.return_value = {
            "rotation_enabled": True,
            "rotation_interval": 90,
            "rotation_post_count": 15
        }

        result = self.service.fetch_initial_config()

        self.assertIsNotNone(result)
        self.assertTrue(result.rotation_enabled)
        self.assertEqual(result.rotation_interval, 90)
        self.assertEqual(result.rotation_post_count, 15)
        self.mock_api_client.get_config.assert_called_once()

    @patch('services.config_service.load_api_key')
    def test_fetch_initial_config_api_failure(self, mock_load_api_key):
        """Test fetching initial config when API returns None."""
        mock_load_api_key.return_value = "test-api-key"
        self.mock_api_client.get_config.return_value = None

        result = self.service.fetch_initial_config()

        self.assertIsNone(result)

    @patch('services.config_service.load_api_key')
    def test_fetch_initial_config_exception(self, mock_load_api_key):
        """Test fetching initial config when API raises exception."""
        mock_load_api_key.return_value = "test-api-key"
        self.mock_api_client.get_config.side_effect = Exception("Network error")

        result = self.service.fetch_initial_config()

        self.assertIsNone(result)

    @patch('services.config_service.load_api_key')
    def test_refresh_if_needed_ttl_not_expired(self, mock_load_api_key):
        """Test refresh when TTL has not expired yet."""
        mock_load_api_key.return_value = "test-api-key"

        # Set up existing config
        self.service.config = DeviceConfiguration.from_dict({
            "rotation_enabled": False,
            "rotation_interval": 60,
            "rotation_post_count": 10
        })
        self.service.last_fetch = time.time()  # Just fetched

        result = self.service.refresh_if_needed()

        # Should return existing config without calling API
        self.assertIsNotNone(result)
        self.assertFalse(result.rotation_enabled)
        self.mock_api_client.get_config.assert_not_called()

    @patch('services.config_service.load_api_key')
    def test_refresh_if_needed_ttl_expired(self, mock_load_api_key):
        """Test refresh when TTL has expired."""
        mock_load_api_key.return_value = "test-api-key"

        # Set up existing config with old timestamp
        self.service.config = DeviceConfiguration.from_dict({
            "rotation_enabled": False,
            "rotation_interval": 60,
            "rotation_post_count": 10
        })
        self.service.last_fetch = time.time() - 200  # 200 seconds ago (> 120s TTL)

        # Mock API returning new config
        self.mock_api_client.get_config.return_value = {
            "rotation_enabled": True,
            "rotation_interval": 90,
            "rotation_post_count": 15
        }

        result = self.service.refresh_if_needed()

        # Should refresh and return new config
        self.assertIsNotNone(result)
        self.assertTrue(result.rotation_enabled)
        self.assertEqual(result.rotation_interval, 90)
        self.mock_api_client.get_config.assert_called_once()

    @patch('services.config_service.load_api_key')
    def test_refresh_if_needed_not_registered(self, mock_load_api_key):
        """Test refresh when device is not registered."""
        mock_load_api_key.return_value = ""

        # Set last fetch to old time
        self.service.last_fetch = time.time() - 200

        result = self.service.refresh_if_needed()

        self.assertIsNone(result)
        self.mock_api_client.get_config.assert_not_called()

    @patch('services.config_service.load_api_key')
    def test_detect_changes_rotation_enabled(self, mock_load_api_key):
        """Test change detection for rotation_enabled."""
        mock_load_api_key.return_value = "test-api-key"

        # Set up old config
        self.service.config = DeviceConfiguration.from_dict({
            "rotation_enabled": False,
            "rotation_interval": 60,
            "rotation_post_count": 10
        })
        self.service.last_fetch = time.time() - 200

        # Mock new config with rotation enabled
        self.mock_api_client.get_config.return_value = {
            "rotation_enabled": True,  # Changed!
            "rotation_interval": 60,
            "rotation_post_count": 10
        }

        self.service.refresh_if_needed()

        # Verify new config applied
        self.assertTrue(self.service.config.rotation_enabled)

    @patch('services.config_service.load_api_key')
    def test_detect_changes_rotation_interval(self, mock_load_api_key):
        """Test change detection for rotation_interval."""
        mock_load_api_key.return_value = "test-api-key"

        # Set up old config
        self.service.config = DeviceConfiguration.from_dict({
            "rotation_enabled": True,
            "rotation_interval": 60,
            "rotation_post_count": 10
        })
        self.service.last_fetch = time.time() - 200

        # Mock new config with different interval
        self.mock_api_client.get_config.return_value = {
            "rotation_enabled": True,
            "rotation_interval": 90,  # Changed!
            "rotation_post_count": 10
        }

        self.service.refresh_if_needed()

        # Verify new config applied
        self.assertEqual(self.service.config.rotation_interval, 90)

    @patch('services.config_service.load_api_key')
    def test_detect_changes_rotation_post_count(self, mock_load_api_key):
        """Test change detection for rotation_post_count."""
        mock_load_api_key.return_value = "test-api-key"

        # Set up old config
        self.service.config = DeviceConfiguration.from_dict({
            "rotation_enabled": True,
            "rotation_interval": 60,
            "rotation_post_count": 10
        })
        self.service.last_fetch = time.time() - 200

        # Mock new config with different post count
        self.mock_api_client.get_config.return_value = {
            "rotation_enabled": True,
            "rotation_interval": 60,
            "rotation_post_count": 15  # Changed!
        }

        self.service.refresh_if_needed()

        # Verify new config applied
        self.assertEqual(self.service.config.rotation_post_count, 15)

    @patch('services.config_service.load_api_key')
    def test_refresh_api_failure_keeps_old_config(self, mock_load_api_key):
        """Test that API failure during refresh keeps old config."""
        mock_load_api_key.return_value = "test-api-key"

        # Set up old config
        old_config = DeviceConfiguration.from_dict({
            "rotation_enabled": True,
            "rotation_interval": 60,
            "rotation_post_count": 10
        })
        self.service.config = old_config
        self.service.last_fetch = time.time() - 200

        # Mock API failure
        self.mock_api_client.get_config.return_value = None

        result = self.service.refresh_if_needed()

        # Should keep old config
        self.assertIsNotNone(result)
        self.assertEqual(result, old_config)

    @patch('services.config_service.load_api_key')
    def test_get_rotation_settings_with_config(self, mock_load_api_key):
        """Test getting rotation settings when config exists."""
        self.service.config = DeviceConfiguration.from_dict({
            "rotation_enabled": True,
            "rotation_interval": 90,
            "rotation_post_count": 15
        })

        enabled, interval, post_count = self.service.get_rotation_settings()

        self.assertTrue(enabled)
        self.assertEqual(interval, 90)
        self.assertEqual(post_count, 15)

    @patch('services.config_service.load_api_key')
    def test_get_rotation_settings_without_config(self, mock_load_api_key):
        """Test getting rotation settings when config does not exist."""
        self.service.config = None

        enabled, interval, post_count = self.service.get_rotation_settings()

        # Should return defaults
        self.assertFalse(enabled)
        self.assertEqual(interval, 60)
        self.assertEqual(post_count, 10)


if __name__ == '__main__':
    unittest.main()
