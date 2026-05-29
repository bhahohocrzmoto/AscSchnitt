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
                for (int i = 0; i < 6; i++)
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
            int col = (int)Math.Round(colFloat, MidpointRounding.AwayFromZero);
            int row = (int)Math.Round(rowFloat, MidpointRounding.AwayFromZero);

            if (row < 0 || row >= Header.NRows || col < 0 || col >= Header.NCols)
            {
                return null;
            }

            double value = Values[row, col];
            return IsNoData(value) ? (double?)null : value;
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
            return Math.Abs(value - Header.NoData) < 1e-9;
        }
    }
}
