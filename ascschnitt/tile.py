from __future__ import annotations

import math
from dataclasses import dataclass

from .asc_header import parse_float, split_whitespace
from .models import AscGridHeader


@dataclass
class AscGridTile:
    header: AscGridHeader
    values: list[list[float]]

    @classmethod
    def load(cls, header: AscGridHeader) -> "AscGridTile":
        values: list[list[float]] = []
        with header.file_path.open("r", encoding="utf-8-sig") as reader:
            for _ in range(header.header_line_count):
                if reader.readline() == "":
                    raise ValueError(f"ASC file ended inside header: {header.file_path}")

            for row in range(header.nrows):
                line = reader.readline()
                if line == "":
                    raise ValueError(f"ASC file ended before all raster rows were read: {header.file_path}")

                parts = split_whitespace(line)
                if len(parts) < header.ncols:
                    raise ValueError(
                        f"ASC row {row} has {len(parts)} values; expected {header.ncols}: {header.file_path}"
                    )
                values.append([parse_float(part) for part in parts[: header.ncols]])

        return cls(header=header, values=values)

    def sample(self, x: float, y: float) -> float | None:
        bilinear = self.sample_bilinear(x, y)
        return bilinear if bilinear is not None else self.sample_nearest(x, y)

    def sample_nearest(self, x: float, y: float) -> float | None:
        col_float, row_float = self._float_indices(x, y)
        col = _nearest_index(col_float, self.header.ncols)
        row = _nearest_index(row_float, self.header.nrows)
        if col is None or row is None:
            return None

        value = self.values[row][col]
        return None if self._is_nodata(value) else value

    def sample_bilinear(self, x: float, y: float) -> float | None:
        col_float, row_float = self._float_indices(x, y)
        col0 = math.floor(col_float)
        row0 = math.floor(row_float)
        col1 = col0 + 1
        row1 = row0 + 1

        if row0 < 0 or row1 >= self.header.nrows or col0 < 0 or col1 >= self.header.ncols:
            return None

        z00 = self.values[row0][col0]
        z10 = self.values[row0][col1]
        z01 = self.values[row1][col0]
        z11 = self.values[row1][col1]

        if any(self._is_nodata(value) for value in (z00, z10, z01, z11)):
            return None

        dx = col_float - col0
        dy = row_float - row0
        z_top = z00 * (1.0 - dx) + z10 * dx
        z_bottom = z01 * (1.0 - dx) + z11 * dx
        return z_top * (1.0 - dy) + z_bottom * dy

    def _float_indices(self, x: float, y: float) -> tuple[float, float]:
        col_float = (x - (self.header.xllcorner + 0.5 * self.header.cellsize)) / self.header.cellsize
        row_float = ((self.header.yllcorner + (self.header.nrows - 0.5) * self.header.cellsize) - y) / self.header.cellsize
        return col_float, row_float

    def _is_nodata(self, value: float) -> bool:
        return math.isnan(value) or abs(value - self.header.nodata) < 1e-9


def _nearest_index(float_index: float, count: int) -> int | None:
    eps = 1e-9
    if float_index < -0.5 - eps or float_index > count - 0.5 + eps:
        return None

    index = math.floor(float_index + 0.5)
    return min(max(index, 0), count - 1)
