from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SamplePoint2d:
    """A projected 2D world coordinate."""

    x: float
    y: float


@dataclass(frozen=True)
class SchnittSample:
    """One sampled station along a terrain section."""

    distance: float
    x: float
    y: float
    z: float | None
    source_file: str


@dataclass(frozen=True)
class AscGridHeader:
    """Metadata and footprint for one Arc/Info ASCII Grid tile."""

    file_path: Path
    header_line_count: int
    ncols: int
    nrows: int
    xllcorner: float
    yllcorner: float
    cellsize: float
    nodata: float

    @property
    def xmin(self) -> float:
        return self.xllcorner

    @property
    def xmax(self) -> float:
        return self.xllcorner + self.ncols * self.cellsize

    @property
    def ymin(self) -> float:
        return self.yllcorner

    @property
    def ymax(self) -> float:
        return self.yllcorner + self.nrows * self.cellsize

    def contains(self, x: float, y: float) -> bool:
        return self.xmin <= x <= self.xmax and self.ymin <= y <= self.ymax

    def contains_interior(self, x: float, y: float) -> bool:
        return self.xmin < x < self.xmax and self.ymin < y < self.ymax

    def intersects(self, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
        return self.xmin <= xmax and self.xmax >= xmin and self.ymin <= ymax and self.ymax >= ymin
