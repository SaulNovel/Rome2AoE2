from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "build/python-deps/pillow"))

from PIL import Image, ImageDraw

from rome2aoe2.animation import CATEGORIES, discover, enrich_metadata, preview_cache_identity
from rome2aoe2.cli import load_default_catalog
from rome2aoe2.preview import CACHE


MANIFEST = ROOT / "build/cache/rome2aoe2/principes-default-manifest.json"
OUTPUT = ROOT / "build/validation/rome2aoe2/principes-animation-human-review"


def death_diagnostics(stem: str) -> dict:
    report = ROOT / "build/validation/hastati-gameplay/native-death-investigation/body-gates" / stem / "report.json"
    if not report.is_file():
        return {"grounding": "not measured", "terminal_pose_stability": "not measured",
                "weapon_release_drop": "not established by source metadata"}
    doc = json.loads(report.read_text(encoding="utf-8"))
    samples = doc.get("samples", [])
    terminal = None
    if len(samples) >= 2:
        points = ("hips", "head")
        terminal = max(math.dist(samples[-1][p], samples[-2][p]) for p in points)
    ground = float(doc["final_ground_min_z"])
    return {
        "grounding": {"final_geometry_min_z": ground, "assessment": "grounded" if abs(ground) <= .065 else "review"},
        "terminal_pose_stability": {"last_sample_head_or_hips_translation_delta": terminal,
                                    "assessment": "stable at sampled phases" if terminal is not None and terminal <= .08 else "review"},
        "weapon_release_drop": "not derivable from fragment/body-gate metadata; inspect the authoritative contact sheet",
    }


def overview(category: str, rows: list[dict]) -> str:
    selected = [0, 2, 4, 6, 8]
    thumb_w, thumb_h, label_h = 180, 180, 30
    canvas = Image.new("RGB", (thumb_w * len(selected), (thumb_h + label_h) * len(rows)), (28, 28, 28))
    draw = ImageDraw.Draw(canvas)
    for row_index, row in enumerate(rows):
        sheet = Image.open(row["preview"]).convert("RGB")
        cell_w, cell_h = sheet.width // 3, sheet.height // 3
        y = row_index * (thumb_h + label_h)
        draw.text((8, y + 7), f"[{row['id']}] {row['filename']}", fill="white")
        for column, phase in enumerate(selected):
            x0, y0 = phase % 3 * cell_w, phase // 3 * cell_h
            crop = sheet.crop((x0, y0, x0 + cell_w, y0 + cell_h))
            crop.thumbnail((thumb_w, thumb_h))
            canvas.paste(crop, (column * thumb_w + (thumb_w - crop.width) // 2, y + label_h))
    name = "death-shortlist-overview.png" if category == "death" else f"{category}-candidates-overview.png"
    target = OUTPUT / name
    canvas.save(target)
    return str(target)


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    unit = load_default_catalog(None).resolve("Rom_Principes", "rom_rome")
    groups = enrich_metadata(discover(unit))
    package = {"format": "rome2aoe2.animation-human-review", "unit": "Rom_Principes", "categories": {}}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        rows = []
        for index, candidate in enumerate(groups[category].candidates, 1):
            contact = CACHE / preview_cache_identity(manifest, candidate) / "contact-sheet.png"
            rendered = contact if index <= groups[category].shortlist_size and contact.is_file() else None
            row = {
                "id": index, "filename": Path(candidate.resolved_asset).name,
                "asset": candidate.resolved_asset, "states": list(candidate.states),
                "frames": candidate.frame_count, "fps": candidate.fps, "duration": candidate.duration,
                "root_displacement": candidate.root_displacement,
                "horizontal_displacement": candidate.horizontal_displacement,
                "approximate_speed": candidate.locomotion_speed,
                "score": candidate.score, "reasons": list(candidate.suitability),
                "auto_recommended": index == 1, "preview": str(rendered) if rendered else None,
                "preview_status": "VALID native-basis" if rendered else "not rendered (show-more candidate)",
            }
            if category == "attack":
                row.update({"synchronized_context_penalty": -20 if "synchronized" in candidate.context_tags else 0,
                            "attack_style": "synchronized melee; thrust/slash style not derivable from current source evidence"})
            if category == "death":
                row.update(death_diagnostics(Path(candidate.resolved_asset).stem))
            rows.append(row)
        rendered_rows = [row for row in rows if row["preview"]]
        package["categories"][category] = {
            "candidate_count": len(rows), "shortlist_count": len(rendered_rows),
            "additional_count": len(rows) - len(rendered_rows), "auto_recommended_id": 1,
            "overview": overview(category, rendered_rows), "candidates": rows,
        }
    (OUTPUT / "candidate-index.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT / "candidate-index.json")


if __name__ == "__main__":
    main()
