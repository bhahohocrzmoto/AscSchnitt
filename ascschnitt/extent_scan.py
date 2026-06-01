from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Iterator
from pathlib import Path

from .asc_header import parse_float, read_header
from .models import AscGridHeader


@dataclass(frozen=True)
class CoordinateSystemChoice:
    epsg: int
    label: str
    folder_name: str

    @property
    def display_name(self) -> str:
        return f"EPSG:{self.epsg} - {self.label} - {self.folder_name}"


GK_CHOICES: tuple[CoordinateSystemChoice, ...] = (
    CoordinateSystemChoice(31254, "MGI / Austria GK West", "m28"),
    CoordinateSystemChoice(31255, "MGI / Austria GK Central", "m31"),
    CoordinateSystemChoice(31256, "MGI / Austria GK East", "m34"),
)

GK_BY_EPSG: dict[int, CoordinateSystemChoice] = {choice.epsg: choice for choice in GK_CHOICES}


@dataclass(frozen=True)
class TileExtent:
    file_path: Path
    xmin: float
    xmax: float
    ymin: float
    ymax: float
    cellsize: float

    @classmethod
    def from_header(cls, header: AscGridHeader) -> "TileExtent":
        return cls(
            file_path=header.file_path,
            xmin=header.xmin,
            xmax=header.xmax,
            ymin=header.ymin,
            ymax=header.ymax,
            cellsize=header.cellsize,
        )

    def contains(self, x: float, y: float) -> bool:
        return self.xmin <= x <= self.xmax and self.ymin <= y <= self.ymax

    def intersects(self, xmin: float, ymin: float, xmax: float, ymax: float) -> bool:
        return self.xmin <= xmax and self.xmax >= xmin and self.ymin <= ymax and self.ymax >= ymin


@dataclass(frozen=True)
class ExtentScanResult:
    root_folder: Path
    epsg: int
    folder_name: str
    scan_folder: Path
    tiles: tuple[TileExtent, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def asc_file_count(self) -> int:
        return len(self.tiles)

    @property
    def xmin(self) -> float | None:
        return min((tile.xmin for tile in self.tiles), default=None)

    @property
    def xmax(self) -> float | None:
        return max((tile.xmax for tile in self.tiles), default=None)

    @property
    def ymin(self) -> float | None:
        return min((tile.ymin for tile in self.tiles), default=None)

    @property
    def ymax(self) -> float | None:
        return max((tile.ymax for tile in self.tiles), default=None)

    @property
    def min_cellsize(self) -> float | None:
        return min((tile.cellsize for tile in self.tiles), default=None)

    @property
    def max_cellsize(self) -> float | None:
        return max((tile.cellsize for tile in self.tiles), default=None)

    def point_tile(self, x: float, y: float) -> TileExtent | None:
        return next((tile for tile in self.tiles if tile.contains(x, y)), None)

    def line_bbox_tiles(self, start_x: float, start_y: float, end_x: float, end_y: float) -> list[TileExtent]:
        xmin, xmax = sorted((start_x, end_x))
        ymin, ymax = sorted((start_y, end_y))
        return [tile for tile in self.tiles if tile.intersects(xmin, ymin, xmax, ymax)]

    def overall_extent_intersects_line_bbox(self, start_x: float, start_y: float, end_x: float, end_y: float) -> bool:
        if not self.tiles:
            return False
        xmin, xmax = sorted((start_x, end_x))
        ymin, ymax = sorted((start_y, end_y))
        overall_xmin = min(tile.xmin for tile in self.tiles)
        overall_xmax = max(tile.xmax for tile in self.tiles)
        overall_ymin = min(tile.ymin for tile in self.tiles)
        overall_ymax = max(tile.ymax for tile in self.tiles)
        return overall_xmin <= xmax and overall_xmax >= xmin and overall_ymin <= ymax and overall_ymax >= ymin


def choice_for_epsg(epsg: int | str) -> CoordinateSystemChoice:
    parsed = int(str(epsg).replace("EPSG:", "").strip())
    try:
        return GK_BY_EPSG[parsed]
    except KeyError as exc:
        raise ValueError(f"Unsupported EPSG:{parsed}. Choose one of: {', '.join(str(choice.epsg) for choice in GK_CHOICES)}") from exc


def parse_user_float(text: str, field_name: str = "value") -> float:
    try:
        return parse_float(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be numeric.") from exc


def selected_epsg_folder(root_folder: str | Path, epsg: int | str) -> Path:
    choice = choice_for_epsg(epsg)
    return Path(root_folder) / choice.folder_name


def discover_gk_folders(root_folder: str | Path) -> dict[int, Path]:
    root = Path(root_folder)
    found: dict[int, Path] = {}
    if not root.is_dir():
        return found

    child_dirs = {
        child.name.lower(): child
        for child in root.iterdir()
        if child.is_dir() and "prjxml" not in child.name.lower()
    }
    for choice in GK_CHOICES:
        child = child_dirs.get(choice.folder_name.lower())
        if child is not None:
            found[choice.epsg] = child
    return found


def iter_relevant_asc_files(folder: str | Path) -> Iterator[Path]:
    root = Path(folder)
    if not root.is_dir():
        return

    for path in root.rglob("*.asc"):
        if not path.is_file():
            continue
        if any("prjxml" in part.lower() for part in path.parts):
            continue
        yield path


def scan_extent(root_folder: str | Path, epsg: int | str) -> ExtentScanResult:
    root = Path(root_folder)
    choice = choice_for_epsg(epsg)
    scan_folder = root / choice.folder_name
    warnings: list[str] = []
    tiles: list[TileExtent] = []

    if not root.is_dir():
        raise FileNotFoundError(f"ASC root folder does not exist or is not accessible: {root}")
    if not scan_folder.is_dir():
        return ExtentScanResult(
            root,
            choice.epsg,
            choice.folder_name,
            scan_folder,
            tuple(),
            (f"Folder not found: {scan_folder}",),
        )

    for path in iter_relevant_asc_files(scan_folder):
        try:
            tiles.append(TileExtent.from_header(read_header(path)))
        except (OSError, ValueError) as exc:
            warnings.append(f"Invalid or inaccessible ASC header skipped: {path} ({exc})")

    return ExtentScanResult(root, choice.epsg, choice.folder_name, scan_folder, tuple(tiles), tuple(warnings))
