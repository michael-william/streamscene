"""Base service class for all business logic services."""

from abc import ABC, abstractmethod
from typing import Optional
import logging


class BaseService(ABC):
    """
    Abstract base class for all services.

    Services encapsulate business logic and coordinate between
    low-level components (managers, clients, etc.) and the application.

    Each service should:
    - Have a single, well-defined responsibility
    - Accept dependencies via constructor (dependency injection)
    - Use logging for observability
    - Provide clear error handling
    """

    def __init__(self, logger_name: str):
        """
        Initialize base service.

        Args:
            logger_name: Name for the logger (e.g., "streamscene.network")
        """
        self.logger = logging.getLogger(logger_name)

    @abstractmethod
    def initialize(self) -> bool:
        """
        Initialize the service.

        Called once after construction to perform any setup.
        Should be idempotent - safe to call multiple times.

        Returns:
            True if initialization successful, False otherwise
        """
        pass

    def shutdown(self) -> None:
        """
        Clean up service resources.

        Called when service is no longer needed.
        Default implementation does nothing - override if cleanup needed.
        """
        pass
