#!/usr/bin/env python3
"""Create default background images for Meme It posts."""

from PIL import Image, ImageDraw, ImageFilter
import random

DISPLAY_WIDTH = 800
DISPLAY_HEIGHT = 480
BACKGROUNDS_DIR = "/root/streamscene/backgrounds"

def create_solid_background(color, filename):
    """Create a solid color background."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), color)
    img.save(f"{BACKGROUNDS_DIR}/{filename}")
    print(f"Created {filename}")

def create_gradient_background(color1, color2, filename, vertical=False):
    """Create a gradient background."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT))
    draw = ImageDraw.Draw(img)

    if vertical:
        for y in range(DISPLAY_HEIGHT):
            # Interpolate between color1 and color2
            ratio = y / DISPLAY_HEIGHT
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(0, y), (DISPLAY_WIDTH, y)], fill=(r, g, b))
    else:
        for x in range(DISPLAY_WIDTH):
            # Interpolate between color1 and color2
            ratio = x / DISPLAY_WIDTH
            r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
            g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
            b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
            draw.line([(x, 0), (x, DISPLAY_HEIGHT)], fill=(r, g, b))

    img.save(f"{BACKGROUNDS_DIR}/{filename}")
    print(f"Created {filename}")

def create_pattern_background(filename):
    """Create a subtle pattern background."""
    img = Image.new("RGB", (DISPLAY_WIDTH, DISPLAY_HEIGHT), (240, 240, 240))
    draw = ImageDraw.Draw(img)

    # Draw diagonal lines pattern
    spacing = 30
    for i in range(-DISPLAY_HEIGHT, DISPLAY_WIDTH, spacing):
        draw.line([(i, 0), (i + DISPLAY_HEIGHT, DISPLAY_HEIGHT)],
                 fill=(220, 220, 220), width=2)

    img.save(f"{BACKGROUNDS_DIR}/{filename}")
    print(f"Created {filename}")

def main():
    """Create all default backgrounds."""

    # Solid colors (good for high contrast with text)
    create_solid_background((255, 255, 255), "white.png")  # White
    create_solid_background((0, 0, 0), "black.png")  # Black
    create_solid_background((41, 128, 185), "blue.png")  # Blue
    create_solid_background((231, 76, 60), "red.png")  # Red
    create_solid_background((46, 204, 113), "green.png")  # Green
    create_solid_background((155, 89, 182), "purple.png")  # Purple
    create_solid_background((230, 126, 34), "orange.png")  # Orange
    create_solid_background((52, 73, 94), "dark_slate.png")  # Dark slate

    # Gradients (aesthetically pleasing)
    create_gradient_background((41, 128, 185), (142, 68, 173), "blue_purple_gradient.png", vertical=True)
    create_gradient_background((46, 204, 113), (52, 152, 219), "green_blue_gradient.png", vertical=True)
    create_gradient_background((241, 196, 15), (230, 126, 34), "yellow_orange_gradient.png", vertical=True)
    create_gradient_background((231, 76, 60), (192, 57, 43), "red_gradient.png", vertical=True)

    # Pattern backgrounds
    create_pattern_background("pattern_lines.png")

    print("\nAll default backgrounds created successfully!")

if __name__ == "__main__":
    main()
