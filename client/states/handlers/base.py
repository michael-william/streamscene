"""Base infrastructure for state handlers.

Provides context and utilities for state handling logic.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class DeviceContext:
    """Context object containing all dependencies for state handlers.

    This allows state handlers to access services and components without
    tight coupling to the main client class.
    """
    # Services (business logic)
    network_service: Any
    config_service: Any
    setup_service: Any

    # Managers (low-level operations)
    network_manager: Any
    setup_manager: Any

    # API and rendering
    api_client: Any
    renderer: Any
    display: Any

    # State machine
    state_machine: Any

    # Device info
    device_uuid: str

    def __post_init__(self):
        """Validate that all required dependencies are present."""
        required = [
            'network_service', 'config_service', 'setup_service',
            'network_manager', 'setup_manager',
            'api_client', 'renderer', 'display',
            'state_machine', 'device_uuid'
        ]

        for attr in required:
            if getattr(self, attr) is None:
                raise ValueError(f"DeviceContext missing required dependency: {attr}")


class StateHandlerResult:
    """Result of state handler execution.

    Encapsulates state transition decisions and any data to pass forward.
    """

    def __init__(self,
                 success: bool = True,
                 next_state: Optional[str] = None,
                 state_data: Optional[dict] = None,
                 error: Optional[str] = None):
        """Initialize result.

        Args:
            success: Whether the state handler executed successfully
            next_state: Next state to transition to (if any)
            state_data: Data to pass to next state
            error: Error message if handler failed
        """
        self.success = success
        self.next_state = next_state
        self.state_data = state_data or {}
        self.error = error

    def __bool__(self):
        """Allow using result in boolean context (if result: ...)."""
        return self.success
