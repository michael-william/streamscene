"""Service layer for StreamScene client.

This package contains business logic services that coordinate
between low-level managers and the main application loop.

Services provide:
- Clean separation of concerns
- Testable business logic
- Reusable functionality
- Dependency injection support
"""

from .base import BaseService
from .config_service import ConfigurationService, DeviceConfiguration
from .ota_state import OTAStateManager, OTAStateData, OTAStatus
from .ota_package import OTAPackageHandler, OTAPackageError
from .ota_installer import OTAInstaller, OTAInstallerError
from .ota_service import OTAService, UpdateInfo, UpdateResult

__all__ = [
    'BaseService',
    'ConfigurationService',
    'DeviceConfiguration',
    # OTA components
    'OTAStateManager',
    'OTAStateData',
    'OTAStatus',
    'OTAPackageHandler',
    'OTAPackageError',
    'OTAInstaller',
    'OTAInstallerError',
    'OTAService',
    'UpdateInfo',
    'UpdateResult',
]
