"""
Generate the full VoDy font family — vowel-differentiated fonts for phonological dyslexia.

Each variant applies a different visual treatment to vowel glyphs.
"""

import copy
import os
from fontTools.ttLib import TTFont

OUT_DIR = "c:/dev/dysfont/fonts"
INTER_REGULAR = "c:/dev/dysfont/Inter-Regular.ttf"

VOWELS_LOWER = list("aeiou")
VOWELS_UPPER = list("AEIOU")
VOWELS = VOWELS_LOWER + VOWELS_UPPER


def get_vowel_glyphs(font):
    """Return list of (char, glyph_name) for all vowels found in the font."""
    cmap = font.getBestCmap()
    result = []
    for ch in VOWELS:
        cp = ord(ch)
        if cp in cmap:
            result.append((ch, cmap[cp]))
    return result


def rename_font(font, new_name):
    """Replace the font family name and add credit metadata."""
    name_table = font["name"]
    for record in name_table.names:
        try:
            s = record.toUnicode()
        except Exception:
            continue
        for old in ["Inter", "Arial"]:
            if old in s:
                s = s.replace(old, new_name)
        record.string = s

    # Add/overwrite credit fields (nameID reference):
    #   9  = Designer
    #   11 = Vendor URL
    #   13 = License Description
    credits = {
        9:  "Sam Glassenberg / Brain Power Tools LLC",
        13: "VoDy font family by Sam Glassenberg / Brain Power Tools LLC. "
            "Vowel-differentiated fonts for phonological dyslexia.",
    }
    for name_id, value in credits.items():
        name_table.setName(value, name_id, 3, 1, 0x0409)  # Windows, Unicode BMP, English
        name_table.setName(value, name_id, 1, 0, 0)        # Mac, Roman, English


def scale_glyph(font, glyph_name, sx, sy, anchor_x="origin", anchor_y="baseline"):
    """
    Scale a glyph's contours.
    sx, sy: scale factors for x and y axes.
    anchor_x: "origin" (scale from x=0) or "center" (scale from glyph center).
    anchor_y: "baseline" (scale from y=0) or "top" (scale from ascender).
    """
    glyf_table = font["glyf"]
    glyph = glyf_table[glyph_name]
    hmtx = font["hmtx"]
    width, lsb = hmtx[glyph_name]

    if glyph.numberOfContours == 0:
        return
    if glyph.numberOfContours == -1 and not glyph.isComposite():
        return

    if glyph.isComposite():
        cx = width / 2 if anchor_x == "center" else 0
        for component in glyph.components:
            xx, xy_, yx, yy = 1.0, 0.0, 0.0, 1.0
            if hasattr(component, "transform") and component.transform:
                (xx, xy_), (yx, yy) = component.transform
            new_xx = xx * sx
            new_yy = yy * sy
            if hasattr(component, "x") and hasattr(component, "y"):
                if anchor_x == "center":
                    component.x = int(cx + (component.x - cx) * sx)
                else:
                    component.x = int(component.x * sx)
                component.y = int(component.y * sy)
            component.transform = ((new_xx, xy_ * sx), (yx * sy, new_yy))
            component.flags |= 0x0008
        return

    # Simple glyph
    coords = glyph.coordinates
    cx = width / 2 if anchor_x == "center" else 0

    # For top-aligned: get ascender height
    if anchor_y == "top":
        ascender = font["OS/2"].sTypoAscender
    else:
        ascender = 0

    new_coords = []
    for x, y in coords:
        if anchor_x == "center":
            new_x = cx + (x - cx) * sx
        else:
            new_x = x * sx
        if anchor_y == "top":
            new_y = ascender + (y - ascender) * sy
        else:
            new_y = y * sy
        new_coords.append((int(round(new_x)), int(round(new_y))))

    glyph.coordinates = type(coords)(new_coords)
    glyph.recalcBounds(glyf_table)


def set_advance_width(font, glyph_name, new_width):
    hmtx = font["hmtx"]
    _, lsb = hmtx[glyph_name]
    glyf_table = font["glyf"]
    glyph = glyf_table[glyph_name]
    if glyph.numberOfContours and glyph.numberOfContours > 0:
        lsb = glyph.xMin
    hmtx[glyph_name] = (new_width, lsb)


def add_spacing(font, glyph_name, extra_left, extra_right):
    """Add extra space on left/right of a glyph by shifting contours and widening."""
    glyf_table = font["glyf"]
    glyph = glyf_table[glyph_name]
    hmtx = font["hmtx"]
    width, lsb = hmtx[glyph_name]

    if glyph.numberOfContours == 0:
        hmtx[glyph_name] = (width + extra_left + extra_right, lsb + extra_left)
        return
    if glyph.numberOfContours == -1 and not glyph.isComposite():
        hmtx[glyph_name] = (width + extra_left + extra_right, lsb + extra_left)
        return

    if glyph.isComposite():
        for component in glyph.components:
            if hasattr(component, "x"):
                component.x += extra_left
    else:
        coords = glyph.coordinates
        new_coords = [(x + extra_left, y) for x, y in coords]
        glyph.coordinates = type(coords)(new_coords)
        glyph.recalcBounds(glyf_table)

    new_lsb = glyph.xMin if (not glyph.isComposite() and glyph.numberOfContours > 0) else lsb + extra_left
    hmtx[glyph_name] = (width + extra_left + extra_right, new_lsb)


