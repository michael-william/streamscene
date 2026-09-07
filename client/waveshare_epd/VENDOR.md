# Vendored: waveshare_epd

This directory is **third-party code copied into this repository**, not a package
installed by pip. Do not add `waveshare-epd` to `client/requirements.txt` - it is
not published on PyPI, and listing it makes pip abort the entire install, which
silently leaves the image with no pillow/requests/qrcode either.

## Provenance

| | |
|---|---|
| Upstream | https://github.com/waveshare/e-Paper |
| Commit | `a794fbc39656b0f93938d1ffb3fdc77eaed9e9fc` (master) |
| Source path | `RaspberryPi_JetsonNano/python/lib/waveshare_epd/` |
| Retrieved | 2026-09-06 |
| License | MIT-style permission notice, retained in each file header |

## What was copied

Only the files needed to drive the 7.3" 7-color panel, not the full 79-file
upstream library (1.2M -> 112K):

| File | Purpose |
|---|---|
| `epd7in3e.py` | Driver for the Waveshare 7.3" E variant (800x480, 7 colors) |
| `epdconfig.py` | Platform GPIO/SPI abstraction; selects the RaspberryPi backend |
| `__init__.py` | Empty, marks the package |
| `DEV_Config_32.so` | Native SPI helper, 32-bit (used on the Pi Zero 2 W armhf image) |
| `DEV_Config_64.so` | Native SPI helper, 64-bit |

Both `.so` files are kept because `epdconfig.py` picks one at runtime based on
the machine word size (see its `DEV_Config_*.so` lookup).

## Runtime requirements

`epdconfig.RaspberryPi.__init__` imports `spidev` and `gpiozero` lazily, so the
package imports fine without them - failures only appear when a display is
actually constructed. Both are in `client/requirements.txt`. SPI must also be
enabled in `/boot/firmware/config.txt` (`dtparam=spi=on`); `build_sd_image.sh`
does this at image build time.

## Adding another panel

Copy the matching `epd*.py` from the same upstream path and commit it here.
Keep this file's commit hash in sync with whatever revision you copy from.

## Updating

Re-copy from upstream and update the commit hash above. There is no automatic
update path - that is the accepted trade for a build that does not depend on
GitHub being reachable.
