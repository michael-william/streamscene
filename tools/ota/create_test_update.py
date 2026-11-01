#!/usr/bin/env python3
"""Create a test OTA update package for testing the OTA system.

This script creates a mock update package and adds it to the database
for testing the full OTA update flow.

Usage:
    python create_test_update.py --version 0.0.1-test

This will:
1. Create a test update package (streamscene-update-0.0.1-test.tar.gz)
2. Add an update record to the database with rollout_percentage=100
3. Print the package hash for verification
"""

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from streamscene.core.database import get_session
from streamscene.core.models import DeviceUpdate


def create_update_script(version: str) -> str:
    """Create the update.sh script content."""
    return f'''#!/bin/bash
# StreamScene Test Update Script v{version}
# This is a test update for OTA system verification

set -e

VERSION="{version}"
INSTALL_DIR="/home/pi/streamscene-client"
LOG_FILE="/var/log/streamscene/update-$(date +%Y%m%d-%H%M%S).log"

echo "=====================================" | tee -a "$LOG_FILE"
echo "StreamScene Test Update v$VERSION" | tee -a "$LOG_FILE"
echo "=====================================" | tee -a "$LOG_FILE"
echo "Started at: $(date)" | tee -a "$LOG_FILE"

# Verify we're updating the right directory
if [ ! -d "$INSTALL_DIR" ]; then
    echo "ERROR: Install directory not found: $INSTALL_DIR" | tee -a "$LOG_FILE"
    exit 1
fi

# Copy updated client files
echo "Copying client files..." | tee -a "$LOG_FILE"
cp -r client/* "$INSTALL_DIR/" 2>&1 | tee -a "$LOG_FILE"

# Update VERSION file
echo "$VERSION" > "$INSTALL_DIR/VERSION"
echo "Updated VERSION to $VERSION" | tee -a "$LOG_FILE"

echo "=====================================" | tee -a "$LOG_FILE"
echo "Update completed at: $(date)" | tee -a "$LOG_FILE"
echo "=====================================" | tee -a "$LOG_FILE"

exit 0
'''


def create_test_package(version: str, output_dir: Path) -> tuple[Path, str, int]:
    """
    Create a test update package.

    Args:
        version: Version string (e.g., "0.0.1-test")
        output_dir: Directory to create package in

    Returns:
        Tuple of (package_path, sha256_hash, size_bytes)
    """
    # Create staging directory
    staging_dir = output_dir / f"staging-{version}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True)

    # Create VERSION file
    version_file = staging_dir / "VERSION"
    version_file.write_text(version + "\n")
    print(f"  Created VERSION file: {version}")

    # Create update.sh script
    update_script = staging_dir / "update.sh"
    update_script.write_text(create_update_script(version))
    os.chmod(update_script, 0o755)
    print(f"  Created update.sh script")

    # Create client directory with test file
    client_dir = staging_dir / "client"
    client_dir.mkdir()

    # Copy VERSION file to client dir (simulating a client update)
    (client_dir / "VERSION").write_text(version + "\n")

    # Create a marker file to prove the update worked
    (client_dir / "UPDATE_MARKER.txt").write_text(
        f"This file was added by OTA update v{version}\n"
        f"Installed at: {datetime.now().isoformat()}\n"
    )
    print(f"  Created client files")

    # Create CHANGELOG.md
    changelog = staging_dir / "CHANGELOG.md"
    changelog.write_text(f"""# Changelog v{version}

## Test Update

This is a test OTA update package for verification purposes.

### Changes
- Test update marker file added
- VERSION file updated to {version}

### Testing
This update is safe to install and will not affect device functionality.
""")
    print(f"  Created CHANGELOG.md")

    # Create the tar.gz package
    package_name = f"streamscene-update-{version}.tar.gz"
    package_path = output_dir / package_name

    print(f"  Creating tarball: {package_name}")
    with tarfile.open(package_path, "w:gz") as tar:
        for item in staging_dir.iterdir():
            tar.add(item, arcname=item.name)

    # Calculate hash
    sha256 = hashlib.sha256()
    with open(package_path, 'rb') as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    package_hash = sha256.hexdigest()

    # Get file size
    package_size = package_path.stat().st_size

    # Clean up staging
    shutil.rmtree(staging_dir)

    print(f"  Package created: {package_path}")
    print(f"  SHA256: {package_hash}")
    print(f"  Size: {package_size} bytes")

    return package_path, package_hash, package_size


