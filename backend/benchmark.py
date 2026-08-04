"""
Milestone 2 acceptance test - does preprocessing actually improve OCR accuracy?

Runs the extractor over the sample screenshots several times, enabling one more
preprocessing stage each run, and scores every field against ground_truth.json.

    python benchmark.py                    # cumulative ablation, all samples
    python benchmark.py --leave-one-out    # what each stage is worth on its own
    python benchmark.py --write-truth out.json   # seed a ground-truth file

DESIGN DECISION: the ablation is cumulative rather than one-stage-at-a-time,
because the stages are not independent - denoise has nothing to act on until
threshold has run, and contrast only matters through the threshold it feeds.
Cumulative rows answer the question that actually matters ("is the pipeline
worth having, and does each stage earn its place"). --leave-one-out covers the
other reading: pull one stage out of the finished pipeline and see what breaks.
"""

import argparse
import json
from pathlib import Path

from extract import extract
from preprocessing import STAGES

# Anchored to the repo root rather than the working directory: the sample set and
# its ground truth are shared test data that live above backend/, so this script
# runs the same from either directory.
REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = REPO_ROOT / "sample pictures"
TRUTH_PATH = REPO_ROOT / "ground_truth.json"

FIELDS = ("name", "stat_1", "stat_2", "stat_3")

# DESIGN DECISION: overall accuracy alone would flatter every configuration.
# Roughly four fifths of the stat cells in the sample set are "0", and a stat
# cell that OCRs to garbage also lands on 0 once to_int() strips the non-digits.
# A pipeline that reads nothing at all therefore scores most of the stat columns
# correctly by accident. These buckets separate the fields where being right
# means something:
#   name     - 166 free-form strings, no modal answer to fall into
#   stat!=0  - the stat cells that actually carry a value
#   stat==0  - reported for completeness; near-100% even with no preprocessing
BUCKETS = ("name", "stat!=0", "stat==0")


def bucket_of(field, expected):
    if field == "name":
        return "name"
    return "stat!=0" if expected else "stat==0"


def run(stages, truth, sample_dir):
    """Score one preprocessing configuration across every sample.

    Returns ({bucket: (correct, total)}, misses).

    Rows are compared by grid position - keep_empty=True guarantees one record
    per grid row, so a configuration that reads a name as blank is penalised for
    that field alone instead of shifting every row below it.
    """
    tally = {bucket: [0, 0] for bucket in BUCKETS}
    misses = []
    for filename, truth_rows in truth.items():
        rows = extract(str(sample_dir / filename), stages=stages, keep_empty=True)
        for index, expected in enumerate(truth_rows):
            actual = rows[index] if index < len(rows) else {}
            for field in FIELDS:
                counts = tally[bucket_of(field, expected[field])]
                counts[1] += 1
                if actual.get(field) == expected[field]:
                    counts[0] += 1
                else:
                    misses.append((filename, index, field,
                                   expected[field], actual.get(field)))
    return {b: tuple(c) for b, c in tally.items()}, misses


def cumulative_configs():
    """(label, stages) for the empty pipeline, then one stage added at a time."""
    configs = [("raw crop (no preprocessing)", ())]
    for count in range(1, len(STAGES) + 1):
        enabled = STAGES[:count]
        configs.append(("+ " + enabled[-1], enabled))
    return configs


def leave_one_out_configs():
    """(label, stages) for the full pipeline minus each stage in turn."""
    configs = [("full pipeline", STAGES)]
    for dropped in STAGES:
        remaining = tuple(s for s in STAGES if s != dropped)
        configs.append((f"- {dropped}", remaining))
    return configs


def report(configs, truth, sample_dir, show_misses):
    header = f"{'configuration':<28}" + "".join(f"{b:>12}" for b in BUCKETS)
    print(header + f"{'overall':>12}{'delta':>8}")
    print("-" * len(header + f"{'overall':>12}{'delta':>8}"))

    baseline = None
    for label, stages in configs:
        tally, misses = run(stages, truth, sample_dir)
        cells = ""
        for bucket in BUCKETS:
            correct, total = tally[bucket]
            cells += f"{correct / total:>11.1%} " if total else f"{'-':>12}"

        correct = sum(c for c, _ in tally.values())
        total = sum(t for _, t in tally.values())
        overall = correct / total
        if baseline is None:
            baseline, delta = overall, ""
        else:
            delta = f"{overall - baseline:+.1%}"
        print(f"{label:<28}{cells}{overall:>11.1%} {delta:>7}")

        if show_misses and misses:
            for filename, row, field, want, got in misses[:25]:
                print(f"    {filename[-10:]} row {row:>2} {field:<7} "
                      f"want {want!r:<16} got {got!r}")
            if len(misses) > 25:
                print(f"    ... and {len(misses) - 25} more")


def write_truth(path, sample_dir):
    """Dump the full pipeline's output as a ground-truth skeleton.

    This is a starting point that MUST be hand-checked against the screenshots -
    truth generated by the system under test would otherwise score 100% by
    construction and prove nothing.
    """
    truth = {
        image.name: extract(str(image))
        for image in sorted(sample_dir.glob("*.png"))
    }
    path.write_text(json.dumps(truth, indent=2), encoding="utf-8")
    rows = sum(len(v) for v in truth.values())
    print(f"wrote {path} - {len(truth)} screenshots, {rows} rows. "
          f"Verify it against the images before trusting any score.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", default=SAMPLE_DIR, type=Path,
                        help="directory of screenshots")
    parser.add_argument("--truth", default=TRUTH_PATH, type=Path,
                        help="ground-truth JSON keyed by filename")
    parser.add_argument("--leave-one-out", action="store_true",
                        help="drop one stage from the full pipeline at a time")
    parser.add_argument("--misses", action="store_true",
                        help="list the fields each configuration got wrong")
    parser.add_argument("--write-truth", metavar="PATH", type=Path,
                        help="seed a ground-truth file from the current output")
    args = parser.parse_args()

    if args.write_truth:
        write_truth(args.write_truth, args.samples)
        return

    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    # Keys starting with "_" are notes for whoever maintains the file by hand.
    truth = {k: v for k, v in truth.items() if not k.startswith("_")}
    configs = leave_one_out_configs() if args.leave_one_out else cumulative_configs()
    report(configs, truth, args.samples, args.misses)


if __name__ == "__main__":
    main()
