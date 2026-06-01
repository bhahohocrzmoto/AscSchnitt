using System;
using System.Globalization;
using System.IO;

namespace AscSchnitt
{
    public sealed class AscGridTile
    {
        public AscGridHeader Header { get; private set; } = null!;
        public double[,] Values { get; private set; } = null!;

        public static AscGridTile Load(AscGridHeader header)
        {
            var values = new double[header.NRows, header.NCols];

            using (var reader = new StreamReader(header.FilePath))
            {
                // Skip the exact number of header/blank lines detected when the header was
                // read, so files with or without the optional NODATA_value line both work.
                for (int i = 0; i < header.HeaderLineCount; i++)
                {
                    if (reader.ReadLine() == null)
                    {
                        throw new InvalidDataException("ASC file ended inside header: " + header.FilePath);
                    }
                }

                for (int row = 0; row < header.NRows; row++)
                {
                    // Row 0 in the file is the north/top row. Keep that order in memory.
                    string? line = reader.ReadLine();
                    if (line == null)
                    {
                        throw new InvalidDataException("ASC file ended before all raster rows were read: " + header.FilePath);
                    }

                    string[] parts = AscGridHeader.SplitWhitespace(line);
                    if (parts.Length < header.NCols)
                    {
                        throw new InvalidDataException(
                            string.Format(CultureInfo.InvariantCulture, "ASC row {0} has {1} values; expected {2}.", row, parts.Length, header.NCols));
                    }

                    for (int col = 0; col < header.NCols; col++)
                    {
                        values[row, col] = AscGridHeader.ParseDouble(parts[col]);
                    }
                }
            }

            return new AscGridTile
            {
                Header = header,
                Values = values
            };
        }

        public double? Sample(double x, double y)
        {
            // Prefer smooth interpolation, but do not smear across NODATA holes.
            double? bilinear = SampleBilinear(x, y);
            return bilinear ?? SampleNearest(x, y);
        }

        public double? SampleNearest(double x, double y)
        {
            GetFloatIndices(x, y, out double colFloat, out double rowFloat);

            int? col = NearestIndex(colFloat, Header.NCols);
            int? row = NearestIndex(rowFloat, Header.NRows);
            if (col == null || row == null)
            {
                return null;
            }

            double value = Values[row.Value, col.Value];
            return IsNoData(value) ? (double?)null : value;
        }

        // Maps a floating cell-centre index to the nearest integer cell index. Cell centres
        // sit at integer indices, so the tile footprint spans [-0.5, count - 0.5] in index
        // space. Points inside that band snap to the nearest cell, with the outer half-cell
        // rim (and the exact boundary) clamped to the edge cell rather than failing; points
        // genuinely outside the footprint return null.
        private static int? NearestIndex(double floatIndex, int count)
        {
            const double eps = 1e-9;
            if (floatIndex < -0.5 - eps || floatIndex > count - 0.5 + eps)
            {
                return null;
            }

            int index = (int)Math.Floor(floatIndex + 0.5);
            if (index < 0)
            {
                index = 0;
            }
            else if (index > count - 1)
            {
                index = count - 1;
            }

            return index;
        }

        public double? SampleBilinear(double x, double y)
        {
            GetFloatIndices(x, y, out double colFloat, out double rowFloat);

            int col0 = (int)Math.Floor(colFloat);
            int row0 = (int)Math.Floor(rowFloat);
            int col1 = col0 + 1;
            int row1 = row0 + 1;

            if (row0 < 0 || row1 >= Header.NRows || col0 < 0 || col1 >= Header.NCols)
            {
                return null;
            }

            double z00 = Values[row0, col0];
            double z10 = Values[row0, col1];
            double z01 = Values[row1, col0];
            double z11 = Values[row1, col1];

            if (IsNoData(z00) || IsNoData(z10) || IsNoData(z01) || IsNoData(z11))
            {
                return null;
            }

            double dx = colFloat - col0;
            double dy = rowFloat - row0;

            double zTop = z00 * (1.0 - dx) + z10 * dx;
            double zBottom = z01 * (1.0 - dx) + z11 * dx;
            return zTop * (1.0 - dy) + zBottom * dy;
        }

        private void GetFloatIndices(double x, double y, out double colFloat, out double rowFloat)
        {
            // Convert projected drawing coordinates to floating cell-center indices.
            colFloat = (x - (Header.XllCorner + 0.5 * Header.CellSize)) / Header.CellSize;
            rowFloat = ((Header.YllCorner + (Header.NRows - 0.5) * Header.CellSize) - y) / Header.CellSize;
        }

        private bool IsNoData(double value)
        {
            // NaN is never valid terrain, so treat it like NODATA and keep it out of profiles.
            return double.IsNaN(value) || Math.Abs(value - Header.NoData) < 1e-9;
        }
    }
}