def add_update_to_database(
    version: str,
    package_path: Path,
    package_hash: str,
    package_size: int,
    rollout_percentage: int = 100,
    is_mandatory: bool = False,
) -> DeviceUpdate:
    """Add update record to database."""
    with get_session() as db:
        # Check if update already exists
        existing = db.query(DeviceUpdate).filter(
            DeviceUpdate.version == version
        ).first()

        if existing:
            print(f"\n  Updating existing record for v{version}")
            existing.package_path = str(package_path)
            existing.package_hash = package_hash
            existing.package_size = package_size
            existing.rollout_percentage = rollout_percentage
            existing.is_mandatory = is_mandatory
            existing.is_active = True
            existing.changelog = f"Test update v{version} for OTA verification"
            db.commit()
            return existing

        # Create new update record
        update = DeviceUpdate(
            id=uuid4(),
            version=version,
            release_date=datetime.now(),
            package_path=str(package_path),
            package_hash=package_hash,
            package_size=package_size,
            changelog=f"Test update v{version} for OTA verification",
            is_active=True,
            is_mandatory=is_mandatory,
            rollout_percentage=rollout_percentage,
            min_version_required=None,
        )
        db.add(update)
        db.commit()
        db.refresh(update)

        print(f"\n  Created database record:")
        print(f"    ID: {update.id}")
        print(f"    Version: {update.version}")
        print(f"    Rollout: {update.rollout_percentage}%")
        print(f"    Mandatory: {update.is_mandatory}")

        return update


def main():
    parser = argparse.ArgumentParser(
        description="Create a test OTA update package"
    )
    parser.add_argument(
        "--version",
        default="0.0.1-test",
        help="Version string for the test update (default: 0.0.1-test)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/var/lib/streamscene/updates"),
        help="Output directory for package (default: /var/lib/streamscene/updates)"
    )
    parser.add_argument(
        "--rollout",
        type=int,
        default=100,
        help="Rollout percentage 0-100 (default: 100)"
    )
    parser.add_argument(
        "--mandatory",
        action="store_true",
        help="Mark update as mandatory"
    )
    parser.add_argument(
        "--skip-db",
        action="store_true",
        help="Skip adding to database (just create package)"
    )

    args = parser.parse_args()

    print(f"\n=== Creating Test OTA Update v{args.version} ===\n")

    # Ensure output directory exists
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Create package
    print("Step 1: Creating update package...")
    package_path, package_hash, package_size = create_test_package(
        args.version, args.output_dir
    )

    if not args.skip_db:
        # Add to database
        print("\nStep 2: Adding to database...")
        add_update_to_database(
            version=args.version,
            package_path=package_path,
            package_hash=package_hash,
            package_size=package_size,
            rollout_percentage=args.rollout,
            is_mandatory=args.mandatory,
        )

    print(f"\n=== Test Update Created Successfully ===")
    print(f"\nPackage: {package_path}")
    print(f"Hash: {package_hash}")
    print(f"\nTo test on device:")
    print(f"  1. Flash SD card with StreamScene image")
    print(f"  2. Register device through web UI")
    print(f"  3. Device will automatically check for updates")
    print(f"  4. Update v{args.version} will be downloaded and installed")
    print(f"  5. Check /home/pi/streamscene-client/UPDATE_MARKER.txt after reboot")


if __name__ == "__main__":
    main()
