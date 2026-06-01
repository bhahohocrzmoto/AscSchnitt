from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

from .csv_export import format_number
from .models import SamplePoint2d, SchnittSample

PROFILE_LAYER = "ASC_SCHNITT_PROFILE"
ROUTE_LAYER = "ASC_SCHNITT_ROUTE"
TEXT_LAYER = "ASC_SCHNITT_TEXT"


def export_dxf(
    path: str | Path,
    samples: list[SchnittSample],
    start: SamplePoint2d,
    end: SamplePoint2d,
    insertion: SamplePoint2d,
    datum: float,
    vertical_exaggeration: float,
) -> None:
    """Write a small ASCII DXF containing the plan route, profile, and labels."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    valid_z = [sample.z for sample in samples if sample.z is not None]
    min_z = min(valid_z) if valid_z else math.nan
    max_z = max(valid_z) if valid_z else math.nan
    length = samples[-1].distance if samples else 0.0

    lines: list[str] = []
    _section(lines, "HEADER")
    _pair(lines, 9, "$ACADVER")
    _pair(lines, 1, "AC1009")
    _endsec(lines)

    _section(lines, "TABLES")
    _pair(lines, 0, "TABLE")
    _pair(lines, 2, "LAYER")
    _pair(lines, 70, 3)
    _layer(lines, PROFILE_LAYER, 1)
    _layer(lines, ROUTE_LAYER, 3)
    _layer(lines, TEXT_LAYER, 7)
    _pair(lines, 0, "ENDTAB")
    _endsec(lines)

    _section(lines, "ENTITIES")
    _line(lines, ROUTE_LAYER, start.x, start.y, end.x, end.y)
    _text(lines, TEXT_LAYER, start.x, start.y, "Start")
    _text(lines, TEXT_LAYER, end.x, end.y, "End")

    for segment in _valid_profile_segments(samples, insertion, datum, vertical_exaggeration):
        _polyline(lines, PROFILE_LAYER, segment)

    label_y = insertion.y - 4.0
    labels = [
        f"Profile length: {format_number(length)} m",
        f"Min elevation: {format_number(min_z)} m" if valid_z else "Min elevation: n/a",
        f"Max elevation: {format_number(max_z)} m" if valid_z else "Max elevation: n/a",
        f"Datum: {format_number(datum)} m",
        f"Vertical exaggeration: {format_number(vertical_exaggeration)}",
    ]
    for index, label in enumerate(labels):
        _text(lines, TEXT_LAYER, insertion.x, label_y - index * 4.0, label)

    _endsec(lines)
    _pair(lines, 0, "EOF")

    output.write_text("\n".join(lines) + "\n", encoding="ascii", errors="xmlcharrefreplace")


def automatic_datum(samples: Iterable[SchnittSample]) -> float:
    valid = [sample.z for sample in samples if sample.z is not None]
    if not valid:
        raise ValueError("No valid terrain samples found along the section line.")
    return math.floor(min(valid) / 10.0) * 10.0


def _valid_profile_segments(
    samples: list[SchnittSample], insertion: SamplePoint2d, datum: float, vertical_exaggeration: float
) -> Iterable[list[tuple[float, float]]]:
    current: list[tuple[float, float]] = []
    for sample in samples:
        if sample.z is None:
            if len(current) >= 2:
                yield current
            current = []
            continue

        current.append((insertion.x + sample.distance, insertion.y + (sample.z - datum) * vertical_exaggeration))

    if len(current) >= 2:
        yield current


def _section(lines: list[str], name: str) -> None:
    _pair(lines, 0, "SECTION")
    _pair(lines, 2, name)


def _endsec(lines: list[str]) -> None:
    _pair(lines, 0, "ENDSEC")


def _layer(lines: list[str], name: str, color: int) -> None:
    _pair(lines, 0, "LAYER")
    _pair(lines, 2, name)
    _pair(lines, 70, 0)
    _pair(lines, 62, color)
    _pair(lines, 6, "CONTINUOUS")


def _line(lines: list[str], layer: str, x1: float, y1: float, x2: float, y2: float) -> None:
    _pair(lines, 0, "LINE")
    _pair(lines, 8, layer)
    _pair(lines, 10, x1)
    _pair(lines, 20, y1)
    _pair(lines, 30, 0.0)
    _pair(lines, 11, x2)
    _pair(lines, 21, y2)
    _pair(lines, 31, 0.0)


def _polyline(lines: list[str], layer: str, points: list[tuple[float, float]]) -> None:
    _pair(lines, 0, "POLYLINE")
    _pair(lines, 8, layer)
    _pair(lines, 66, 1)
    _pair(lines, 70, 0)
    for x, y in points:
        _pair(lines, 0, "VERTEX")
        _pair(lines, 8, layer)
        _pair(lines, 10, x)
        _pair(lines, 20, y)
        _pair(lines, 30, 0.0)
    _pair(lines, 0, "SEQEND")


def _text(lines: list[str], layer: str, x: float, y: float, text: str, height: float = 2.5) -> None:
    _pair(lines, 0, "TEXT")
    _pair(lines, 8, layer)
    _pair(lines, 10, x)
    _pair(lines, 20, y)
    _pair(lines, 30, 0.0)
    _pair(lines, 40, height)
    _pair(lines, 1, text)


def _pair(lines: list[str], code: int, value: object) -> None:
    lines.append(str(code))
    if isinstance(value, float):
        lines.append(format_number(value))
    else:
        lines.append(str(value))
