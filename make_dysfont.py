"""
Generate a dyslexia-friendly font variant where vowel glyphs are scaled to 90%.

Takes Arial as the base font, shrinks all vowel glyphs (uppercase and lowercase)
to 90% of their original size, and outputs a new TTF + a test HTML page.
"""

from fontTools.ttLib import TTFont
import os

INPUT_FONT = "C:/Windows/Fonts/arial.ttf"
OUTPUT_FONT = "c:/dev/dysfont/DysFont4.ttf"
SCALE = 0.50

VOWELS = list("aeiouAEIOU")


def scale_glyph(font, glyph_name, scale):
    """Scale a single glyph in a TrueType font, including its advance width."""
    glyf_table = font["glyf"]
    hmtx = font["hmtx"]
    glyph = glyf_table[glyph_name]
    width, lsb = hmtx[glyph_name]

    # Scale advance width so kerning tightens around the smaller glyph
    new_width = int(round(width * scale))

    if glyph.numberOfContours == 0 or glyph.numberOfContours == -1:
        if glyph.isComposite():
            for component in glyph.components:
                xx, xy, yx, yy = 1.0, 0.0, 0.0, 1.0
                if hasattr(component, "transform") and component.transform:
                    (xx, xy), (yx, yy) = component.transform

                new_xx = xx * scale
                new_yy = yy * scale

                if hasattr(component, "x") and hasattr(component, "y"):
                    component.x = int(component.x * scale)
                    component.y = int(component.y * scale)

                component.transform = ((new_xx, xy * scale), (yx * scale, new_yy))
                component.flags |= 0x0008  # WE_HAVE_A_SCALE flag

            hmtx[glyph_name] = (new_width, int(round(lsb * scale)))
            return

        hmtx[glyph_name] = (new_width, 0)
        return  # truly empty glyph

    # Simple glyph with contours — scale all points from origin
    coords = glyph.coordinates
    new_coords = []
    for x, y in coords:
        new_coords.append((int(round(x * scale)), int(round(y * scale))))

    glyph.coordinates = type(coords)(new_coords)
    glyph.recalcBounds(glyf_table)

    # Update metrics: narrower width, scaled LSB
    new_lsb = glyph.xMin if glyph.numberOfContours > 0 else 0
    hmtx[glyph_name] = (new_width, new_lsb)


def main():
    print(f"Loading font: {INPUT_FONT}")
    font = TTFont(INPUT_FONT)

    cmap = font.getBestCmap()
    glyf_table = font["glyf"]

    vowel_glyph_names = []
    for char in VOWELS:
        cp = ord(char)
        if cp in cmap:
            glyph_name = cmap[cp]
            vowel_glyph_names.append((char, glyph_name))
        else:
            print(f"  Warning: '{char}' (U+{cp:04X}) not found in cmap")

    print(f"\nScaling {len(vowel_glyph_names)} vowel glyphs to {SCALE * 100:.0f}%:")
    for char, glyph_name in vowel_glyph_names:
        print(f"  '{char}' -> glyph '{glyph_name}'")
        scale_glyph(font, glyph_name, SCALE)

    # Update font metadata so it doesn't conflict with the real Arial
    name_table = font["name"]
    for record in name_table.names:
        s = record.toUnicode()
        if "Arial" in s:
            new_s = s.replace("Arial", "DysFont")
            record.string = new_s

    # Write output
    os.makedirs(os.path.dirname(OUTPUT_FONT), exist_ok=True)
    print(f"\nSaving modified font: {OUTPUT_FONT}")
    font.save(OUTPUT_FONT)
    font.close()
    print("Done!")


if __name__ == "__main__":
    main()
