"""Reorder cached legacy Hastati facets into the canonical AoE runtime order."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from aoe2.facet_mapping import FACET_COUNT, legacy_source_facet, soldier_yaw_degrees
from aoe2.sld import parse_sld, serialize_sld


def reorder(document, frames_per_facet: int):
    if frames_per_facet < 1:
        raise ValueError("frames per facet must be positive")
    if len(document.frames) != FACET_COUNT * frames_per_facet:
        raise ValueError("SLD frame count is not 16 facets x frames per facet")
    source = document.frames
    reordered = []
    for runtime_facet in range(FACET_COUNT):
        source_facet = legacy_source_facet(runtime_facet)
        start = source_facet * frames_per_facet
        reordered.extend(copy.deepcopy(source[start:start + frames_per_facet]))
    for index, frame in enumerate(reordered):
        frame.frame_index = index
    document.frames = reordered
    document.facet_count = FACET_COUNT
    return document


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames-per-facet", type=int, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    corrected = reorder(parse_sld(args.input.read_bytes()), args.frames_per_facet)
    raw = serialize_sld(corrected)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(raw)
    report = {
        "format": "rome2aoe2.canonical-facet-reorder",
        "version": 1,
        "input": str(args.input),
        "output": str(args.output),
        "frames_per_facet": args.frames_per_facet,
        "facets": [
            {
                "runtime_facet": facet,
                "legacy_source_facet": legacy_source_facet(facet),
                "soldier_yaw_degrees": soldier_yaw_degrees(facet),
            }
            for facet in range(FACET_COUNT)
        ],
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
