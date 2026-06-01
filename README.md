# ASC_SCHNITT Python

Pure Python replacement for the original AutoCAD/.NET `ASC_SCHNITT` plugin.
It reads Austrian Arc/Info ASCII Grid `.asc` terrain tiles, samples a section
line, exports sampled profile points to CSV, and draws the route/profile into a
plain ASCII DXF file.

This version avoids:

- `.NET Framework 4.8`
- `dotnet build`
- AutoCAD `.NET` DLL references such as `AcMgd.dll`, `AcDbMgd.dll`, and `AcCoreMgd.dll`
- `NETLOAD`
- compiled plugin DLLs

The optional AutoLISP file in `autocad/asc_schnitt_py.lsp` can be loaded into
AutoCAD to pick points interactively, call the Python exporter, and import the
resulting DXF.

## What It Does

- Recursively scans a user-provided ASC root folder.
- Reads only ASC headers first and builds a tile index.
- Samples a start/end section line at a chosen spacing.
- Loads raster tiles only when sampled points need them.
- Supports German/Austrian decimal commas in headers and raster values.
- Accepts ASC files with or without the optional `NODATA_value` header line.
- Converts `xllcenter`/`yllcenter` headers internally to lower-left corners.
- Uses bilinear interpolation when the four neighbouring cells are valid.
- Falls back to nearest-neighbour sampling if bilinear interpolation touches `NODATA`.
- Splits DXF profile output into multiple polylines across missing/NODATA gaps.
- Writes:
  - `ASC_SCHNITT_PROFILE` profile polylines
  - `ASC_SCHNITT_ROUTE` plan route line
  - `ASC_SCHNITT_TEXT` labels
- Exports sampled points to CSV.

No coordinate transformations are performed. The coordinates you pass to the
Python tool and the selected ASC folder must already be in the same projected
coordinate system.

## Project Structure

```text
ascschnitt/
  asc_header.py      # ASC header parsing
  tile.py            # ASC raster loading and interpolation
  index.py           # recursive ASC tile indexing
  sampler.py         # section sampling logic
  csv_export.py      # CSV writer
  dxf_export.py      # ASCII DXF writer
  cli.py             # command-line interface
autocad/
  asc_schnitt_py.lsp # optional AutoCAD AutoLISP bridge
tests/
  test_ascschnitt.py
```

## Requirements

- Python 3.10 or newer.

The runtime uses only the Python standard library. No pip packages are required
for normal command-line use.

## Run Without Installing

From the repository root:

```bash
python -m ascschnitt \
  --asc-root "C:\\terrain\\asc" \
  --start-x 12345.0 \
  --start-y 56789.0 \
  --end-x 12450.0 \
  --end-y 56820.0 \
  --spacing 1.0 \
  --vertical-exaggeration 1.0 \
  --insertion-x 0.0 \
  --insertion-y 0.0 \
  --csv output/profile.csv \
  --dxf output/profile.dxf
```

At least one of `--csv` or `--dxf` is required.

## Optional Editable Install

If your PC allows local Python package installs, you can install the command in
editable mode:

```bash
python -m pip install -e .
```

Then run:

```bash
ascschnitt --asc-root "C:\\terrain\\asc" --start-x 0 --start-y 0 --end-x 100 --end-y 0 --csv profile.csv --dxf profile.dxf
```

If your PC blocks installs, skip this section and use `python -m ascschnitt`.

## AutoCAD Workflow Without .NET

There are two practical AutoCAD workflows.

### Option A: Generate DXF, Then Import/Open It

1. Run the Python command from a terminal.
2. Open or import the generated `profile.dxf` in AutoCAD.
3. Copy/paste or reference the geometry as needed.

This is the simplest and most reliable restricted-PC workflow.

### Option B: Use the Optional AutoLISP Bridge

The file `autocad/asc_schnitt_py.lsp` defines an AutoCAD command:

```text
ASC_SCHNITT_PY
```

It asks AutoCAD for the section points, spacing, vertical exaggeration, output
paths, starts the Python exporter, and imports the generated DXF.

Basic usage:

1. Make sure `python -m ascschnitt` works from a terminal in this repository, or
   install the package with `python -m pip install -e .`.
2. In AutoCAD, load `autocad/asc_schnitt_py.lsp` with `APPLOAD`.
3. Run `ASC_SCHNITT_PY`.
4. Follow the prompts.

If your Python executable is not named `python`, edit this line near the top of
`autocad/asc_schnitt_py.lsp`:

```lisp
(setq *asc-schnitt-python* "python")
```

For example, change it to `py` or a full path to `python.exe`.

## CSV Output

The CSV columns are:

```text
distance_m,x,y,z_m,source_asc_file
```

Invalid samples outside tiles or on `NODATA` cells have an empty `z_m` field.

## DXF Output

The DXF writer creates a small ASCII DXF with these layers:

- `ASC_SCHNITT_ROUTE` for the plan route line.
- `ASC_SCHNITT_PROFILE` for the terrain profile polylines.
- `ASC_SCHNITT_TEXT` for labels.

The profile X coordinate is:

```text
profile_x = insertion_x + distance_along_section
```

The profile Y coordinate is:

```text
profile_y = insertion_y + (z - datum) * vertical_exaggeration
```

If `--datum` is omitted, the datum is chosen automatically as:

```text
floor(min_z / 10) * 10
```

## ASC Coordinate Handling

Cell centre coordinates are computed as:

```text
x = xllcorner + (col + 0.5) * cellsize
y = yllcorner + (nrows - row - 0.5) * cellsize
```

Sampling converts drawing coordinates back to floating raster indices:

```text
col_float = (x - (xllcorner + 0.5 * cellsize)) / cellsize
row_float = ((yllcorner + (nrows - 0.5) * cellsize) - y) / cellsize
```

`xllcenter`/`yllcenter` headers are converted internally to corner coordinates
by subtracting `0.5 * cellsize`.

## Tests

Run the standard-library test suite from the repository root:

```bash
python -m unittest
```
