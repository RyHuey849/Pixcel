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
import string
import sys

import cv2
import numpy as np

from preprocessing import STAGES, preprocess_cell

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
# sufficiently wide blank gap inside NAME_SEAM recovers the few px of slack;
# when the name and class genuinely touch it falls back to NAME_BOX and
# clean_name() drops the stray glyph.
NAME_BOX = (-2, 69)
NAME_SEAM = (48, 69)  # window searched for the name/class gap
# Blank columns needed to count as the name/class seam rather than letter
# spacing. Measured across the sample set: gaps *inside* a word are never wider
# than 2px, while a genuine name/class gap is 6px or more. At 2 the search
# happily stopped on a letter gap and truncated the name ("FARENHEIT" ->
# "FARENHE"); 3 is the smallest value that cannot match letter spacing.
SEAM_GAP = 3

# The three stat columns are centre-aligned, not right-aligned: "0" and "1,000"
# share a midpoint. Hence centre + half-width rather than a left edge. The
# spacing is uneven (+64 then +78), so all three are listed explicitly.
STAT_CENTRES = (269, 333, 411)
STAT_HALF_WIDTH = 21  # fits "1,000" (29px wide) with room to spare

# OCR tuning. Game text is ~9px tall, far below Tesseract's comfort zone; the
# crops are cleaned up by preprocessing.py before recognition.
#
# Per-column character whitelists. Each cell is recognised on its own, so each
# can be told exactly which alphabet it is allowed to produce.
NAME_CHARSET = string.ascii_letters + string.digits + "._-"
DIGIT_CHARSET = "0123456789"

# CAUTION: the LSTM engine applies a whitelist by discarding disallowed
# characters *after* recognition, not by constraining the search. A stat cell
# whose best hypothesis is a letter therefore comes back empty rather than
# falling through to the best digit, and to_int() reports 0 - a wrong answer
# that looks entirely plausible in the review UI. This font's "9" is read as "g"
# every time, which is exactly that case, so stat cells fall back to an
# unconstrained read when the whitelist leaves nothing behind. See ocr_stat().
DIGIT_LOOKALIKES = str.maketrans({"g": "9"})

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


def ocr(patch, charset=None):
    """Run Tesseract on a single pre-processed cell and return raw text.

    One call per cell, never per screenshot: the whole point of the fixed
    geometry is that each cell arrives already isolated, so Tesseract is only
    ever asked to read one short line of one known alphabet.
    """
    # psm 7 = "a single line of text", which is exactly what a cell holds.
    config = "--psm 7"
    if charset:
        config += f" -c tessedit_char_whitelist={charset}"
    return pytesseract.image_to_string(patch, config=config).strip()


def ocr_name(patch, whitelist=True):
    """Read a name cell, restricted to letters, digits, '.', '_' and '-'."""
    return ocr(patch, NAME_CHARSET if whitelist else None)


def ocr_stat(patch, whitelist=True):
    """Read a stat cell, restricted to digits.

    Falls back to an unconstrained read when the digit whitelist returns
    nothing. An empty result means the whitelist threw away every character
    Tesseract proposed, so the alternative to falling back is not a better digit
    - it is a silent 0. The fallback only ever runs on cells the constrained
    pass already failed, so it cannot make a successful read worse.
    """
    if not whitelist:
        return ocr(patch)
    text = ocr(patch, DIGIT_CHARSET)
    return text if text else ocr(patch)


def to_int(text):
    """Coerce a stat cell to an int: repair known lookalikes, then keep digits.

    Dropping the leftover non-digits is what absorbs the thousands separator in
    "1,000" - the digit whitelist already removes it, but the fallback path in
    ocr_stat() is unconstrained and still sees it.
    """
    digits = re.sub(r"\D", "", text.translate(DIGIT_LOOKALIKES))
    return int(digits) if digits else 0


def clean_name(text):
    """Tidy a name cell: collapse spaces, drop the UI's '..' truncation, and
    drop trailing punctuation left by a Class glyph that touched the name.

    The truncation marker needs its own rule now that NAME_CHARSET permits '.'.
    Tesseract used to discard those dots as disallowed characters; it now keeps
    them, and a marker misread as '.1' ends in an alphanumeric, so the trailing
    punctuation strip below no longer reaches it ("HoagieSlay.." came back as
    "HoagieSlay.1"). Cutting from a '.' that is followed by no further letters
    removes the marker however its second dot was recognised, while leaving a
    '.' that sits inside a real name alone.
    """
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"\.[^A-Za-z]*$", "", text)
    return re.sub(r"[^0-9A-Za-z]+$", "", text)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def decode_image(data):
    """Decode raw image bytes to grayscale.

    The API receives uploads as bytes, not paths. Decoding here rather than in
    the route keeps every entry point into the pipeline on the same OpenCV read,
    and spares the API a round-trip through a temporary file.
    """
    buffer = np.frombuffer(data, np.uint8)
    gray = cv2.imdecode(buffer, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError("could not decode image - unsupported or corrupt file")
    return gray


def extract(path, debug_dir=None, stages=STAGES, keep_empty=False, whitelist=True):
    """Read every row from a screenshot on disk. Returns a list of row dicts."""
    gray = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"could not read image: {path}")
    return extract_image(gray, debug_dir, stages, keep_empty, whitelist)


def extract_image(gray, debug_dir=None, stages=STAGES, keep_empty=False,
                  whitelist=True):
    """Read every row from an already-decoded grayscale screenshot.

    Split out from extract() so an uploaded image can be parsed straight from
    memory; extract() is now just this plus a file read.

    `whitelist` turns the per-column character restrictions off; like `stages`
    it exists so benchmark.py can measure what they are worth.

    `stages` is passed straight to the preprocessor; benchmark.py varies it to
    measure what each stage is worth. Note that the grid geometry below is
    derived from the raw image, so it stays identical across those runs and the
    only thing being compared is the preprocessing.

    `keep_empty` returns one record per grid row instead of skipping the blanks.
    benchmark.py needs it: if a weak configuration reads a name as empty, the
    row would silently vanish and every later row would be compared against the
    wrong answer, which scores the misalignment rather than the OCR.
    """
    ink = ink_mask(gray)
    x0, y0, row_count = locate_grid(ink)
    # Each column is (key, bounds, read, parse) - the reader supplies the
    # alphabet and the parser the type, so adding a column never touches the
    # loop below.
    stat_columns = [
        (f"stat_{i + 1}", (c - STAT_HALF_WIDTH, c + STAT_HALF_WIDTH),
         ocr_stat, to_int)
        for i, c in enumerate(STAT_CENTRES)
    ]

    rows = []
    for row_index in range(row_count):
        # The name's right edge is the one column bound that has to be resolved
        # per row; the stat columns are rigid.
        name_box = (NAME_BOX[0], name_right_edge(ink, x0, y0, row_index))
        columns = [("name", name_box, ocr_name, clean_name)] + stat_columns
        record = {}
        for key, (left, right), read, parse in columns:
            patch = preprocess_cell(
                cell(gray, x0, y0, row_index, left, right), stages)
            if debug_dir is not None:
                cv2.imwrite(str(debug_dir / f"r{row_index:02d}_{key}.png"), patch)
            record[key] = parse(read(patch, whitelist))

        # A blank name means the crop landed past the populated rows.
        if record["name"] or keep_empty:
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
