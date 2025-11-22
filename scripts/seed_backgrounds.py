#!/usr/bin/env python3
"""Seed database with default background images."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from streamscene.core.database import get_session
from streamscene.core.backgrounds import seed_default_backgrounds, get_all_backgrounds
from streamscene.core.models import BackgroundImage

def main():
    """Seed backgrounds."""
    db = get_session()
    try:
        added_count = seed_default_backgrounds(db)
        total_count = db.query(BackgroundImage).count()
        print(f"✓ Seeded {added_count} new background images")
        print(f"Total backgrounds in database: {total_count}")

        # List all backgrounds
        backgrounds = get_all_backgrounds(db, active_only=False)
        print("\nAvailable backgrounds:")
        for bg in backgrounds:
            status = "✓" if bg.is_active else "✗"
            print(f"  {status} {bg.display_name} ({bg.filename})")
    except Exception as e:
        print(f"✗ Error seeding backgrounds: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()
