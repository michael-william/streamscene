#!/bin/bash
# Build an OTA update package from a committed revision.
#
#   scripts/make_ota_package.sh <git-rev> <version> [outdir]
#
# Package contract (client/services/ota_package.py REQUIRED_FILES):
#   update.sh   - run by the client as the service user, cwd = staging dir
#   VERSION     - at the package ROOT (validated before install)
#   client/     - tracked client source, copied over /home/pi/streamscene-client
# Runtime state (venv, API key, device_state.json, wifi_credentials.json) is
# not in the package and is left alone. Boot config and pip packages are not
# changed by OTA - only by flashing a new image.
#
# Prints the INSERT for device_updates. Use min_version_required to keep
# packages away from clients that cannot install them (<=1.3.0 report 1.0.0
# and their backup step fails on lgpio's FIFO).
set -euo pipefail
REV=${1:?git rev}; VER=${2:?version}; OUT=${3:-/var/lib/streamscene/ota-packages}
REPO=$(cd "$(dirname "$0")/.." && pwd)
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
git -C "$REPO" archive "$REV" client | tar -x -C "$W"
rm -rf "$W/client/tests" "$W/client/output"
echo "$VER" > "$W/client/VERSION"
echo "$VER" > "$W/VERSION"
cat > "$W/update.sh" <<'UPD'
#!/bin/bash
set -euo pipefail
DEST=/home/pi/streamscene-client
[ -d "$DEST" ] || { echo "install dir $DEST missing"; exit 1; }
[ -f client/main.py ] || { echo "package has no client/main.py"; exit 1; }
cp -a client/. "$DEST/"
find "$DEST" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "installed $(cat "$DEST/VERSION")"
UPD
chmod +x "$W/update.sh"
mkdir -p "$OUT"
F="$OUT/streamscene-update-$VER.tar.gz"
tar -C "$W" -czf "$F" update.sh VERSION client
chmod 644 "$F"
H=$(sha256sum "$F" | cut -d' ' -f1); S=$(stat -c %s "$F")
# Self-check against the client's own validation rule
tar -tzf "$F" | grep -qx VERSION && tar -tzf "$F" | grep -qx update.sh
echo "package: $F ($S bytes, sha256 $H)"
cat <<SQL
insert into device_updates (id, version, release_date, package_path, package_hash, package_size,
  changelog, is_mandatory, rollout_percentage, min_version_required, is_active, created_at, updated_at)
values (gen_random_uuid(), '$VER', now(), '$F', '$H', $S, '<changelog>', false, 100, '1.4.0', true, now(), now());
SQL
