#!/usr/bin/env python3
"""
Periodic cleanup script for old posts.

Removes posts that exceed each stream's max_history_items limit.
Can be run manually or via cron.

Usage:
    python scripts/cleanup_posts.py

Cron example (run daily at 3am):
    0 3 * * * cd /root/streamscene && /root/streamscene/venv/bin/python scripts/cleanup_posts.py >> /var/log/streamscene-cleanup.log 2>&1
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from streamscene.core.database import get_db_session
from streamscene.core.streams import cleanup_all_streams


def main():
    """Run cleanup on all streams."""
    print("Starting post cleanup...")

    with get_db_session() as session:
        results = cleanup_all_streams(session)
        session.commit()

    if results:
        total = sum(results.values())
        print(f"Cleanup complete: {total} posts deleted across {len(results)} streams")
        for stream_id, count in results.items():
            print(f"  Stream {stream_id}: {count} posts deleted")
    else:
        print("Cleanup complete: No posts needed deletion")


if __name__ == "__main__":
    main()
