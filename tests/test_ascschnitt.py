from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ascschnitt.asc_header import read_header
from ascschnitt.csv_export import export_csv
from ascschnitt.dxf_export import automatic_datum, export_dxf
from ascschnitt.extent_scan import (
    GK_BY_EPSG,
    discover_gk_folders,
    iter_relevant_asc_files,
    parse_user_float,
    scan_extent,
)
from ascschnitt.index import AscGridIndex
from ascschnitt.models import SamplePoint2d
from ascschnitt.sampler import SectionSampler
from ascschnitt.tile import AscGridTile


ASC_TEXT = """ncols 3
nrows 3
xllcorner 0
yllcorner 0
cellsize 1
NODATA_value -9999
7 8 9
4 5 6
1 2 3
"""

ASC_COMMA_TEXT = """ncols 2
nrows 2
xllcenter 0,5
yllcenter 0,5
cellsize 1,0
1 2
3 4
"""


class AscSchnittTests(unittest.TestCase):
    def test_header_accepts_decimal_commas_and_center_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "comma.asc"
            path.write_text(ASC_COMMA_TEXT, encoding="utf-8")

            header = read_header(path)

            self.assertEqual(header.ncols, 2)
            self.assertEqual(header.nrows, 2)
            self.assertEqual(header.xllcorner, 0.0)
            self.assertEqual(header.yllcorner, 0.0)
            self.assertEqual(header.cellsize, 1.0)
            self.assertEqual(header.nodata, -9999.0)

    def test_tile_samples_bilinear_and_nearest_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "tile.asc"
            path.write_text(ASC_TEXT, encoding="utf-8")
            header = read_header(path)
            tile = AscGridTile.load(header)

            self.assertEqual(tile.sample_nearest(0.5, 0.5), 1.0)
            self.assertEqual(tile.sample_bilinear(1.0, 1.0), 3.0)
            self.assertEqual(tile.sample(3.0, 3.0), 9.0)

    def test_sampler_spans_line_and_exports_csv_and_dxf(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            asc = root / "tile.asc"
            csv_path = root / "profile.csv"
            dxf_path = root / "profile.dxf"
            asc.write_text(ASC_TEXT, encoding="utf-8")

            index = AscGridIndex.build_from_folder(root)
            sampler = SectionSampler(index)
            start = SamplePoint2d(0.5, 0.5)
            end = SamplePoint2d(2.5, 0.5)
            samples = sampler.sample_line(start, end, 1.0)

            self.assertEqual(len(samples), 3)
            self.assertEqual([sample.z for sample in samples], [1.0, 2.0, 3.0])
            self.assertEqual(sampler.last_candidate_count, 1)
            self.assertEqual(sampler.loaded_tile_count, 1)

            export_csv(csv_path, samples)
            with csv_path.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(rows[0], ["distance_m", "x", "y", "z_m", "source_asc_file"])
            self.assertEqual(rows[1][:4], ["0", "0.5", "0.5", "1"])

            datum = automatic_datum(samples)
            self.assertEqual(datum, 0.0)
            export_dxf(dxf_path, samples, start, end, SamplePoint2d(10.0, 20.0), datum, 2.0)
            dxf = dxf_path.read_text(encoding="ascii")
            self.assertIn("ASC_SCHNITT_PROFILE", dxf)
            self.assertIn("POLYLINE", dxf)
            self.assertIn("EOF", dxf)

    def test_cli_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            asc = root / "tile.asc"
            csv_path = root / "profile.csv"
            dxf_path = root / "profile.dxf"
            asc.write_text(ASC_TEXT, encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ascschnitt",
                    "--asc-root",
                    str(root),
                    "--start-x",
                    "0.5",
                    "--start-y",
                    "0.5",
                    "--end-x",
                    "2.5",
                    "--end-y",
                    "0.5",
                    "--spacing",
                    "1",
                    "--csv",
                    str(csv_path),
                    "--dxf",
                    str(dxf_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("ASC_SCHNITT Python complete", result.stdout)
            self.assertTrue(csv_path.exists())
            self.assertTrue(dxf_path.exists())



class ExtentScanTests(unittest.TestCase):
    def _write_asc(self, path: Path, text: str = ASC_TEXT) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_extent_scan_corner_coordinates(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._write_asc(root / "m28" / "tile.asc")

            result = scan_extent(root, 31254)

            self.assertEqual(result.asc_file_count, 1)
            self.assertEqual(result.folder_name, "m28")
            self.assertEqual(result.xmin, 0.0)
            self.assertEqual(result.xmax, 3.0)
            self.assertEqual(result.ymin, 0.0)
            self.assertEqual(result.ymax, 3.0)
            self.assertEqual(result.min_cellsize, 1.0)
            self.assertEqual(result.max_cellsize, 1.0)

    def test_extent_scan_center_coordinates_and_decimal_commas(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._write_asc(root / "m31" / "tile.asc", ASC_COMMA_TEXT)

            result = scan_extent(root, "EPSG:31255")

            self.assertEqual(result.asc_file_count, 1)
            self.assertEqual(result.folder_name, "m31")
            self.assertEqual(result.xmin, 0.0)
            self.assertEqual(result.xmax, 2.0)
            self.assertEqual(result.ymin, 0.0)
            self.assertEqual(result.ymax, 2.0)
            self.assertEqual(parse_user_float("1,25", "test"), 1.25)

    def test_prjxml_folders_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._write_asc(root / "m34" / "tile.asc")
            self._write_asc(root / "m34prjxml" / "metadata.asc")
            self._write_asc(root / "m34" / "nestedprjxml" / "metadata.asc")

            found = discover_gk_folders(root)
            files = list(iter_relevant_asc_files(root / "m34"))
            result = scan_extent(root, 31256)

            self.assertEqual(found[31256], root / "m34")
            self.assertEqual(files, [root / "m34" / "tile.asc"])
            self.assertEqual(result.asc_file_count, 1)

    def test_epsg_folder_mapping(self) -> None:
        self.assertEqual(GK_BY_EPSG[31254].folder_name, "m28")
        self.assertEqual(GK_BY_EPSG[31255].folder_name, "m31")
        self.assertEqual(GK_BY_EPSG[31256].folder_name, "m34")

    def test_point_and_line_extent_checks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self._write_asc(root / "m28" / "tile.asc")
            result = scan_extent(root, 31254)

            self.assertIsNotNone(result.point_tile(0.5, 0.5))
            self.assertIsNone(result.point_tile(10.0, 10.0))
            self.assertEqual(len(result.line_bbox_tiles(-1.0, 1.0, 1.0, 1.0)), 1)
            self.assertEqual(result.line_bbox_tiles(10.0, 10.0, 11.0, 11.0), [])


if __name__ == "__main__":
    unittest.main()
