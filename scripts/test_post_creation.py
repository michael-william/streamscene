#!/usr/bin/env python3
"""Test the full post creation flow with database."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from streamscene.core.database import get_session
from streamscene.core.streams import create_post, get_stream_by_id
from streamscene.core.models import User, Stream
from streamscene.core.backgrounds import get_all_backgrounds

def main():
    """Test post creation."""
    db = get_session()

    try:
        print("=" * 60)
        print("Post Creation Test")
        print("=" * 60)

        # Get first user and stream for testing
        user = db.query(User).first()
        stream = db.query(Stream).first()

        if not user or not stream:
            print("❌ No user or stream found. Create a user and stream first.")
            return

        print(f"\n📊 Test Setup:")
        print(f"   User: {user.display_name} ({user.id})")
        print(f"   Stream: {stream.name} ({stream.id})")

        # Get available backgrounds
        backgrounds = get_all_backgrounds(db)
        print(f"   Backgrounds: {len(backgrounds)} available")

        # Test 1: Create a meme post
        print("\n1️⃣  Testing MEME post creation...")
        try:
            meme_post = create_post(
                session=db,
                stream_id=stream.id,
                author_id=user.id,
                text_content="This is a test meme post with a blue background!",
                content_type="meme",
                background_name="blue.png",
                text_color="#FFFFFF",
                outline_color="#000000"
            )
            db.commit()
            print(f"   ✓ Created meme post: {meme_post.id}")
            print(f"   ✓ Rendered image: {meme_post.processed_image_path}")
            print(f"   ✓ Background: {meme_post.background_name}")
            print(f"   ✓ Text color: {meme_post.text_color}")
            print(f"   ✓ Outline color: {meme_post.outline_color}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            db.rollback()

        # Test 2: Create a picture post
        print("\n2️⃣  Testing PICTURE post creation...")
        try:
            # Load test image
            test_image_path = Path("/root/streamscene/test_images/landscape.jpg")
            if not test_image_path.exists():
                print(f"   ⚠️  Test image not found, skipping picture test")
            else:
                with open(test_image_path, "rb") as f:
                    image_bytes = f.read()

                picture_post = create_post(
                    session=db,
                    stream_id=stream.id,
                    author_id=user.id,
                    text_content="Beautiful landscape photo from my recent trip!",
                    content_type="picture",
                    image_bytes=image_bytes,
                    text_color="#000000",
                    outline_color="#FFFFFF"
                )
                db.commit()
                print(f"   ✓ Created picture post: {picture_post.id}")
                print(f"   ✓ Uploaded image: {picture_post.image_path}")
                print(f"   ✓ Rendered image: {picture_post.processed_image_path}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            db.rollback()

        # Test 3: Test with maximum text length
        print("\n3️⃣  Testing maximum text length (160 chars)...")
        try:
            max_text = "A" * 160
            long_post = create_post(
                session=db,
                stream_id=stream.id,
                author_id=user.id,
                text_content=max_text,
                content_type="meme",
                background_name="white.png",
                text_color="#000000",
                outline_color="#FFFFFF"
            )
            db.commit()
            print(f"   ✓ Created post with 160 characters")
            print(f"   ✓ Post ID: {long_post.id}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            db.rollback()

        # Test 4: Test validation (text too long)
        print("\n4️⃣  Testing validation (161 chars should fail)...")
        try:
            too_long_text = "A" * 161
            invalid_post = create_post(
                session=db,
                stream_id=stream.id,
                author_id=user.id,
                text_content=too_long_text,
                content_type="meme",
                background_name="white.png"
            )
            print(f"   ❌ Should have raised ValueError!")
        except ValueError as e:
            print(f"   ✓ Correctly rejected: {e}")
            db.rollback()
        except Exception as e:
            print(f"   ❌ Unexpected error: {e}")
            db.rollback()

        # Test 5: Test default background
        print("\n5️⃣  Testing default background (no background_name)...")
        try:
            default_post = create_post(
                session=db,
                stream_id=stream.id,
                author_id=user.id,
                text_content="This should use the default white background",
                content_type="meme",
                # background_name not provided
            )
            db.commit()
            print(f"   ✓ Created post with default background: {default_post.background_name}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            db.rollback()

        # Test 6: Verify rendered files exist
        print("\n6️⃣  Verifying rendered images exist on disk...")
        from streamscene.core.streams import RENDERED_DIR
        rendered_files = list(RENDERED_DIR.glob("*.png"))
        print(f"   ✓ Found {len(rendered_files)} rendered images in cache")
        for f in rendered_files[:5]:  # Show first 5
            size_kb = f.stat().st_size / 1024
            print(f"      • {f.name} ({size_kb:.1f} KB)")

        print("\n" + "=" * 60)
        print("✅ Post creation tests complete!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
