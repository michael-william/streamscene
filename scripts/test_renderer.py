#!/usr/bin/env python3
"""Test the PIL image renderer with various scenarios."""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PIL import Image, ImageDraw
from streamscene.core.image_renderer import ImageRenderer

# Create test output directory
OUTPUT_DIR = Path("/root/streamscene/test_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Create test images directory
TEST_IMAGES_DIR = Path("/root/streamscene/test_images")
TEST_IMAGES_DIR.mkdir(exist_ok=True)


def create_test_images():
    """Create test images with different orientations."""

    # Landscape image (800x450)
    landscape = Image.new("RGB", (800, 450), (100, 150, 200))
    draw = ImageDraw.Draw(landscape)
    draw.text((400, 225), "LANDSCAPE", fill="white", anchor="mm")
    draw.rectangle([50, 50, 750, 400], outline="white", width=5)
    landscape.save(TEST_IMAGES_DIR / "landscape.jpg", "JPEG")
    print(f"✓ Created landscape image (800x450)")

    # Portrait image (450x800)
    portrait = Image.new("RGB", (450, 800), (200, 100, 150))
    draw = ImageDraw.Draw(portrait)
    draw.text((225, 400), "PORTRAIT", fill="white", anchor="mm")
    draw.rectangle([50, 50, 400, 750], outline="white", width=5)
    portrait.save(TEST_IMAGES_DIR / "portrait.jpg", "JPEG")
    print(f"✓ Created portrait image (450x800)")

    # Square image (600x600)
    square = Image.new("RGB", (600, 600), (150, 200, 100))
    draw = ImageDraw.Draw(square)
    draw.text((300, 300), "SQUARE", fill="white", anchor="mm")
    draw.rectangle([50, 50, 550, 550], outline="white", width=5)
    square.save(TEST_IMAGES_DIR / "square.jpg", "JPEG")
    print(f"✓ Created square image (600x600)")


def test_meme_posts():
    """Test meme post rendering with various backgrounds and text lengths."""
    renderer = ImageRenderer()

    test_cases = [
        {
            "name": "meme_short_white",
            "background": "white.png",
            "text": "Short text",
            "text_color": (0, 0, 0),
            "outline_color": (255, 255, 255),
        },
        {
            "name": "meme_medium_blue",
            "background": "blue.png",
            "text": "This is a medium length message that should wrap nicely across multiple lines.",
            "text_color": (255, 255, 255),
            "outline_color": (0, 0, 0),
        },
        {
            "name": "meme_long_gradient",
            "background": "blue_purple_gradient.png",
            "text": "This is a much longer message with exactly 160 characters to test the maximum length allowed by the system and ensure proper font sizing and wrapping!",
            "text_color": (255, 255, 255),
            "outline_color": (0, 0, 0),
        },
        {
            "name": "meme_pattern_orange_text",
            "background": "pattern_lines.png",
            "text": "Testing colored text on pattern background with orange color!",
            "text_color": (255, 140, 0),  # Orange
            "outline_color": (0, 0, 0),
        },
        {
            "name": "meme_black_bg_white_text",
            "background": "black.png",
            "text": "Classic white text on black background - very readable!",
            "text_color": (255, 255, 255),
            "outline_color": (100, 100, 100),
        },
    ]

    for test_case in test_cases:
        print(f"\n📝 Testing: {test_case['name']}")
        background_path = f"/root/streamscene/backgrounds/{test_case['background']}"

        rendered = renderer.render_meme_post(
            background_image_path=background_path,
            text_content=test_case['text'],
            stream_name="Test Stream",
            author_name="Test Author",
            post_date=datetime.now(),
            text_color=test_case['text_color'],
            outline_color=test_case['outline_color']
        )

        output_path = OUTPUT_DIR / f"{test_case['name']}.png"
        rendered.save(output_path, "PNG")
        print(f"   ✓ Saved to {output_path}")
        print(f"   Text length: {len(test_case['text'])} chars")


def test_picture_posts():
    """Test picture post rendering with different orientations."""
    renderer = ImageRenderer()

    test_cases = [
        {
            "name": "picture_landscape_short",
            "image": "landscape.jpg",
            "text": "Beautiful landscape photo!",
            "text_color": (0, 0, 0),
            "outline_color": (255, 255, 255),
        },
        {
            "name": "picture_landscape_long",
            "image": "landscape.jpg",
            "text": "This is a longer caption for a landscape photo that will wrap to multiple lines and appear below the centered image.",
            "text_color": (0, 0, 0),
            "outline_color": (255, 255, 255),
        },
        {
            "name": "picture_portrait_short",
            "image": "portrait.jpg",
            "text": "Portrait with text on the right!",
            "text_color": (0, 0, 0),
            "outline_color": (255, 255, 255),
        },
        {
            "name": "picture_portrait_long",
            "image": "portrait.jpg",
            "text": "This is a longer caption for a portrait photo. The text should appear on the right side in a 40% width column while the image takes up 60% on the left.",
            "text_color": (0, 0, 0),
            "outline_color": (255, 255, 255),
        },
        {
            "name": "picture_square_medium",
            "image": "square.jpg",
            "text": "Square photos are treated like landscape - centered with text below!",
            "text_color": (0, 0, 0),
            "outline_color": (255, 255, 255),
        },
        {
            "name": "picture_landscape_colored_text",
            "image": "landscape.jpg",
            "text": "Testing colored text on photos with blue text and red outline!",
            "text_color": (0, 100, 200),  # Blue
            "outline_color": (200, 0, 0),  # Red
        },
    ]

    for test_case in test_cases:
        print(f"\n📷 Testing: {test_case['name']}")
        image_path = TEST_IMAGES_DIR / test_case['image']

        rendered = renderer.render_picture_post(
            image_path=str(image_path),
            text_content=test_case['text'],
            stream_name="Family Photos",
            author_name="Photographer",
            post_date=datetime.now(),
            text_color=test_case['text_color'],
            outline_color=test_case['outline_color']
        )

        output_path = OUTPUT_DIR / f"{test_case['name']}.png"
        rendered.save(output_path, "PNG")
        print(f"   ✓ Saved to {output_path}")
        print(f"   Image: {test_case['image']}, Text length: {len(test_case['text'])} chars")


def test_edge_cases():
    """Test edge cases and potential issues."""
    renderer = ImageRenderer()

    print("\n🔬 Testing edge cases:")

    # Empty text
    print("\n  Testing empty text...")
    rendered = renderer.render_meme_post(
        background_image_path="/root/streamscene/backgrounds/white.png",
        text_content="",
        stream_name="Empty Test",
        author_name="Tester",
        post_date=datetime.now(),
        text_color=(0, 0, 0),
        outline_color=(255, 255, 255)
    )
    output_path = OUTPUT_DIR / "edge_empty_text.png"
    rendered.save(output_path, "PNG")
    print(f"   ✓ Empty text: {output_path}")

    # Very long words (no spaces)
    print("\n  Testing very long words...")
    long_word = "Supercalifragilisticexpialidocious" * 3
    rendered = renderer.render_meme_post(
        background_image_path="/root/streamscene/backgrounds/blue.png",
        text_content=long_word[:160],  # Truncate to 160
        stream_name="Long Word Test",
        author_name="Tester",
        post_date=datetime.now(),
        text_color=(255, 255, 255),
        outline_color=(0, 0, 0)
    )
    output_path = OUTPUT_DIR / "edge_long_word.png"
    rendered.save(output_path, "PNG")
    print(f"   ✓ Long word: {output_path}")

    # Single character
    print("\n  Testing single character...")
    rendered = renderer.render_meme_post(
        background_image_path="/root/streamscene/backgrounds/red.png",
        text_content="!",
        stream_name="Single Char",
        author_name="Tester",
        post_date=datetime.now(),
        text_color=(255, 255, 255),
        outline_color=(0, 0, 0)
    )
    output_path = OUTPUT_DIR / "edge_single_char.png"
    rendered.save(output_path, "PNG")
    print(f"   ✓ Single character: {output_path}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("PIL Image Renderer Test Suite")
    print("=" * 60)

    print("\n1️⃣  Creating test images...")
    create_test_images()

    print("\n2️⃣  Testing MEME posts...")
    test_meme_posts()

    print("\n3️⃣  Testing PICTURE posts...")
    test_picture_posts()

    print("\n4️⃣  Testing edge cases...")
    test_edge_cases()

    print("\n" + "=" * 60)
    print("✅ All tests complete!")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("=" * 60)

    # List all generated files
    output_files = sorted(OUTPUT_DIR.glob("*.png"))
    print(f"\n📊 Generated {len(output_files)} test images:")
    for f in output_files:
        size_kb = f.stat().st_size / 1024
        print(f"   • {f.name} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
