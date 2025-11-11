"""
Device State Machine

Manages device lifecycle states and transitions:
WIFI_SETUP → CONNECTING → AWAITING_REGISTRATION → REGISTERED → READY

State persists to JSON file to survive reboots.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class DeviceState(Enum):
    """Device lifecycle states."""

    WIFI_SETUP = "wifi_setup"                      # No WiFi credentials, running hotspot
    CONNECTING = "connecting"                      # Attempting to connect to WiFi
    AWAITING_REGISTRATION = "awaiting_registration"  # WiFi connected, waiting for user to register device
    REGISTERED = "registered"                      # Device registered with server, not yet operational
    READY = "ready"                                # Operational, displaying content
    ERROR = "error"                                # Recoverable error state

    def __str__(self) -> str:
        return self.value


class StateMachine:
    """
    Device state machine with persistence.

    Manages state transitions and persists current state to disk.
    State survives reboots by loading from JSON file.
    """

    # Valid state transitions (from_state -> [allowed_to_states])
    VALID_TRANSITIONS = {
        DeviceState.WIFI_SETUP: [DeviceState.CONNECTING, DeviceState.ERROR],
        DeviceState.CONNECTING: [DeviceState.AWAITING_REGISTRATION, DeviceState.WIFI_SETUP, DeviceState.ERROR],
        DeviceState.AWAITING_REGISTRATION: [DeviceState.REGISTERED, DeviceState.ERROR],
        DeviceState.REGISTERED: [DeviceState.READY, DeviceState.ERROR],
        DeviceState.READY: [DeviceState.ERROR],  # Can transition to error from ready
        DeviceState.ERROR: [DeviceState.WIFI_SETUP, DeviceState.CONNECTING, DeviceState.AWAITING_REGISTRATION],  # Recovery paths
    }

    def __init__(self, device_uuid: str, state_file: Optional[Path] = None):
        """
        Initialize state machine.

        Args:
            device_uuid: Device UUID for logging
            state_file: Path to state persistence file (default: ./device_state.json)
        """
        self.device_uuid = device_uuid
        self.state_file = state_file or Path.home() / "streamscene-client" / "device_state.json"

        # Ensure state directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load or initialize state
        self.current_state: DeviceState
        self.state_data: Dict[str, Any] = {}
        self.load_state()

    def load_state(self) -> None:
        """
        Load state from disk.

        If state file doesn't exist, initialize to WIFI_SETUP.
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)

                # Restore state
                state_value = data.get("state", "wifi_setup")
                self.current_state = DeviceState(state_value)
                self.state_data = data.get("data", {})

                logger.info(f"[StateMachine] Loaded state: {self.current_state} from {self.state_file}")

            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.error(f"[StateMachine] Error loading state file: {e}. Resetting to WIFI_SETUP.")
                self.current_state = DeviceState.WIFI_SETUP
                self.state_data = {}
        else:
            # First boot - start at WIFI_SETUP
            logger.info(f"[StateMachine] No state file found. Starting at WIFI_SETUP.")
            self.current_state = DeviceState.WIFI_SETUP
            self.state_data = {}
            self.save_state()

    def save_state(self) -> None:
        """Save current state to disk."""
        data = {
            "device_uuid": self.device_uuid,
            "state": self.current_state.value,
            "data": self.state_data,
            "last_updated": datetime.now().isoformat()
        }

        try:
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"[StateMachine] Saved state: {self.current_state} to {self.state_file}")

        except IOError as e:
            logger.error(f"[StateMachine] Error saving state file: {e}")

    def get_state(self) -> DeviceState:
        """Get current state."""
        return self.current_state

    def get_state_data(self, key: str, default: Any = None) -> Any:
        """Get data associated with current state."""
        return self.state_data.get(key, default)

    def set_state_data(self, key: str, value: Any) -> None:
        """Set data associated with current state."""
        self.state_data[key] = value
        self.save_state()

    def can_transition_to(self, new_state: DeviceState) -> bool:
        """
        Check if transition to new_state is valid.

        Args:
            new_state: Target state

        Returns:
            True if transition is allowed
        """
        allowed_states = self.VALID_TRANSITIONS.get(self.current_state, [])
        return new_state in allowed_states

    def transition_to(self, new_state: DeviceState, state_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Transition to new state.

        Args:
            new_state: Target state
            state_data: Optional data to associate with new state

        Returns:
            True if transition successful, False if invalid transition
        """
        if not self.can_transition_to(new_state):
            logger.error(f"[StateMachine] Invalid transition: {self.current_state} -> {new_state}")
            return False

        logger.info(f"[StateMachine] Transitioning: {self.current_state} -> {new_state}")

        old_state = self.current_state
        self.current_state = new_state

        # Update state data
        if state_data:
            self.state_data.update(state_data)

        # Add transition metadata
        self.state_data["previous_state"] = old_state.value
        self.state_data["transitioned_at"] = datetime.now().isoformat()

        # Persist to disk
        self.save_state()

        return True

    def reset_to_wifi_setup(self) -> None:
        """
        Reset state machine to WIFI_SETUP.

        Used for error recovery or manual reset.
        Clears all state data.
        """
        logger.warning(f"[StateMachine] Resetting to WIFI_SETUP from {self.current_state}")

        self.current_state = DeviceState.WIFI_SETUP
        self.state_data = {}
        self.save_state()

    def handle_error(self, error_message: str, recovery_state: Optional[DeviceState] = None) -> None:
        """
        Transition to ERROR state with error details.

        Args:
            error_message: Description of the error
            recovery_state: State to transition to after error handling (default: WIFI_SETUP)
        """
        logger.error(f"[StateMachine] Error: {error_message}")

        # Only transition to ERROR if not already in ERROR
        if self.current_state != DeviceState.ERROR:
            self.transition_to(DeviceState.ERROR, {
                "error_message": error_message,
                "error_state": self.current_state.value,
                "recovery_state": (recovery_state or DeviceState.WIFI_SETUP).value,
                "error_time": datetime.now().isoformat()
            })

    def recover_from_error(self) -> bool:
        """
        Attempt to recover from ERROR state.

        Transitions to recovery_state if specified, otherwise to WIFI_SETUP.

        Returns:
            True if recovery transition successful
        """
        if self.current_state != DeviceState.ERROR:
            logger.warning(f"[StateMachine] Not in ERROR state, cannot recover")
            return False

        recovery_state_value = self.state_data.get("recovery_state", "wifi_setup")

        try:
            recovery_state = DeviceState(recovery_state_value)
        except ValueError:
            logger.warning(f"[StateMachine] Invalid recovery state '{recovery_state_value}', using WIFI_SETUP")
            recovery_state = DeviceState.WIFI_SETUP

        logger.info(f"[StateMachine] Recovering from error to {recovery_state}")

        # Clear error data
        error_data = self.state_data.copy()
        self.state_data = {}

        # Transition to recovery state
        return self.transition_to(recovery_state, {
            "recovered_from_error": error_data.get("error_message"),
            "recovered_at": datetime.now().isoformat()
        })

    def __str__(self) -> str:
        """String representation."""
        return f"StateMachine(state={self.current_state}, device={self.device_uuid})"

    def __repr__(self) -> str:
        """Repr representation."""
        return self.__str__()


def main():
    """Example usage and testing."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Example device UUID
    device_uuid = "test-device-" + datetime.now().strftime("%Y%m%d-%H%M%S")

    print(f"\n=== State Machine Test ===")
    print(f"Device UUID: {device_uuid}\n")

    # Initialize state machine
    sm = StateMachine(device_uuid)
    print(f"Initial state: {sm.get_state()}\n")

    # Test valid transition: WIFI_SETUP -> CONNECTING
    print("Attempting transition: WIFI_SETUP -> CONNECTING")
    success = sm.transition_to(DeviceState.CONNECTING, {"ssid": "TestNetwork", "password": "secret"})
    print(f"Success: {success}, Current state: {sm.get_state()}\n")

    # Test invalid transition: CONNECTING -> READY (skips states)
    print("Attempting invalid transition: CONNECTING -> READY")
    success = sm.transition_to(DeviceState.READY)
    print(f"Success: {success}, Current state: {sm.get_state()}\n")

    # Test valid transition: CONNECTING -> AWAITING_REGISTRATION
    print("Attempting transition: CONNECTING -> AWAITING_REGISTRATION")
    success = sm.transition_to(DeviceState.AWAITING_REGISTRATION)
    print(f"Success: {success}, Current state: {sm.get_state()}\n")

    # Test error handling
    print("Triggering error...")
    sm.handle_error("Test error message", recovery_state=DeviceState.CONNECTING)
    print(f"Current state: {sm.get_state()}")
    print(f"Error data: {sm.state_data}\n")

    # Test recovery
    print("Recovering from error...")
    success = sm.recover_from_error()
    print(f"Success: {success}, Current state: {sm.get_state()}\n")

    # Test state persistence
    print("Testing state persistence...")
    print(f"State file: {sm.state_file}")

    print("\n=== State Machine Test Complete ===\n")


if __name__ == "__main__":
    main()
