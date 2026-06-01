from __future__ import annotations

import argparse
from pathlib import Path

from .csv_export import export_csv
from .dxf_export import automatic_datum, export_dxf
from .index import AscGridIndex
from .models import SamplePoint2d
from .sampler import SectionSampler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sample ASC terrain tiles and write section CSV/DXF outputs.")
    parser.add_argument("--asc-root", required=True, help="Folder containing .asc files; scanned recursively.")
    parser.add_argument("--start-x", type=float, required=True)
    parser.add_argument("--start-y", type=float, required=True)
    parser.add_argument("--end-x", type=float, required=True)
    parser.add_argument("--end-y", type=float, required=True)
    parser.add_argument("--spacing", type=float, default=1.0)
    parser.add_argument("--vertical-exaggeration", type=float, default=1.0)
    parser.add_argument("--insertion-x", type=float, default=0.0, help="Profile insertion X in the DXF output.")
    parser.add_argument("--insertion-y", type=float, default=0.0, help="Profile insertion Y in the DXF output.")
    parser.add_argument("--datum", type=float, help="Profile datum. Defaults to floor(min_z / 10) * 10.")
    parser.add_argument("--csv", type=Path, help="CSV output path.")
    parser.add_argument("--dxf", type=Path, help="DXF output path.")
    args = parser.parse_args(argv)

    if args.spacing <= 0.0:
        parser.error("--spacing must be greater than zero")
    if args.vertical_exaggeration <= 0.0:
        parser.error("--vertical-exaggeration must be greater than zero")
    if args.csv is None and args.dxf is None:
        parser.error("At least one of --csv or --dxf is required")

    index = AscGridIndex.build_from_folder(args.asc_root)
    if not index.headers:
        raise SystemExit(f"No .asc files found under {args.asc_root}")

    start = SamplePoint2d(args.start_x, args.start_y)
    end = SamplePoint2d(args.end_x, args.end_y)
    insertion = SamplePoint2d(args.insertion_x, args.insertion_y)

    sampler = SectionSampler(index)
    samples = sampler.sample_line(start, end, args.spacing)
    valid_count = sum(1 for sample in samples if sample.z is not None)
    if valid_count == 0:
        raise SystemExit("No valid terrain samples found along the section line.")

    datum = args.datum if args.datum is not None else automatic_datum(samples)

    if args.csv is not None:
        export_csv(args.csv, samples)
    if args.dxf is not None:
        export_dxf(args.dxf, samples, start, end, insertion, datum, args.vertical_exaggeration)

    print("ASC_SCHNITT Python complete.")
    print(f"ASC files scanned: {len(index.headers)}")
    print(f"Tiles intersecting section bounding box: {sampler.last_candidate_count}")
    print(f"Tiles loaded: {sampler.loaded_tile_count}")
    print(f"Samples: {len(samples)}")
    print(f"Valid samples: {valid_count}")
    print(f"Invalid/NODATA samples: {len(samples) - valid_count}")
    if args.csv is not None:
        print(f"CSV exported: {args.csv}")
    if args.dxf is not None:
        print(f"DXF exported: {args.dxf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
