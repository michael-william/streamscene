"""Configuration management service.

Handles device configuration loading, caching, and change detection.
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from config import load_api_key, save_api_key
from services.base import BaseService


@dataclass
class DeviceConfiguration:
    """Device configuration data structure."""
    rotation_enabled: bool = False
    rotation_interval: int = 60
    rotation_post_count: int = 10
    raw_config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, config_dict: Optional[Dict[str, Any]]) -> Optional['DeviceConfiguration']:
        """Create DeviceConfiguration from API response dictionary.

        Args:
            config_dict: Configuration dictionary from API

        Returns:
            DeviceConfiguration instance or None if config_dict is None
        """
        if not config_dict:
            return None

        return cls(
            rotation_enabled=config_dict.get("rotation_enabled", False),
            rotation_interval=config_dict.get("rotation_interval", 60),
            rotation_post_count=config_dict.get("rotation_post_count", 10),
            raw_config=config_dict
        )


class ConfigurationService(BaseService):
    """Service for managing device configuration.

    Responsibilities:
    - Load device configuration from server
    - Cache configuration with TTL
    - Detect and log configuration changes
    - Manage API key persistence
    """

    def __init__(
        self,
        api_client,
        refresh_interval: int = 120
    ):
        """Initialize configuration service.

        Args:
            api_client: API client instance for fetching config
            refresh_interval: Config refresh interval in seconds (default: 120)
        """
        super().__init__("streamscene.config")
        self.api_client = api_client
        self.refresh_interval = refresh_interval

        # Configuration state
        self.config: Optional[DeviceConfiguration] = None
        self.last_fetch: float = 0

    def initialize(self) -> bool:
        """Initialize service and fetch initial configuration.

        Returns:
            True if initialization successful
        """
        self.logger.info("Configuration service initializing...")

        # Fetch initial config if device is registered
        self.fetch_initial_config()

        return True

    def is_registered(self) -> bool:
        """Check if device has API key (is registered).

        Returns:
            True if device has API key
        """
        api_key = load_api_key()
        return bool(api_key)

    def save_api_key_to_file(self, api_key: str) -> bool:
        """Save API key to persistent storage.

        Args:
            api_key: API key to save

        Returns:
            True if saved successfully
        """
        return save_api_key(api_key)

    def fetch_initial_config(self) -> Optional[DeviceConfiguration]:
        """Fetch device configuration on startup if device is registered.

        This loads rotation settings and other config from the server.
        Config is refreshed periodically via refresh_if_needed().

        Returns:
            DeviceConfiguration if successful, None otherwise
        """
        # Only fetch config if device has API key (is registered)
        if not self.is_registered():
            self.logger.debug("Skipping config fetch (device not registered yet)")
            return None

        self.logger.info("Fetching device configuration...")

        try:
            config_dict = self.api_client.get_config()
            self.last_fetch = time.time()

            if not config_dict:
                self.logger.warning("Failed to fetch device configuration")
                return None

            # Convert to DeviceConfiguration
            self.config = DeviceConfiguration.from_dict(config_dict)

            if self.config:
                self.logger.info(f"Rotation enabled: {self.config.rotation_enabled}")
                if self.config.rotation_enabled:
                    self.logger.info(
                        f"Rotation interval: {self.config.rotation_interval}s, "
                        f"Post count: {self.config.rotation_post_count}"
                    )

            return self.config

        except Exception as e:
            self.logger.error(f"Error fetching configuration: {e}")
            return None

    def refresh_if_needed(self) -> Optional[DeviceConfiguration]:
        """Refresh device configuration if TTL expired.

        Detects and applies config changes like rotation settings without requiring restart.
        Returns current config if refresh not needed.

        Returns:
            DeviceConfiguration (current or refreshed) or None if refresh failed
        """
        # Check if it's time to refresh config
        time_since_last_fetch = time.time() - self.last_fetch
        if time_since_last_fetch < self.refresh_interval:
            # Not time yet, return current config
            return self.config

        # Only refresh if device is registered
        if not self.is_registered():
            return None

        self.logger.debug(
            f"Refreshing configuration (last fetch: {int(time_since_last_fetch)}s ago)"
        )

        try:
            # Store old config for comparison
            old_config = self.config

            # Fetch new config
            new_config_dict = self.api_client.get_config()
            if not new_config_dict:
                self.logger.warning("Failed to refresh configuration")
                return self.config  # Keep old config

            # Update config and timestamp
            new_config = DeviceConfiguration.from_dict(new_config_dict)
            self.config = new_config
            self.last_fetch = time.time()

            # Detect and log changes
            changes_detected = self._detect_changes(old_config, new_config)

            if not changes_detected:
                self.logger.debug("No changes detected")
            else:
                self.logger.info("Configuration refreshed with changes")

            return self.config

        except Exception as e:
            self.logger.error(f"Error refreshing configuration: {e}")
            return self.config  # Keep old config on error

    def _detect_changes(
        self,
        old_config: Optional[DeviceConfiguration],
        new_config: Optional[DeviceConfiguration]
    ) -> bool:
        """Detect and log configuration changes.

        Args:
            old_config: Previous configuration
            new_config: New configuration

        Returns:
            True if changes were detected
        """
        if not old_config or not new_config:
            return False

        changes_detected = False

        # Check rotation_enabled change
        if old_config.rotation_enabled != new_config.rotation_enabled:
            self.logger.info(
                f"Rotation mode changed: {old_config.rotation_enabled} → {new_config.rotation_enabled}"
            )
            changes_detected = True

        # Check rotation_interval change
        if old_config.rotation_interval != new_config.rotation_interval:
            self.logger.info(
                f"Rotation interval changed: {old_config.rotation_interval}s → {new_config.rotation_interval}s"
            )
            changes_detected = True

        # Check rotation_post_count change
        if old_config.rotation_post_count != new_config.rotation_post_count:
            self.logger.info(
                f"Rotation post count changed: {old_config.rotation_post_count} → {new_config.rotation_post_count}"
            )
            changes_detected = True

        return changes_detected

    def get_rotation_settings(self) -> tuple[bool, int, int]:
        """Get current rotation settings.

        Returns:
            Tuple of (enabled, interval, post_count)
        """
        if not self.config:
            return (False, 60, 10)  # Default values

        return (
            self.config.rotation_enabled,
            self.config.rotation_interval,
            self.config.rotation_post_count
        )
