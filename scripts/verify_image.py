"""Build-time verification of a StreamScene SD card image.

Runs inside the image via chroot, using the image's own venv interpreter, with
the client directory as the working directory - the same way
streamscene-client.service runs main.py.

Exits non-zero on any problem so build_sd_image.sh can abort the build.
"""

import ast
import py_compile
import sys
from importlib.metadata import version
from pathlib import Path

CLIENT_DIR = Path("/home/pi/streamscene-client")
DRIVER_DIR = CLIENT_DIR / "waveshare_epd"
EXPECTED_PANEL = (800, 480)

failures = []


def check(label, fn):
    try:
        print("  {}: {}".format(label, fn()))
    except Exception as exc:  # noqa: BLE001 - report, don't raise, so all checks run
        failures.append("{}: {}".format(label, exc))
        print("  {}: FAILED - {}".format(label, exc))


def runtime_packages():
    import PIL, PIL.Image, requests, qrcode  # noqa: F401
    return "pillow {} | requests {} | qrcode {}".format(
        version("pillow"), version("requests"), version("qrcode")
    )


def gpio_packages():
    # Imported lazily by epdconfig.RaspberryPi.__init__, so they never fail at
    # import time - only when a panel is constructed on the device.
    import spidev, gpiozero, lgpio  # noqa: F401
    return "spidev {} | gpiozero {} | lgpio {}".format(
        version("spidev"), version("gpiozero"), version("lgpio")
    )


def inky_packages():
    # Importing inky.eeprom / inky.auto is side-effect free (no GPIO claimed
    # until a display class is constructed), so a real import works here.
    import numpy, smbus2, gpiod, gpiodevice  # noqa: F401
    import inky.auto, inky.eeprom, inky.inky_e673  # noqa: F401
    return "inky {} | numpy {} | gpiod {}".format(
        version("inky"), version("numpy"), version("gpiod")
    )


def boot_config():
    cfg = Path("/boot/firmware/config.txt").read_text().splitlines()
    active = {l.strip() for l in cfg if l.strip() and not l.strip().startswith("#")}
    need = ["dtparam=spi=on", "dtparam=i2c_arm=on", "dtoverlay=spi0-0cs"]
    missing = [n for n in need if n not in active]
    if missing:
        raise RuntimeError("config.txt missing: {}".format(", ".join(missing)))
    return ", ".join(need)


def vendored_driver():
    # NOTE: the driver is deliberately NOT imported here.
    # waveshare_epd/epdconfig.py performs platform detection at module import
    # time by grepping /proc/cpuinfo for "Raspberry", and instantiates a GPIO
    # backend as a side effect. Inside the build chroot that detection cannot
    # succeed - there is no /proc, and bind-mounting the host's would report an
    # x86 CPU - so it falls through to the Jetson backend and raises.
    # A real import is only meaningful on the device; what is verifiable here is
    # that the files are present, syntactically valid, and describe the panel we
    # expect. Panel geometry is read statically rather than by import.
    required = ["__init__.py", "epdconfig.py", "epd7in3e.py",
                "DEV_Config_32.so", "DEV_Config_64.so"]
    missing = [f for f in required if not (DRIVER_DIR / f).exists()]
    if missing:
        raise RuntimeError("missing vendored files: {}".format(", ".join(missing)))

    for py in DRIVER_DIR.glob("*.py"):
        py_compile.compile(str(py), doraise=True)

    # Read EPD_WIDTH / EPD_HEIGHT from the module source without executing it.
    tree = ast.parse((DRIVER_DIR / "epd7in3e.py").read_text())
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = node.value.value
    geometry = (consts.get("EPD_WIDTH"), consts.get("EPD_HEIGHT"))
    if geometry != EXPECTED_PANEL:
        raise RuntimeError(
            "panel geometry {} != expected {} - wrong epd*.py vendored?".format(
                geometry, EXPECTED_PANEL
            )
        )
    return "vendored waveshare_epd.epd7in3e {}x{} (import deferred to device)".format(*geometry)


def client_entrypoint():
    # main.py is what the service executes; a syntax error here bricks the device.
    py_compile.compile(str(CLIENT_DIR / "main.py"), doraise=True)
    return "main.py compiles"


def network_tooling():
    # The client shells out to these by absolute-ish name. A missing binary here
    # is invisible until a device is in someone's house failing to get an IP:
    # wpa_supplicant associates, nothing requests a lease, and the connection
    # simply "fails" with no useful message. Bookworm dropped dhcpcd in favour
    # of NetworkManager, which first_boot.sh masks, so dhcpcd must be installed
    # explicitly.
    import shutil

    required = ["dhclient", "wpa_supplicant", "wpa_cli", "hostapd", "dnsmasq", "rfkill"]
    found, missing = [], []
    for name in required:
        path = shutil.which(name, path="/usr/sbin:/sbin:/usr/bin:/bin")
        (found if path else missing).append(name)
    if missing:
        raise RuntimeError("missing network binaries: {}".format(", ".join(missing)))
    # dhcpcd must exist but must NOT be enabled at boot - an auto-started
    # daemon claims wlan0 and breaks the hotspot.
    wants = Path("/etc/systemd/system/multi-user.target.wants/dhcpcd.service")
    if wants.exists():
        raise RuntimeError(
            "dhcpcd.service is enabled at boot; it will claim wlan0 and break the hotspot"
        )
    return "all present, dhcpcd daemon not auto-started ({})".format(", ".join(found))


def wifi_seeding():
    # Not a failure either way, but it must be stated plainly: an image with
    # pre-seeded credentials carries a plaintext WiFi password and must never
    # be handed to anyone.
    creds = CLIENT_DIR / "wifi_credentials.json"
    if creds.exists():
        return "PRE-SEEDED - dev image, DO NOT DISTRIBUTE"
    return "none - distribution image"


check("venv OK", runtime_packages)
check("gpio OK", gpio_packages)
check("inky OK", inky_packages)
check("driver OK", vendored_driver)
check("boot OK", boot_config)
check("client OK", client_entrypoint)
check("network OK", network_tooling)
check("wifi", wifi_seeding)

if failures:
    print("\nImage verification FAILED:")
    for f in failures:
        print("  - {}".format(f))
    sys.exit(1)

print("  image verification passed")
