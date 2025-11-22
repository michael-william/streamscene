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
from .network_service import NetworkService, NetworkStatus
from .config_service import ConfigurationService, DeviceConfiguration
from .setup_service import SetupService, NetworkCheckResult, RegistrationResult

__all__ = [
    'BaseService',
    'NetworkService',
    'NetworkStatus',
    'ConfigurationService',
    'DeviceConfiguration',
    'SetupService',
    'NetworkCheckResult',
    'RegistrationResult',
]
