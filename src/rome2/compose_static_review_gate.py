"""Compose deterministic human-review sheets and inventory static gate images."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def sheet(paths, output, labels, columns=2):
    images = [Image.open(path).convert("RGBA") for path in paths]
    width = max(image.width for image in images); height = max(image.height for image in images)
    rows = (len(images) + columns - 1) // columns
    canvas = Image.new("RGBA", (width * columns, (height + 44) * rows), (20, 22, 27, 255))
    draw = ImageDraw.Draw(canvas)
    for index, (image, label) in enumerate(zip(images, labels)):
        x = index % columns * width; y = index // columns * (height + 44)
        canvas.alpha_composite(image, (x + (width-image.width)//2, y))
        draw.text((x + 16, y + height + 13), label, fill=(235, 235, 235, 255))
    canvas.save(output)


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("root", type=Path)
    args = parser.parse_args(); root = args.root
    directions = [root / f"static-{angle:03d}.png" for angle in (45, 135, 225, 315)]
    sheet(directions, root / "static-directions-contact-sheet.png",
          ["045", "135", "225", "315"])
    sheet([root / "review-shield-current.png", root / "review-shield-infantry-static-review-v1.png"],
          root / "review-shield-lighting-ab.png", ["legacy review", "infantry_static_review_v1"])
    sheet([root / "review-helmet-current.png", root / "review-helmet-infantry-static-review-v1.png"],
          root / "review-helmet-lighting-ab.png", ["legacy review", "infantry_static_review_v1"])
    sheet([root / "gladius-grip-before.png", root / "gladius-grip-after.png"],
          root / "gladius-grip-before-after.png",
          ["before: source pivot/socket only", "after: generic grip class solver"])
    names = [f"static-{angle:03d}.png" for angle in (45, 135, 225, 315)] + [
        "static-diagnostic.png", "static-directions-contact-sheet.png",
        "static-equipment-grip-close.png", "review-shield-lighting-ab.png",
        "review-helmet-lighting-ab.png", "gladius-grip-before-after.png"]
    records = []
    for name in names:
        path = root / name
        with Image.open(path) as image:
            records.append({"path": str(path.resolve()), "bytes": path.stat().st_size,
                            "dimensions": list(image.size), "nonzero": path.stat().st_size > 0})
    report = {"format": "rome2aoe2.static-review-gate", "version": 1, "outputs": records}
    (root / "static-review-gate.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__": main()
