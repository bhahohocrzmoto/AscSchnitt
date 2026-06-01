from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .asc_header import read_header
from .models import AscGridHeader


@dataclass
class AscGridIndex:
    headers: list[AscGridHeader] = field(default_factory=list)

    @classmethod
    def build_from_folder(cls, root_folder: str | Path) -> "AscGridIndex":
        root = Path(root_folder)
        if not root.is_dir():
            raise FileNotFoundError(root)

        return cls(headers=[read_header(path) for path in root.rglob("*.asc")])

    def find_tiles_intersecting_bounding_box(self, xmin: float, ymin: float, xmax: float, ymax: float) -> list[AscGridHeader]:
        return [header for header in self.headers if header.intersects(xmin, ymin, xmax, ymax)]

    def find_tile_containing_point(self, x: float, y: float) -> AscGridHeader | None:
        return next((header for header in self.headers if header.contains(x, y)), None)
