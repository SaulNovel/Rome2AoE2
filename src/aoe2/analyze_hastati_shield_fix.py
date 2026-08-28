"""Build shield-only before/after evidence for the controlled faction-mask fix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw

from aoe2.facet_mapping import legacy_source_facet


def frame(root: Path, facet: int) -> Path:
    return root / "master" / f"idle-direction-{facet:02d}-frame-000.png"


def changed_bounds(before: Image.Image, after: Image.Image, threshold: int = 2):
    changed = []
    for index, (left, right) in enumerate(zip(before.get_flattened_data(), after.get_flattened_data())):
        if max(abs(left[channel] - right[channel]) for channel in range(4)) > threshold:
            changed.append((index % before.width, index // before.width))
    if not changed:
        return None, 0
    return (min(x for x, _ in changed), min(y for _, y in changed),
            max(x for x, _ in changed) + 1, max(y for _, y in changed) + 1), len(changed)


def expand(box, width: int, height: int, margin: int = 24):
    return (max(0, box[0] - margin), max(0, box[1] - margin),
            min(width, box[2] + margin), min(height, box[3] + margin))


def checker(image: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", image.size)
    draw = ImageDraw.Draw(canvas)
    step = max(8, image.width // 20)
    for y in range(0, image.height, step):
        for x in range(0, image.width, step):
            value = 58 if (x // step + y // step) % 2 else 86
            draw.rectangle((x, y, x + step - 1, y + step - 1), fill=(value, value, value, 255))
    canvas.alpha_composite(image)
    canvas.thumbnail((size, size), Image.Resampling.NEAREST)
    result = Image.new("RGB", (size, size), (24, 24, 24))
    result.paste(canvas.convert("RGB"), ((size - canvas.width) // 2, (size - canvas.height) // 2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-root", type=Path, required=True)
    parser.add_argument("--after-root", type=Path, required=True)
    parser.add_argument("--sld-report", type=Path, required=True)
    parser.add_argument("--source-diffuse", type=Path, required=True)
    parser.add_argument("--source-mask", type=Path, required=True)
    parser.add_argument("--rome-reference", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--facets", default="0,2,4,6,8,10,12,14")
    args = parser.parse_args()
    facets = [int(value) for value in args.facets.split(",")]
    args.output_root.mkdir(parents=True, exist_ok=True)
    cell, label = 360, 30
    sheet = Image.new("RGB", (3 * cell, len(facets) * (cell + label)), (24, 24, 24))
    draw = ImageDraw.Draw(sheet)
    records = []
    representative = None
    for row, runtime_facet in enumerate(facets):
        source_facet = legacy_source_facet(runtime_facet)
        before = Image.open(frame(args.before_root, source_facet)).convert("RGBA")
        after = Image.open(frame(args.after_root, runtime_facet)).convert("RGBA")
        if before.size != after.size:
            raise ValueError("before/after canvases differ")
        box, changed = changed_bounds(before, after)
        if box is None:
            raise AssertionError(f"facet {runtime_facet} has no changed pixels")
        crop = expand(box, *before.size)
        difference = Image.new("RGBA", before.size)
        values = []
        for left, right in zip(before.get_flattened_data(), after.get_flattened_data()):
            delta = tuple(min(255, abs(left[i] - right[i]) * 4) for i in range(3))
            values.append((*delta, max(left[3], right[3])))
        difference.putdata(values)
        views = (("BEFORE", before.crop(crop)), ("AFTER", after.crop(crop)),
                 ("4x RGB DIFFERENCE", difference.crop(crop)))
        y = row * (cell + label)
        for column, (caption, image) in enumerate(views):
            x = column * cell
            draw.text((x + 8, y + 8), f"facet {runtime_facet:02d} {caption}", fill=(245, 245, 245))
            sheet.paste(checker(image, cell), (x, y + label))
        records.append({"runtime_facet": runtime_facet, "accepted_source_facet": source_facet,
                        "changed_bounds_master": list(box), "changed_pixels": changed,
                        "canvas_pixels": before.width * before.height})
        if runtime_facet == 4:
            representative = (before.crop(crop), after.crop(crop))
    sheet.save(args.output_root / "shield-before-after-directions.png")
    sld = json.loads(args.sld_report.read_text(encoding="utf-8"))
    if representative is None:
        raise AssertionError("representative facet 4 was not included")
    source_mask = Image.open(args.source_mask).convert("RGBA")
    source_mask.putalpha(255)
    stages = [
        ("ROME II DIFFUSE", Image.open(args.source_diffuse).convert("RGBA")),
        ("ROME II FACTION MASK", source_mask),
        ("ROME-AUTHORED REFERENCE", Image.open(args.rome_reference).convert("RGBA")),
        ("PRODUCTION BEFORE", representative[0]),
        ("PROPOSED RENDER", representative[1]),
        ("DECODED SLD x1", Image.open(args.sld_report.parent / "decoded-x1.png").convert("RGBA")),
        ("DECODED SLD x2", Image.open(args.sld_report.parent / "decoded-x2.png").convert("RGBA")),
    ]
    stage_cell, stage_label = 360, 34
    stage_sheet = Image.new("RGB", (4 * stage_cell, 2 * (stage_cell + stage_label)), (24, 24, 24))
    stage_draw = ImageDraw.Draw(stage_sheet)
    for index, (caption, image) in enumerate(stages):
        column, row = index % 4, index // 4
        x, y = column * stage_cell, row * (stage_cell + stage_label)
        stage_draw.text((x + 8, y + 9), caption, fill=(245, 245, 245))
        stage_sheet.paste(checker(image, stage_cell), (x, y + stage_label))
    stage_sheet.save(args.output_root / "shield-pipeline-stage-comparison.png")
    report = {
        "format": "rome2aoe2.hastati-shield-fix-proof", "version": 1,
        "root_cause": "DecalDirtmap shield faction mask received a zero colour table",
        "fix": "apply the established early-scutum C0,C2,C1 faction slot order",
        "render_change_scope": "DecalDirtmap pixels only", "records": records,
        "sld_round_trip": sld["records"],
        "artifacts": ["shield-before-after-directions.png", "shield-pipeline-stage-comparison.png",
                      "sld-gate/source-vs-decoded-contact-sheet.png"],
    }
    (args.output_root / "shield-fix-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
