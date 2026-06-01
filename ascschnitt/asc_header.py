from __future__ import annotations

from pathlib import Path

from .models import AscGridHeader

_HEADER_KEYS = {
    "ncols",
    "nrows",
    "xllcorner",
    "yllcorner",
    "xllcenter",
    "yllcenter",
    "cellsize",
    "nodata_value",
}


def split_whitespace(line: str) -> list[str]:
    return line.split()


def parse_float(text: str) -> float:
    """Parse ASC numeric text, accepting Austrian/German decimal commas."""

    return float(text.strip().replace(",", "."))


def read_header(file_path: str | Path) -> AscGridHeader:
    path = Path(file_path)
    values: dict[str, str] = {}
    header_line_count = 0

    with path.open("r", encoding="utf-8-sig") as reader:
        for line in reader:
            parts = split_whitespace(line)
            if not parts:
                header_line_count += 1
                continue

            key = parts[0].lower()
            if key not in _HEADER_KEYS:
                break

            if len(parts) < 2:
                raise ValueError(f"Invalid ASC header line in {path}: {line.rstrip()}")

            values[key] = parts[1]
            header_line_count += 1

    def required(key: str) -> str:
        try:
            return values[key]
        except KeyError as exc:
            raise ValueError(f"ASC header is missing {key}: {path}") from exc

    ncols = int(required("ncols"))
    nrows = int(required("nrows"))
    cellsize = parse_float(required("cellsize"))
    nodata = parse_float(values.get("nodata_value", "-9999"))

    if ncols <= 0 or nrows <= 0:
        raise ValueError(f"ASC ncols/nrows must be positive: {path}")
    if cellsize <= 0:
        raise ValueError(f"ASC cellsize must be positive: {path}")

    if "xllcorner" in values:
        xllcorner = parse_float(values["xllcorner"])
    elif "xllcenter" in values:
        xllcorner = parse_float(values["xllcenter"]) - 0.5 * cellsize
    else:
        raise ValueError(f"ASC header is missing xllcorner/xllcenter: {path}")

    if "yllcorner" in values:
        yllcorner = parse_float(values["yllcorner"])
    elif "yllcenter" in values:
        yllcorner = parse_float(values["yllcenter"]) - 0.5 * cellsize
    else:
        raise ValueError(f"ASC header is missing yllcorner/yllcenter: {path}")

    return AscGridHeader(
        file_path=path,
        header_line_count=header_line_count,
        ncols=ncols,
        nrows=nrows,
        xllcorner=xllcorner,
        yllcorner=yllcorner,
        cellsize=cellsize,
        nodata=nodata,
    )
