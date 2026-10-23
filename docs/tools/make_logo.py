"""Draws the app logo as vector shapes, so it is sharp at any size:
  assets/logo.png   1024 px, transparent: the logo in the window header
  assets/icon.ico   transparent: the window icon
  assets/app.ico    on the logo's navy background: the .exe icon
Geometry and colors measured from the original logo artwork.

    python docs/tools/make_logo.py [project folder]
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIZE = 1024                 # logo.png side
SUPERSAMPLE = 4

# In the original's units: a 3x3 diamond grid with 33.4 units between neighbours.
STEP = 33.4
RADIUS = 14.0
LINE = 12.75
CENTER = (176.5, 101.0)
NODES = {"top": (0, -2), "left": (-2, 0), "ul": (-1, -1), "dl": (-1, 1), "mid": (0, 0),
         "bottom": (0, 2), "ur": (1, -1), "dr": (1, 1), "right": (2, 0)}
LINKS = (("left", "ul"), ("left", "dl"), ("ul", "mid"), ("mid", "dr"), ("ur", "right"), ("dr", "right"))
# Left-to-right gradient (x in original units -> color).
GRADIENT = ((110, (44, 179, 230)), (143, (66, 157, 211)), (177, (80, 134, 198)), (210, (90, 115, 182)),
            (243, (102, 102, 174)))


def _gradient_color(x):
    if x <= GRADIENT[0][0]:
        return GRADIENT[0][1]
    for (x1, c1), (x2, c2) in zip(GRADIENT, GRADIENT[1:]):
        if x <= x2:
            f = (x - x1) / (x2 - x1)
            return tuple(round(a + (b - a) * f) for a, b in zip(c1, c2))
    return GRADIENT[-1][1]


def draw_logo(size, margin=0.04):
    big = size * SUPERSAMPLE
    extent = 2 * 2 * STEP + 2 * RADIUS              # the drawing is this wide and tall
    k = big * (1 - 2 * margin) / extent
    ox = big / 2 - CENTER[0] * k
    oy = big / 2 - CENTER[1] * k

    def point(name):
        gx, gy = NODES[name]
        return ox + (CENTER[0] + gx * STEP) * k, oy + (CENTER[1] + gy * STEP) * k

    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    for a, b in LINKS:
        draw.line((point(a), point(b)), fill=255, width=round(LINE * k))
    r = RADIUS * k
    for name in NODES:
        x, y = point(name)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)
    ramp = Image.new("RGB", (big, 1))
    ramp.putdata([_gradient_color((x - ox) / k) for x in range(big)])
    color = ramp.resize((big, big))
    logo = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    logo.paste(color, (0, 0), mask)
    return logo.resize((size, size), Image.LANCZOS)


NAVY = (9, 22, 38)          # the original artwork's background


def draw_tile(size):
    """The logo on a navy rounded square (the .exe icon)."""
    big = size * SUPERSAMPLE
    tile = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, big - 1, big - 1), radius=round(big * 0.22), fill=NAVY)
    tile = tile.resize((size, size), Image.LANCZOS)
    tile.alpha_composite(draw_logo(size, margin=0.17))
    return tile


def _save_ico(path, draw):
    # Each size drawn on its own (not scaled down from one image), so small sizes stay crisp.
    sizes = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
    images = [draw(s) for s in sizes]
    images[-1].save(path, sizes=[(s, s) for s in sizes], append_images=images[:-1])


def main(root=ROOT):
    assets = os.path.join(root, "assets")
    os.makedirs(assets, exist_ok=True)
    draw_logo(SIZE).save(os.path.join(assets, "logo.png"))
    _save_ico(os.path.join(assets, "icon.ico"), lambda s: draw_logo(s, margin=0.02))
    _save_ico(os.path.join(assets, "app.ico"), draw_tile)
    print(f"{assets}: logo.png, icon.ico and app.ico written")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT)
