"""SIGTERM must cut short the main loop's waits (TimeoutStopSec regression)."""

import signal
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import main


class TestShutdownWaits(unittest.TestCase):
    def setUp(self):
        # Bypass __init__: it touches the display and network hardware
        self.client = object.__new__(main.StreamSceneClient)
        self.client._stop = threading.Event()
        self.client.running = True

    def test_sleep_returns_early_on_signal(self):
        threading.Timer(0.2, self.client._signal_handler, args=(signal.SIGTERM, None)).start()
        t0 = time.monotonic()
        self.assertTrue(self.client._sleep(60))
        self.assertLess(time.monotonic() - t0, 2)
        self.assertFalse(self.client.running)

    def test_sleep_runs_full_time_without_signal(self):
        self.assertFalse(self.client._sleep(0.1))


if __name__ == "__main__":
    unittest.main()
