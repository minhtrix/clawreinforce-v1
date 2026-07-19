from __future__ import annotations

import csv
import json
from pathlib import Path

from clawreinforce.core.arena import BenchReport


def export_csv(report: BenchReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["tier", "trial", "without_skill", "with_skill", "uplift", "status", "reason", "input_tokens", "output_tokens", "cost_usd"],
        )
        writer.writeheader()
        for row in report.rows:
            values = {name: getattr(row, name) for name in writer.fieldnames}
            if isinstance(values["reason"], dict):
                values["reason"] = json.dumps(values["reason"], ensure_ascii=False, separators=(",", ":"))
            writer.writerow(values)
    return path


def export_png(report: BenchReport, path: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    width = 960
    height = 190 + max(1, len(report.rows)) * 42
    image = Image.new("RGB", (width, height), "#0d1017")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=16)
    draw.text((32, 24), "clawreinforce arena", fill="#f4f5f7", font=font)
    draw.text((32, 54), f"{report.task} × {report.skill}", fill="#aeb4c2", font=font)
    draw.text((32, 86), "WITHOUT", fill="#fb7185", font=font)
    draw.text((180, 86), "WITH SKILL", fill="#7c6cff", font=font)
    y = 128
    for row in report.rows:
        label = f"{row.tier} · trial {row.trial}"
        draw.text((32, y), label, fill="#dce0e8", font=font)
        if row.without_skill is not None:
            draw.rectangle((420, y, 420 + int(row.without_skill * 180), y + 14), fill="#fb7185")
        if row.with_skill is not None:
            draw.rectangle((620, y, 620 + int(row.with_skill * 180), y + 14), fill="#7c6cff")
        draw.text((820, y), "n/a" if row.uplift is None else f"{row.uplift:+.2f}", fill="#8ee6b0", font=font)
        y += 42
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return path
