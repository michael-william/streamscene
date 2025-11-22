#!/usr/bin/env python3
"""Display a test post on the physical device."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from streamscene.core.database import get_session
from streamscene.core.models import Device, Stream, Post
from streamscene.core.streams import create_post

def main():
    """Display test post on device."""
    db = get_session()

    try:
        print("=" * 60)
        print("Display Test Post on Device")
        print("=" * 60)

        # Get the device
        device_uuid = "1c91d1e9-3cc9-44ba-a008-9cdee188d90c"
        device = db.query(Device).filter(Device.device_uuid == device_uuid).first()

        if not device:
            print(f"❌ Device not found: {device_uuid}")
            return

        print(f"\n📱 Device: {device.nickname}")
        print(f"   UUID: {device.device_uuid}")
        print(f"   State: {device.setup_state}")

        # Check current stream
        if device.current_stream_id:
            current_stream = db.query(Stream).filter(Stream.id == device.current_stream_id).first()
            print(f"   Current Stream: {current_stream.name if current_stream else 'Unknown'}")
        else:
            print(f"   Current Stream: None")

        # Get all streams
        streams = db.query(Stream).all()
        print(f"\n📊 Available Streams:")
        for idx, stream in enumerate(streams, 1):
            post_count = db.query(Post).filter(Post.stream_id == stream.id).count()
            is_current = stream.id == device.current_stream_id
            marker = "👉" if is_current else "  "
            print(f"{marker} {idx}. {stream.name} ({post_count} posts)")

        # Prompt user to select stream or use current
        if device.current_stream_id:
            current_stream = db.query(Stream).filter(Stream.id == device.current_stream_id).first()
            stream_choice = current_stream
            print(f"\n✓ Using device's current stream: {current_stream.name}")
        else:
            # Use first stream
            stream_choice = streams[0] if streams else None
            if stream_choice:
                device.current_stream_id = stream_choice.id
                db.commit()
                print(f"\n✓ Set device stream to: {stream_choice.name}")

        if not stream_choice:
            print("❌ No streams available")
            return

        # Get user for post creation
        user = device.user if device.user_id else db.query(User).first()
        if not user:
            print("❌ No user available")
            return

        print(f"\n📝 Creating test post...")
        print(f"   Author: {user.display_name or 'Anonymous'}")
        print(f"   Stream: {stream_choice.name}")

        # Create a visually striking test post (no emojis due to DB encoding)
        test_post = create_post(
            session=db,
            stream_id=stream_choice.id,
            author_id=user.id,
            text_content="Testing new image renderer on E Ink display! This post was generated using PIL with dynamic font sizing.",
            content_type="meme",
            background_name="blue_purple_gradient.png",
            text_color="#FFFFFF",
            outline_color="#000000"
        )
        db.commit()

        print(f"\n✅ Test post created!")
        print(f"   Post ID: {test_post.id}")
        print(f"   Content Type: {test_post.content_type}")
        print(f"   Background: {test_post.background_name}")
        print(f"   Rendered Image: {test_post.processed_image_path}")

        # Check if device will pick it up
        print(f"\n📡 Device Status:")
        print(f"   The device polls for new content every ~60 seconds")
        print(f"   Latest post in stream '{stream_choice.name}' is now the test post")
        print(f"   Device should display it on next content fetch")

        print(f"\n💡 To force immediate update, SSH to device and restart:")
        print(f"   ssh pi@192.168.1.40 'sudo systemctl restart streamscene-client'")

        print("\n" + "=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    from streamscene.core.models import User
    main()
