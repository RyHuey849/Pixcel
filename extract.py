"""
Milestone 1 - OCR prototype.

Extracts Name / Stat 1 / Stat 2 / Stat 3 from a single MapleStory screenshot
and prints the rows as JSON.

Usage:
    python extract.py sample.png
    python extract.py sample.png --debug crops/   # dump crops for calibration

This is deliberately NOT a generic table reader. Every screenshot comes from
the same UI, so the table geometry below is hard-coded and never inferred.
"""

import argparse
import json
import re
import sys

import cv2
import numpy as np

try:
    import pytesseract
except ImportError:
    sys.exit("pytesseract is not installed. Run: pip install -r requirements.txt")


# ---------------------------------------------------------------------------
# Layout constants
#
# DESIGN DECISION: the geometry is hard-coded, but it is expressed *relative to
# the table's top-left text origin* rather than in absolute image coordinates.
# The sample screenshots are all the same UI at the same zoom - the row pitch is
# exactly 24px in every one - but they were cropped by hand, so the table sits
# at a different offset in each file (x varies 19..31, y varies 9..16, and the
# files differ in size by up to 13px). Absolute boxes would drift off the text;
# anchoring costs one cheap projection and makes the same numbers work on every
# file. Everything below is still fixed - only the origin is looked up.
#
# All X values are offsets from the left edge of the Name column.
# All Y values are offsets from the top of the first row's text band.
# ---------------------------------------------------------------------------

ROW_PITCH = 24  # vertical distance between consecutive rows, measured exactly

# The text band is ~9px tall; pad above for accents (Aårön, MôXuân) and below
# for descenders (y, g) so no glyph is clipped.
CELL_TOP = -4
CELL_BOTTOM = 15

# Name is left-aligned at the origin. The UI truncates long names with ".."
# at a fixed width, which is what sets the right edge here. The Class column
# that follows is centre-aligned, so a long class name ("Thunder Breaker")
# can reach back to about +64 while a truncated name can reach +68 - the two
# columns overlap, so no single fixed edge separates them. Cutting at the last
# blank gap inside NAME_SEAM recovers the few px of slack; when the name and
# class genuinely touch it falls back to NAME_BOX and clean_name() drops the
# stray glyph.
NAME_BOX = (-2, 69)
NAME_SEAM = (48, 69)  # window searched for the name/class gap
SEAM_GAP = 2  # blank columns needed to count as a gap, not letter spacing

# The three stat columns are centre-aligned, not right-aligned: "0" and "1,000"
# share a midpoint. Hence centre + half-width rather than a left edge. The
# spacing is uneven (+64 then +78), so all three are listed explicitly.
STAT_CENTRES = (269, 333, 411)
STAT_HALF_WIDTH = 21  # fits "1,000" (29px wide) with room to spare

# OCR tuning. Game text is ~9px tall, far below Tesseract's comfort zone, so
# crops are upscaled before recognition.
UPSCALE = 4
PAD = 12  # white border; Tesseract needs quiet space around the glyphs
STAT_ALLOWLIST = "0123456789,"  # comma: thousands separator in "1,000"

# Ink detection. The panel is a dark dithered texture with light text, so
# "brighter than the median by a margin" separates the two cleanly.
INK_MARGIN = 25
BAND_MIN_INK = 8  # px of ink on a scanline before it counts as text
BAND_MIN_HEIGHT = 5  # discard 1-2px specks from the panel texture


# ---------------------------------------------------------------------------
# Grid location
# ---------------------------------------------------------------------------


def ink_mask(gray):
    """Boolean mask of text pixels (light glyphs on a dark panel)."""
    return gray > np.median(gray) + INK_MARGIN


def text_bands(ink):
    """(top, bottom) of each horizontal run of scanlines containing text."""
    per_row = ink.sum(axis=1)
    bands, start = [], None
    for y, count in enumerate(per_row):
        if count > BAND_MIN_INK and start is None:
            start = y
        elif count <= BAND_MIN_INK and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, len(per_row) - 1))
    return [b for b in bands if b[1] - b[0] >= BAND_MIN_HEIGHT]


def locate_grid(ink):
    """Find the table origin and row count. Returns (x0, y0, row_count)."""
    bands = text_bands(ink)
    if not bands:
        raise ValueError("no text rows found - is this a screenshot of the list?")

    # Names are left-aligned, so the leftmost ink on any text row is the origin.
    # Restricting to text rows keeps stray UI chrome above/below out of it.
    rows_with_text = np.zeros(ink.shape[0], bool)
    for top, bottom in bands:
        rows_with_text[top:bottom + 1] = True
    x0 = int(np.argmax(ink[rows_with_text].sum(axis=0) > 0))

    y0 = bands[0][0]
    # Derive the count from the span rather than len(bands): a row whose glyphs
    # all sit low could in principle split, but the span endpoints are solid.
    row_count = round((bands[-1][0] - y0) / ROW_PITCH) + 1
    return x0, y0, row_count