def thicken_glyph(font, glyph_name, amount):
    """Thicken a glyph by expanding contour points outward from center."""
    glyf_table = font["glyf"]
    glyph = glyf_table[glyph_name]
    if glyph.numberOfContours <= 0:
        return
    if glyph.isComposite():
        return

    hmtx = font["hmtx"]
    width, lsb = hmtx[glyph_name]

    coords = glyph.coordinates
    # Find center
    xs = [x for x, y in coords]
    ys = [y for x, y in coords]
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2

    new_coords = []
    for x, y in coords:
        dx = x - cx
        dy = y - cy
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > 0:
            # Push outward
            factor = (dist + amount) / dist
            new_x = cx + dx * factor
            new_y = cy + dy * factor
        else:
            new_x, new_y = x, y
        new_coords.append((int(round(new_x)), int(round(new_y))))

    glyph.coordinates = type(coords)(new_coords)
    glyph.recalcBounds(glyf_table)

    # Widen advance width proportionally
    new_w = int(round(width + amount * 2))
    hmtx[glyph_name] = (new_w, glyph.xMin)


def deepen_curve(font, glyph_name, factor):
    """Deepen the curve of a glyph by pulling bottom points lower."""
    glyf_table = font["glyf"]
    glyph = glyf_table[glyph_name]
    if glyph.numberOfContours <= 0 or glyph.isComposite():
        return

    coords = glyph.coordinates
    ys = [y for _, y in coords]
    min_y = min(ys)
    max_y = max(ys)
    mid_y = (min_y + max_y) / 2

    new_coords = []
    for x, y in coords:
        if y < mid_y:
            # Below midpoint — pull lower
            pull = (mid_y - y) / (mid_y - min_y) if mid_y != min_y else 0
            new_y = y - int(round(pull * factor))
        else:
            new_y = y
        new_coords.append((x, new_y))

    glyph.coordinates = type(coords)(new_coords)
    glyph.recalcBounds(glyf_table)


def widen_glyph(font, glyph_name, factor):
    """Widen a glyph horizontally by the given factor (1.2 = 20% wider), centered."""
    glyf_table = font["glyf"]
    glyph = glyf_table[glyph_name]
    hmtx = font["hmtx"]
    width, lsb = hmtx[glyph_name]
    new_width = int(round(width * factor))

    if glyph.numberOfContours <= 0:
        if glyph.isComposite():
            for comp in glyph.components:
                xx, xy_, yx, yy = 1.0, 0.0, 0.0, 1.0
                if hasattr(comp, "transform") and comp.transform:
                    (xx, xy_), (yx, yy) = comp.transform
                comp.transform = ((xx * factor, xy_), (yx, yy))
                if hasattr(comp, "x"):
                    comp.x = int(comp.x * factor)
                comp.flags |= 0x0008
            hmtx[glyph_name] = (new_width, int(round(lsb * factor)))
        return

    coords = glyph.coordinates
    # Scale around the glyph's own bounding box center
    xs = [x for x, y in coords]
    glyph_cx = (min(xs) + max(xs)) / 2
    new_coords = []
    for x, y in coords:
        new_x = glyph_cx + (x - glyph_cx) * factor
        new_coords.append((int(round(new_x)), y))
    glyph.coordinates = type(coords)(new_coords)
    glyph.recalcBounds(glyf_table)

    # Re-center the widened glyph in the new advance width
    # by shifting so the glyph sits with equal side bearings
    glyph_w = glyph.xMax - glyph.xMin
    target_lsb = (new_width - glyph_w) // 2
    shift = target_lsb - glyph.xMin
    if shift != 0:
        coords = glyph.coordinates
        new_coords = [(x + shift, y) for x, y in coords]
        glyph.coordinates = type(coords)(new_coords)
        glyph.recalcBounds(glyf_table)

    hmtx[glyph_name] = (new_width, glyph.xMin)


def open_counter(font, glyph_name, amount):
    """Open the counter (inner space) of a glyph like E by pushing inner points outward."""
    glyf_table = font["glyf"]
    glyph = glyf_table[glyph_name]
    if glyph.numberOfContours <= 0 or glyph.isComposite():
        return

    hmtx = font["hmtx"]
    width, lsb = hmtx[glyph_name]

    coords = glyph.coordinates
    xs = [x for x, y in coords]
    min_x, max_x = min(xs), max(xs)
    mid_x = (min_x + max_x) / 2

    new_coords = []
    for x, y in coords:
        # Push rightward points further right to open counters
        if x > mid_x:
            push = (x - mid_x) / (max_x - mid_x) if max_x != mid_x else 0
            new_x = x + int(round(push * amount))
        else:
            new_x = x
        new_coords.append((new_x, y))

    glyph.coordinates = type(coords)(new_coords)
    glyph.recalcBounds(glyf_table)
    hmtx[glyph_name] = (width + amount, glyph.xMin)


