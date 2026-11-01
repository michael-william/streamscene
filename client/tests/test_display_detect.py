"""Panel driver selection (Waveshare vs Pimoroni Inky)."""
import sys
import types

import pytest

import config
import display


def _fake_inky(monkeypatch, eeprom_result=None, raises=None):
    eeprom = types.ModuleType("inky.eeprom")

    def read_eeprom():
        if raises:
            raise raises
        return eeprom_result

    eeprom.read_eeprom = read_eeprom
    pkg = types.ModuleType("inky")
    pkg.eeprom = eeprom
    monkeypatch.setitem(sys.modules, "inky", pkg)
    monkeypatch.setitem(sys.modules, "inky.eeprom", eeprom)


class _EE:
    def get_variant(self):
        return "Spectra 6 7.3 800 x 480 (E673)"


def test_forced_driver(monkeypatch):
    monkeypatch.setattr(config, "DISPLAY_DRIVER", "inky")
    assert display.detect_eink_driver() == "inky"
    monkeypatch.setattr(config, "DISPLAY_DRIVER", "waveshare")
    assert display.detect_eink_driver() == "waveshare"


def test_auto_finds_inky(monkeypatch):
    monkeypatch.setattr(config, "DISPLAY_DRIVER", "auto")
    _fake_inky(monkeypatch, eeprom_result=_EE())
    assert display.detect_eink_driver() == "inky"


def test_auto_no_eeprom_is_waveshare(monkeypatch):
    monkeypatch.setattr(config, "DISPLAY_DRIVER", "auto")
    _fake_inky(monkeypatch, eeprom_result=None)
    assert display.detect_eink_driver() == "waveshare"


def test_auto_probe_error_is_waveshare(monkeypatch):
    monkeypatch.setattr(config, "DISPLAY_DRIVER", "auto")
    _fake_inky(monkeypatch, raises=FileNotFoundError("/dev/i2c-1"))
    assert display.detect_eink_driver() == "waveshare"


def test_get_display_dispatch(monkeypatch):
    monkeypatch.setattr(display, "EInkDisplay", lambda: "W")
    monkeypatch.setattr(display, "InkyDisplay", lambda: "I")
    monkeypatch.setattr(display, "detect_eink_driver", lambda: "inky")
    assert display.get_display("eink") == "I"
    assert display.get_display("waveshare") == "W"
    with pytest.raises(ValueError):
        display.get_display("bogus")
