"""
Milestone 1 - OCR prototype.

Extracts Name / Stat 1 / Stat 2 / Stat 3 from a single MapleStory screenshot
and prints the rows as JSON.

Usage:
    python extract.py sample.png
    python extract.py sample.png --debug crops/   # dump crops for calibration

This is deliberately NOT a generic table reader. Every screenshot comes from
the same UI at the same resolution, so the layout is hard-coded below.
"""

import argparse
import json
import re
import sys

from PIL import Image

try:
    import pytesseract
except ImportError:
    sys.exit("pytesseract is not installed. Run: pip install -r requirements.txt")


# ---------------------------------------------------------------------------
# Layout constants
#
# DESIGN DECISION: every input is resized to STANDARD_SIZE before cropping, so
# these coordinates are expressed in one fixed space. A screenshot taken at a
# different resolution still lands on the same crop boxes, and there is exactly
# one set of numbers to calibrate.
#
# DESIGN DECISION: rows are evenly spaced, so the grid is described by an
# origin + pitch rather than one rectangle per cell. Calibrating the whole
# table is ~6 numbers instead of 4 x N rectangles.
#
# !! PLACEHOLDER VALUES - calibrated against sample.png in the next step. !!
# ---------------------------------------------------------------------------

STANDARD_SIZE = (1920, 1080)  # (width, height) every image is normalized to

FIRST_ROW_TOP = 300  # y of the first row's text band
ROW_HEIGHT = 34  # height of the text band
ROW_PITCH = 40  # y distance between consecutive row tops
ROW_COUNT = 12  # rows visible per screenshot

# (key, x, width, numeric). Only these four columns are read; every other
# column in the UI is simply never cropped.
COLUMNS = (
    ("name", 420, 260, False),
    ("stat_1", 700, 120, True),
    ("stat_2", 840, 120, True),
    ("stat_3", 980, 120, True),
)

# OCR tuning. Game text is small, so crops are upscaled before recognition;
# Tesseract wants roughly 30px cap height to do its best work.
UPSCALE = 4
NUMERIC_ALLOWLIST = "0123456789"
NAME_ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def load_normalized(path):
    """Open the screenshot and force it to STANDARD_SIZE."""
    image = Image.open(path).convert("RGB")
    if image.size != STANDARD_SIZE:
        # LANCZOS preserves glyph edges better than the default on downscale.
        image = image.resize(STANDARD_SIZE, Image.LANCZOS)
    return image


def cell_box(row_index, x, width):
    """Pillow crop box (left, upper, right, lower) for one cell."""
    top = FIRST_ROW_TOP + row_index * ROW_PITCH
    return (x, top, x + width, top + ROW_HEIGHT)


def preprocess(cell):
    """Upscale and binarize a cell so Tesseract sees clean black-on-white."""
    cell = cell.resize(
        (cell.width * UPSCALE, cell.height * UPSCALE), Image.LANCZOS
    ).convert("L")
    # MapleStory renders light text on a dark panel; invert so text is dark,
    # then hard-threshold to kill the panel texture and anti-aliasing halo.
    cell = cell.point(lambda p: 0 if p > 140 else 255, mode="L")
    return cell


def ocr(cell, numeric):
    """Run Tesseract on a single pre-processed cell and return raw text."""
    # psm 7 = "treat the image as a single text line", which is exactly what a
    # cell is. The allowlist is the single biggest accuracy win here: it stops
    # digits being read as letters (0/O, 1/l, 5/S) and vice versa.
    allowlist = NUMERIC_ALLOWLIST if numeric else NAME_ALLOWLIST
    config = f"--psm 7 -c tessedit_char_whitelist={allowlist}"
    return pytesseract.image_to_string(cell, config=config).strip()


def to_int(text):
    """Coerce OCR output to an int, defaulting to 0 when nothing was read."""
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else 0


def extract(path, debug_dir=None):
    """Read every row from a screenshot. Returns a list of row dicts."""
    image = load_normalized(path)
    rows = []

    for row_index in range(ROW_COUNT):
        row = {}
        for key, x, width, numeric in COLUMNS:
            cell = image.crop(cell_box(row_index, x, width))
            processed = preprocess(cell)
            if debug_dir is not None:
                processed.save(debug_dir / f"r{row_index:02d}_{key}.png")
            text = ocr(processed, numeric)
            row[key] = to_int(text) if numeric else text

        # A blank name means we've run past the populated rows. Skip rather
        # than emit empty records.
        if row["name"]:
            rows.append(row)

    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", help="path to the screenshot")
    parser.add_argument(
        "--debug",
        metavar="DIR",
        help="write each pre-processed crop here, for calibrating the constants",
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
