"""
Milestone 2 - cell preprocessing.

Every cropped cell goes through one fixed pipeline before it reaches Tesseract:

    grayscale -> upscale -> contrast -> threshold -> denoise -> pad

The cells are tiny (~70x19 px, glyphs ~9 px tall) and sit on a dark, dithered
panel with light text. That is close to the worst case for Tesseract's LSTM,
which was trained on ~30 px dark-on-light print. Each stage below closes one
specific part of that gap.

Every constant here is measured by benchmark.py, which can enable or disable
individual stages so a claimed improvement is attributable to a stage rather
than assumed.
"""

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Tuning constants
# ---------------------------------------------------------------------------

# Tesseract's LSTM wants an x-height near 30 px. This font's x-height is ~7 px,
# so 4x lands at ~28. Higher factors cost time without adding information -
# there is nothing in the source pixels for 8x to recover.
UPSCALE = 4

# Endpoints of the contrast stretch, as percentiles of the cell's histogram.
#
# MEASURED: clipping hurts, monotonically. Sweeping these over the sample set
# gives 94.8% overall at p0/p100, 94.2% at p1/p99, 94.0% at p2/p98 and 90.3% at
# p5/p95 - where the stat columns collapse to 50.8%, because a stat cell is
# mostly background and 5% of its pixels is a large share of its ink.
#
# The reason is that Otsu runs immediately downstream. Otsu picks its cut from
# the histogram's shape, so a monotonic linear rescale barely moves it; the only
# thing clipping contributes is saturated glyph edges, which is lost detail and
# nothing else. p0/p100 is therefore the right choice: a pure min-max stretch
# that widens the ~40-level panel/text separation to the full 255 without
# discarding a single pixel's worth of information.
CONTRAST_PERCENTILES = (0.0, 100.0)

# DESIGN DECISION: skip the stretch when the cell is nearly flat. An empty cell
# contains only dither, and stretching it would amplify that texture into
# something Otsu happily splits into "glyphs" - inventing text where there is
# none. Cells that hold real text span far more than this.
MIN_CONTRAST_RANGE = 20

# Speck removal threshold, expressed in *source* pixels so it tracks UPSCALE.
#
# Measured by sweeping this constant over the sample set (672 fields): 0-20 px
# all score 94.3%, 24 drops to 93.8%, and 32 to 92.4%. So the safe ceiling is
# real and close - at 24 the filter starts eating the thin diacritics and the
# stems of "l"/"i", and accuracy falls. 1 source pixel sits well inside the flat
# region while still removing anything smaller than a single source pixel.
MIN_INK_SOURCE_PIXELS = 1
MIN_COMPONENT_AREA = MIN_INK_SOURCE_PIXELS * UPSCALE * UPSCALE

# Tesseract needs quiet space around the glyphs or it clips the outermost
# stroke. Not one of the milestone's five stages, but required for any of them
# to pay off, so it always runs.
PAD = 12

# Stage names, in pipeline order. benchmark.py builds ablations from these.
STAGES = ("grayscale", "upscale", "contrast", "threshold", "denoise")


# ---------------------------------------------------------------------------
# Stages
# ---------------------------------------------------------------------------


def to_grayscale(image):
    """Collapse to a single channel.

    The UI draws light gray text on a dark gray panel, so no colour channel
    carries information the others lack - plain luminance is the right
    reduction. Already-gray input passes straight through, which is what makes
    this safe to call on crops taken from a grayscale read.
    """
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image


def upscale(gray, factor=UPSCALE):
    """Enlarge the cell to the size Tesseract expects.

    INTER_CUBIC rather than INTER_NEAREST: nearest keeps the source's hard
    pixel staircase, which the LSTM reads as stroke texture. Cubic interpolates
    smooth edges, and its mild low-pass side effect also softens the panel's
    dither before it reaches the threshold.
    """
    return cv2.resize(gray, None, fx=factor, fy=factor,
                      interpolation=cv2.INTER_CUBIC)


def enhance_contrast(gray):
    """Linearly stretch the cell's own intensity range to full scale.

    The panel/text separation is only ~40 levels out of 255. Widening it before
    Otsu gives the threshold a genuinely bimodal histogram to split instead of
    two neighbouring humps.

    DESIGN DECISION: a global linear stretch, not CLAHE. CLAHE equalises per
    tile, and on a cell this small most tiles are pure background - it would
    amplify dither hardest exactly where there is no signal. A single linear map
    cannot invent local structure, and the flat-cell guard covers the one case
    where even that would mislead. See CONTRAST_PERCENTILES for why the
    endpoints do not clip.
    """
    low, high = np.percentile(gray, CONTRAST_PERCENTILES)
    if high - low < MIN_CONTRAST_RANGE:
        return gray  # flat cell - see MIN_CONTRAST_RANGE
    stretched = (gray.astype(np.float32) - low) * (255.0 / (high - low))
    return np.clip(stretched, 0, 255).astype(np.uint8)


def binarize(gray):
    """Otsu threshold, inverted to dark-on-light.

    Inverted because Tesseract expects print: dark glyphs, light page. Otsu
    picks the cut per cell, which absorbs the brighter "highlighted" rows that
    appear in most screenshots without a hand-tuned constant.
    """
    _, binary = cv2.threshold(gray, 0, 255,
                              cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def denoise(binary):
    """Drop ink blobs too small to be part of a glyph.

    Whatever the threshold picks up from the dithered panel survives as isolated
    specks a pixel or two across. Tesseract treats them as punctuation or as
    stroke fragments, which is how "0" becomes "o." or "6".

    DESIGN DECISION: connected-component area filtering rather than a median
    blur or morphological opening. Both of those are shape operations - they
    thin real strokes at the same time as they erase specks, and at this glyph
    size the strokes cannot spare the pixels. Removing whole components below an
    area cutoff leaves every surviving glyph bit-for-bit intact.
    """
    # The image is dark-on-light, so ink is the zero pixels; connected component
    # labelling works on the non-zero ones.
    ink = (binary == 0).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)

    areas = stats[:, cv2.CC_STAT_AREA]
    # Label 0 is the background, which is far larger than the cutoff and so is
    # never selected here.
    too_small = np.flatnonzero(areas < MIN_COMPONENT_AREA)
    if too_small.size == 0:
        return binary

    cleaned = binary.copy()
    cleaned[np.isin(labels, too_small)] = 255  # repaint speck as page
    return cleaned


def pad(image, thresholded):
    """Add the quiet border Tesseract needs around the text.

    White when the cell is already binarized. Otherwise the cell is still
    light-on-dark, and a white frame would read as a page edge cutting through
    the line, so it is padded with its own median instead - which keeps
    stage-ablation runs in benchmark.py honest.
    """
    value = 255 if thresholded else int(np.median(image))
    return cv2.copyMakeBorder(image, PAD, PAD, PAD, PAD,
                              cv2.BORDER_CONSTANT, value=value)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def preprocess_cell(patch, stages=STAGES):
    """Run a cropped cell through the pipeline and return it OCR-ready.

    `stages` exists so benchmark.py can measure one stage at a time; production
    callers take the default, which is all of them.
    """
    stages = frozenset(stages)

    if "grayscale" in stages:
        patch = to_grayscale(patch)
    if "upscale" in stages:
        patch = upscale(patch)
    if "contrast" in stages:
        patch = enhance_contrast(patch)

    thresholded = "threshold" in stages
    if thresholded:
        patch = binarize(patch)
        if "denoise" in stages:
            # Denoising is defined on ink components, so it only means anything
            # once the ink has been separated from the panel.
            patch = denoise(patch)

    return pad(patch, thresholded)
