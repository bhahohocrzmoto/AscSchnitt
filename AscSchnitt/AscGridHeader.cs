using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;

namespace AscSchnitt
{
    public sealed class AscGridHeader
    {
        public string FilePath { get; set; } = string.Empty;
        public int NCols { get; set; }
        public int NRows { get; set; }
        public double XllCorner { get; set; }
        public double YllCorner { get; set; }
        public double CellSize { get; set; }
        public double NoData { get; set; } = -9999.0;
        public double XMin { get; set; }
        public double XMax { get; set; }
        public double YMin { get; set; }
        public double YMax { get; set; }

        // Number of leading lines (header keys plus any blank lines before the raster)
        // that AscGridTile.Load must skip to reach the first data row. Because NODATA_value
        // is optional, this is NOT a fixed constant.
        public int HeaderLineCount { get; set; }

        // Recognised Arc/Info ASCII Grid header keys. The header ends at the first line
        // whose first token is not one of these (i.e. the first raster-data row).
        private static readonly HashSet<string> HeaderKeys = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "ncols",
            "nrows",
            "xllcorner",
            "yllcorner",
            "xllcenter",
            "yllcenter",
            "cellsize",
            "nodata_value"
        };

        public bool Contains(double x, double y)
        {
            return x >= XMin && x <= XMax && y >= YMin && y <= YMax;
        }

        // Strictly inside the footprint (excludes the shared edges). Used to give a point
        // that lies on a tile seam to the tile that owns it internally.
        public bool ContainsInterior(double x, double y)
        {
            return x > XMin && x < XMax && y > YMin && y < YMax;
        }

        public bool Intersects(double xmin, double ymin, double xmax, double ymax)
        {
            return XMin <= xmax && XMax >= xmin && YMin <= ymax && YMax >= ymin;
        }

        public static AscGridHeader Read(string filePath)
        {
            var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            int headerLineCount = 0;

            // Arc/Info ASCII Grid headers are FIVE or SIX key/value lines (NODATA_value is
            // optional). Read leading lines until the first token is no longer a header key,
            // i.e. until the first raster-data row, instead of assuming a fixed line count.
            using (var reader = new StreamReader(filePath))
            {
                string? line;
                while ((line = reader.ReadLine()) != null)
                {
                    string[] parts = SplitWhitespace(line);
                    if (parts.Length == 0)
                    {
                        // Tolerate blank lines inside the header; Load skips them too.
                        headerLineCount++;
                        continue;
                    }

                    if (!HeaderKeys.Contains(parts[0]))
                    {
                        // First data row reached; stop without consuming it.
                        break;
                    }

                    if (parts.Length < 2)
                    {
                        throw new InvalidDataException("Invalid ASC header line: " + line);
                    }

                    values[parts[0]] = parts[1];
                    headerLineCount++;
                }
            }

            var header = new AscGridHeader
            {
                FilePath = filePath,
                HeaderLineCount = headerLineCount,
                NCols = ParseInt(Get(values, "ncols")),
                NRows = ParseInt(Get(values, "nrows")),
                CellSize = ParseDouble(Get(values, "cellsize")),
                NoData = values.TryGetValue("NODATA_value", out string? nodata) ? ParseDouble(nodata) : -9999.0
            };

            if (header.NCols <= 0 || header.NRows <= 0)
            {
                throw new InvalidDataException("ASC ncols/nrows must be positive.");
            }

            if (!(header.CellSize > 0.0))
            {
                throw new InvalidDataException(
                    "ASC cellsize must be positive: " + header.CellSize.ToString(CultureInfo.InvariantCulture));
            }

            bool hasXCorner = values.TryGetValue("xllcorner", out string? xCorner);
            bool hasYCorner = values.TryGetValue("yllcorner", out string? yCorner);
            bool hasXCenter = values.TryGetValue("xllcenter", out string? xCenter);
            bool hasYCenter = values.TryGetValue("yllcenter", out string? yCenter);

            if (hasXCorner)
            {
                header.XllCorner = ParseDouble(xCorner!);
            }
            else if (hasXCenter)
            {
                // Store everything internally as lower-left corner coordinates.
                header.XllCorner = ParseDouble(xCenter!) - 0.5 * header.CellSize;
            }
            else
            {
                throw new InvalidDataException("ASC header is missing xllcorner/xllcenter.");
            }

            if (hasYCorner)
            {
                header.YllCorner = ParseDouble(yCorner!);
            }
            else if (hasYCenter)
            {
                header.YllCorner = ParseDouble(yCenter!) - 0.5 * header.CellSize;
            }
            else
            {
                throw new InvalidDataException("ASC header is missing yllcorner/yllcenter.");
            }

            header.XMin = header.XllCorner;
            header.XMax = header.XllCorner + header.NCols * header.CellSize;
            header.YMin = header.YllCorner;
            header.YMax = header.YllCorner + header.NRows * header.CellSize;

            return header;
        }

        public static double ParseDouble(string text)
        {
            // Austrian data often uses decimal commas; AutoCAD and CSV output use invariant dots here.
            string normalized = text.Trim().Replace(',', '.');
            return double.Parse(normalized, NumberStyles.Float | NumberStyles.AllowThousands, CultureInfo.InvariantCulture);
        }

        private static int ParseInt(string text)
        {
            return int.Parse(text.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture);
        }

        private static string Get(Dictionary<string, string> values, string key)
        {
            if (!values.TryGetValue(key, out string? value))
            {
                throw new InvalidDataException("ASC header is missing " + key + ".");
            }

            return value;
        }

        internal static string[] SplitWhitespace(string line)
        {
            return line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
        }
    }
}
