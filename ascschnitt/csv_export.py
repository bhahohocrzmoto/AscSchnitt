from __future__ import annotations

import csv
from pathlib import Path

from .models import SchnittSample


def format_number(value: float) -> str:
    text = f"{value:.3f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def export_csv(path: str | Path, samples: list[SchnittSample]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["distance_m", "x", "y", "z_m", "source_asc_file"])
        for sample in samples:
            writer.writerow(
                [
                    format_number(sample.distance),
                    format_number(sample.x),
                    format_number(sample.y),
                    "" if sample.z is None else format_number(sample.z),
                    sample.source_file,
                ]
            )