# ---------------------------------------------------------------------------
# Cropping and OCR
# ---------------------------------------------------------------------------


def row_slice(height, y0, row):
    """(top, bottom) of one row's crop band, clamped to the image."""
    top = y0 + row * ROW_PITCH + CELL_TOP
    bottom = y0 + row * ROW_PITCH + CELL_BOTTOM
    # Clamp so the first/last row survives a screenshot cropped tight to the text.
    return max(top, 0), min(bottom, height)


def cell(gray, x0, y0, row, left, right):
    """Crop one cell, given column bounds relative to the table origin."""
    top, bottom = row_slice(gray.shape[0], y0, row)
    return gray[top:bottom, max(x0 + left, 0):min(x0 + right, gray.shape[1])]


def name_right_edge(ink, x0, y0, row):
    """Right edge for this row's name cell: the last gap before the Class column."""
    top, bottom = row_slice(ink.shape[0], y0, row)
    seam = ink[top:bottom, x0 + NAME_SEAM[0]:x0 + NAME_SEAM[1]].any(axis=0)
    # Walk back from the far edge for the last run of blank columns. Anything
    # left of it is the name; anything right of it belongs to Class.
    for i in range(len(seam) - SEAM_GAP, -1, -1):
        if not seam[i:i + SEAM_GAP].any():
            return NAME_SEAM[0] + i
    return NAME_BOX[1]  # name and class touch - nothing to cut on


def preprocess(patch):
    """Upscale, invert to dark-on-light, binarize, and pad."""
    patch = cv2.resize(patch, None, fx=UPSCALE, fy=UPSCALE,
                       interpolation=cv2.INTER_CUBIC)
    # Otsu picks the threshold per cell, which handles the brighter "highlighted"
    # rows that appear in most screenshots without a hand-tuned constant.
    _, binary = cv2.threshold(patch, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return cv2.copyMakeBorder(binary, PAD, PAD, PAD, PAD,
                              cv2.BORDER_CONSTANT, value=255)


def ocr(patch, allowlist=None):
    """Run Tesseract on a single pre-processed cell and return raw text."""
    # psm 7 = "a single line of text", which is exactly what a cell holds.
    config = "--psm 7"
    if allowlist:
        # Constraining the alphabet is the single biggest accuracy win on the
        # stat columns: it stops 0/O, 1/l and 5/S being confused.
        config += f" -c tessedit_char_whitelist={allowlist}"
    return pytesseract.image_to_string(patch, config=config).strip()


def to_int(text):
    """Coerce OCR output to an int. Strips the thousands comma in '1,000'."""
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else 0


def clean_name(text):
    """Tidy a name cell: collapse spaces, drop the UI's '..' truncation, and
    drop trailing punctuation left by a Class glyph that touched the name."""
    text = re.sub(r"\s+", "", text)
    return re.sub(r"[^0-9A-Za-z]+$", "", text)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def extract(path, debug_dir=None):
    """Read every row from a screenshot. Returns a list of row dicts."""
    gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"could not read image: {path}")

    ink = ink_mask(gray)
    x0, y0, row_count = locate_grid(ink)
    stat_columns = [
        (f"stat_{i + 1}", (c - STAT_HALF_WIDTH, c + STAT_HALF_WIDTH), STAT_ALLOWLIST)
        for i, c in enumerate(STAT_CENTRES)
    ]

    rows = []
    for row_index in range(row_count):
        # The name's right edge is the one column bound that has to be resolved
        # per row; the stat columns are rigid.
        name_box = (NAME_BOX[0], name_right_edge(ink, x0, y0, row_index))
        record = {}
        for key, (left, right), allowlist in [("name", name_box, None)] + stat_columns:
            patch = preprocess(cell(gray, x0, y0, row_index, left, right))
            if debug_dir is not None:
                cv2.imwrite(str(debug_dir / f"r{row_index:02d}_{key}.png"), patch)
            text = ocr(patch, allowlist)
            record[key] = clean_name(text) if allowlist is None else to_int(text)

        # A blank name means the crop landed past the populated rows.
        if record["name"]:
            rows.append(record)

    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", nargs="?", default="sample.png",
                        help="path to the screenshot (default: sample.png)")
    parser.add_argument(
        "--debug",
        metavar="DIR",
        help="write each pre-processed crop here, for checking the geometry",
    )
    args = parser.parse_args()

    debug_dir = None
    if args.debug:
        from pathlib import Path

        debug_dir = Path(args.debug)
        debug_dir.mkdir(parents=True, exist_ok=True)

    rows = extract(args.image, debug_dir)
    # JSON only on stdout, so this composes with other tools.
    print(json.dumps(rows, indent=4))


if __name__ == "__main__":
    main()
