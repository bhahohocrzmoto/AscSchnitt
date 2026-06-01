from __future__ import annotations

import math

from .index import AscGridIndex
from .models import AscGridHeader, SamplePoint2d, SchnittSample
from .tile import AscGridTile


class SectionSampler:
    """Samples a terrain section across one or more ASC tiles."""

    def __init__(self, index: AscGridIndex) -> None:
        self._index = index
        self._cache: dict[str, AscGridTile] = {}
        self.last_candidate_count = 0

    @property
    def loaded_tile_count(self) -> int:
        return len(self._cache)

    def sample_line(self, start: SamplePoint2d, end: SamplePoint2d, spacing: float) -> list[SchnittSample]:
        if spacing <= 0.0:
            raise ValueError("Sample spacing must be positive.")

        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        segment_count = 0 if length <= 0.0 else max(1, math.ceil(length / spacing))

        candidates = self._index.find_tiles_intersecting_bounding_box(
            min(start.x, end.x),
            min(start.y, end.y),
            max(start.x, end.x),
            max(start.y, end.y),
        )
        self.last_candidate_count = len(candidates)

        samples: list[SchnittSample] = []
        for i in range(segment_count + 1):
            distance = min(i * spacing, length)
            t = 0.0 if length <= 0.0 else distance / length
            x = start.x + t * dx
            y = start.y + t * dy

            header = _select_tile(candidates, x, y)
            if header is None:
                samples.append(SchnittSample(distance=distance, x=x, y=y, z=None, source_file=""))
                continue

            key = str(header.file_path)
            tile = self._cache.get(key)
            if tile is None:
                tile = AscGridTile.load(header)
                self._cache[key] = tile

            samples.append(SchnittSample(distance=distance, x=x, y=y, z=tile.sample(x, y), source_file=key))

        return samples


def _select_tile(candidates: list[AscGridHeader], x: float, y: float) -> AscGridHeader | None:
    boundary_match: AscGridHeader | None = None
    for header in candidates:
        if not header.contains(x, y):
            continue
        if header.contains_interior(x, y):
            return header
        if boundary_match is None or _is_lower_left(header, boundary_match):
            boundary_match = header
    return boundary_match


def _is_lower_left(candidate: AscGridHeader, current: AscGridHeader) -> bool:
    if candidate.xmin != current.xmin:
        return candidate.xmin < current.xmin
    return candidate.ymin < current.ymin