# ---------------------------------------------------------------------------
# Font generators
# ---------------------------------------------------------------------------

def make_vody_small(out_path):
    """VoDy Small: Inter with vowels at 50% size + proportional width."""
    print("\n=== VoDy Small ===")
    font = TTFont(INTER_REGULAR)
    vowels = get_vowel_glyphs(font)
    hmtx = font["hmtx"]
    scale = 0.50

    for ch, gn in vowels:
        print(f"  {ch} -> {gn}")
        width, lsb = hmtx[gn]
        scale_glyph(font, gn, scale, scale)
        set_advance_width(font, gn, int(round(width * scale)))

    rename_font(font, "VoDy Small")
    font.save(out_path)
    font.close()
    print(f"  Saved: {out_path}")


def make_vody_big(out_path):
    """VoDy Big: Inter with vowels 20% bigger."""
    print("\n=== VoDy Big ===")
    font = TTFont(INTER_REGULAR)
    vowels = get_vowel_glyphs(font)
    hmtx = font["hmtx"]
    scale = 1.20

    for ch, gn in vowels:
        print(f"  {ch} -> {gn}")
        width, lsb = hmtx[gn]
        scale_glyph(font, gn, scale, scale)
        set_advance_width(font, gn, int(round(width * scale)))

    rename_font(font, "VoDy Big")
    font.save(out_path)
    font.close()
    print(f"  Saved: {out_path}")


def make_vody_space(out_path):
    """VoDy Space: Inter with 20% extra spacing around vowels."""
    print("\n=== VoDy Space ===")
    font = TTFont(INTER_REGULAR)
    vowels = get_vowel_glyphs(font)
    hmtx = font["hmtx"]

    for ch, gn in vowels:
        print(f"  {ch} -> {gn}")
        width, _ = hmtx[gn]
        extra = int(round(width * 0.20))
        add_spacing(font, gn, extra, extra)

    rename_font(font, "VoDy Space")
    font.save(out_path)
    font.close()
    print(f"  Saved: {out_path}")


def make_vody_high(out_path):
    """VoDy High: Inter with vowels 5% smaller, top-aligned to ascender."""
    print("\n=== VoDy High ===")
    font = TTFont(INTER_REGULAR)
    vowels = get_vowel_glyphs(font)
    hmtx = font["hmtx"]
    scale = 0.95

    for ch, gn in vowels:
        print(f"  {ch} -> {gn}")
        width, lsb = hmtx[gn]
        scale_glyph(font, gn, scale, scale, anchor_x="center", anchor_y="top")
        set_advance_width(font, gn, int(round(width * scale)))

    rename_font(font, "VoDy High")
    font.save(out_path)
    font.close()
    print(f"  Saved: {out_path}")


def make_vody_shaped(out_path):
    """VoDy Shaped: Inter with unique per-vowel visual treatments.
    A/a - wider
    E/e - more open counter
    I/i - thicker
    O/o - heavier weight (thicken)
    U/u - deeper curve
    """
    print("\n=== VoDy Shaped ===")
    font = TTFont(INTER_REGULAR)
    cmap = font.getBestCmap()

    treatments = {
        'A': ('wider', 1.25),
        'a': ('wider', 1.25),
        'E': ('open_counter', 120),
        'e': ('open_counter', 80),
        'I': ('thicken', 40),
        'i': ('thicken', 40),
        'O': ('thicken', 50),
        'o': ('thicken', 50),
        'U': ('deepen', 80),
        'u': ('deepen', 80),
    }

    for ch, (treatment, param) in treatments.items():
        cp = ord(ch)
        if cp not in cmap:
            continue
        gn = cmap[cp]
        print(f"  {ch} -> {gn}: {treatment}({param})")

        if treatment == 'wider':
            widen_glyph(font, gn, param)
        elif treatment == 'open_counter':
            open_counter(font, gn, param)
        elif treatment == 'thicken':
            thicken_glyph(font, gn, param)
        elif treatment == 'deepen':
            deepen_curve(font, gn, param)

    rename_font(font, "VoDy Shaped")
    font.save(out_path)
    font.close()
    print(f"  Saved: {out_path}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    make_vody_small(os.path.join(OUT_DIR, "VoDy_Small.ttf"))
    make_vody_big(os.path.join(OUT_DIR, "VoDy_Big.ttf"))
    make_vody_space(os.path.join(OUT_DIR, "VoDy_Space.ttf"))
    make_vody_high(os.path.join(OUT_DIR, "VoDy_High.ttf"))
    make_vody_shaped(os.path.join(OUT_DIR, "VoDy_Shaped.ttf"))

    print("\n=== All fonts generated! ===")


if __name__ == "__main__":
    main()
