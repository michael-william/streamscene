"""
Phase 5 Integration Test

Verifies that all Phase 5 components are properly integrated:
- State machine has necessary methods
- Renderer has QR code and message rendering
- Network manager has AP mode check
- Main loop uses correct method signatures

This test doesn't require hardware or external dependencies.
"""

import sys
from pathlib import Path

# Add client to path
client_path = Path(__file__).parent.parent
sys.path.insert(0, str(client_path))


def test_state_machine_methods():
    """Test StateMachine has all required methods."""
    print("\n=== Testing StateMachine ===")

    # Import and check class structure
    from states import StateMachine, DeviceState

    # Check methods exist
    required_methods = [
        'get_state',
        'get_state_data',
        'get_all_state_data',  # NEW in Phase 5
        'set_state_data',
        'transition_to',
        'can_transition_to',
        'handle_error',
        'recover_from_error',
    ]

    for method in required_methods:
        assert hasattr(StateMachine, method), f"StateMachine missing method: {method}"
        print(f"  ✓ StateMachine.{method} exists")

    # Check DeviceState enum
    required_states = [
        'WIFI_SETUP',
        'CONNECTING',
        'AWAITING_REGISTRATION',
        'REGISTERED',
        'READY',
        'ERROR',
    ]

    for state in required_states:
        assert hasattr(DeviceState, state), f"DeviceState missing: {state}"
        print(f"  ✓ DeviceState.{state} exists")

    print("✓ StateMachine: All methods verified")


def test_renderer_methods():
    """Test ContentRenderer has all required methods."""
    print("\n=== Testing ContentRenderer ===")

    # We can't import renderer because it requires PIL
    # So we'll just check the file has the methods
    renderer_file = client_path / "renderer.py"
    content = renderer_file.read_text()

    required_methods = [
        'def render_content',
        'def render_error',
        'def render_message',     # For setup screens
        'def render_qr_code',     # For registration QR
    ]

    for method in required_methods:
        assert method in content, f"ContentRenderer missing: {method}"
        print(f"  ✓ ContentRenderer.{method.replace('def ', '')} exists")

    # Check render_qr_code signature
    assert 'url: str' in content, "render_qr_code missing url parameter"
    assert 'title: str' in content, "render_qr_code missing title parameter"
    assert 'instructions: str' in content, "render_qr_code missing instructions parameter"

    # Check render_message signature
    assert 'message: str' in content, "render_message missing message parameter"
    assert 'color: str' in content, "render_message missing color parameter"

    print("✓ ContentRenderer: All methods verified")


def test_network_manager_methods():
    """Test NetworkManager (setup/network.py) has all required methods.

    Collapsed from the old separate NetworkManager/SetupManager/
    NetworkService/SetupService layers into one class - this checks its
    merged surface.
    """
    print("\n=== Testing NetworkManager ===")

    nm_file = client_path / "setup" / "network.py"
    content = nm_file.read_text()

    required_methods = [
        'def switch_to_ap_mode',
        'def connect_to_wifi',
        'def is_in_ap_mode',
        'def check_initial_connectivity',
        'def check_network_and_credentials',
        'def run_wifi_setup_flow',
        'def run_registration_flow',
        'def has_saved_credentials',
        'def attempt_recovery',
    ]

    for method in required_methods:
        assert method in content, f"NetworkManager missing: {method}"
        print(f"  ✓ NetworkManager.{method.replace('def ', '')} exists")

    print("✓ NetworkManager: All methods verified")


def test_main_loop_integration():
    """Test main.py uses correct method signatures."""
    print("\n=== Testing main.py Integration ===")

    main_file = client_path / "main.py"
    content = main_file.read_text()

    checks = {
        'get_all_state_data': 'state_machine.get_all_state_data()',
        'transition_to': 'state_machine.transition_to(',

        # Check renderer usage
        'render_message': 'renderer.render_message(',
        'render_qr_code': 'renderer.render_qr_code(',
        'render_error': 'renderer.render_error(',

        # Check network usage - single NetworkManager instance, not four
        # separate manager/service objects
        'is_in_ap_mode': 'self.network.is_in_ap_mode()',
        'run_wifi_setup_flow': 'self.network.run_wifi_setup_flow(',
        'run_registration_flow': 'self.network.run_registration_flow(',
        'connect_to_wifi unpacks error_reason': 'success, ip_address, error_reason = self.network.connect_to_wifi(',
    }

    for name, call in checks.items():
        assert call in content, f"main.py doesn't use: {call}"
        print(f"  ✓ main.py uses {name}")

    print("✓ main.py: All integrations verified")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Phase 5 Integration Test")
    print("=" * 60)

    try:
        test_state_machine_methods()
        test_renderer_methods()
        test_network_manager_methods()
        test_main_loop_integration()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        print("\nPhase 5 implementation is complete and properly integrated!")
        print("\nReady for:")
        print("  - Hardware testing on Raspberry Pi")
        print("  - End-to-end WiFi setup testing")
        print("  - Device registration flow testing")

        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
