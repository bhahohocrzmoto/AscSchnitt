# ASC_SCHNITT AutoCAD Map 3D Plugin

First working AutoCAD .NET command for generating a plain 2D terrain section profile from Austrian Arc/Info ASCII Grid `.asc` raster tiles.

The command is:

```text
ASC_SCHNITT
```

## What It Does

- Recursively scans a user-provided ASC root folder.
- Reads only ASC headers first and builds a tile index.
- Samples a picked start/end section line at a chosen spacing.
- Loads raster tiles only when sampled points need them.
- Supports German decimal commas in headers and raster values.
- Uses bilinear interpolation when the four neighbouring cells are valid.
- Falls back to nearest-neighbour sampling if bilinear interpolation touches `NODATA`.
- Splits profile output into multiple polylines across missing/NODATA gaps.
- Draws:
  - profile polylines on `ASC_SCHNITT_PROFILE`
  - plan route line on `ASC_SCHNITT_ROUTE`
  - labels on `ASC_SCHNITT_TEXT`
- Exports sampled points to CSV.

No coordinate transformations are performed. The drawing coordinates and selected ASC folder must already be in the same projected coordinate system.

## Project Structure

```text
AscSchnitt/
  AscSchnitt.csproj
  AscGridHeader.cs
  AscGridTile.cs
  AscGridIndex.cs
  SchnittSample.cs
  SchnittCommand.cs
```

## Required AutoCAD References

The project references these AutoCAD .NET assemblies:

- `AcMgd.dll`
- `AcDbMgd.dll`
- `AcCoreMgd.dll`

They are usually in the main AutoCAD or AutoCAD Map 3D installation folder, for example:

```text
C:\Program Files\Autodesk\AutoCAD 2024
```

## Build

Install the .NET SDK that can build `net48` projects, then run from this folder:

```powershell
dotnet build .\AscSchnitt\AscSchnitt.csproj -c Release /p:AutoCADInstallDir="C:\Program Files\Autodesk\AutoCAD 2024"
```

Adjust `AutoCADInstallDir` to the folder containing your AutoCAD assemblies. This project targets `net48`, which fits many AutoCAD/Map 3D installations up to the .NET Framework-based API generation. If your installed AutoCAD uses Autodesk's newer .NET runtime, keep the source files and change the target framework to the one required by that AutoCAD SDK/version.

The DLL will be created under:

```text
AscSchnitt\bin\Release\net48\AscSchnitt.dll
```

## Usage

1. Start AutoCAD Map 3D.
2. Run `NETLOAD`.
3. Select the compiled `AscSchnitt.dll`.
4. Run `ASC_SCHNITT`.
5. Enter the ASC root folder path.
6. Pick or enter the start point.
7. Pick or enter the end point.
8. Choose sample spacing and vertical exaggeration, or press Enter for defaults.
9. Pick the insertion point for the profile.
10. Accept the automatic datum or enter a custom datum.
11. Accept the default CSV export path or enter a custom path.

## ASC Coordinate Handling

Cell centre coordinates are computed as:

```text
x = xllcorner + (col + 0.5) * cellsize
y = yllcorner + (nrows - row - 0.5) * cellsize
```

Sampling converts drawing coordinates back to floating raster indices:

```text
colFloat = (x - (xllcorner + 0.5 * cellsize)) / cellsize
rowFloat = ((yllcorner + (nrows - 0.5) * cellsize) - y) / cellsize
```

`xllcenter`/`yllcenter` headers are converted internally to corner coordinates by subtracting `0.5 * cellsize`.
