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

        public bool Contains(double x, double y)
        {
            return x >= XMin && x <= XMax && y >= YMin && y <= YMax;
        }

        public bool Intersects(double xmin, double ymin, double xmax, double ymax)
        {
            return XMin <= xmax && XMax >= xmin && YMin <= ymax && YMax >= ymin;
        }

        public static AscGridHeader Read(string filePath)
        {
            var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

            // Arc/Info ASCII Grid headers are six key/value lines before raster data.
            using (var reader = new StreamReader(filePath))
            {
                for (int i = 0; i < 6; i++)
                {
                    string? line = reader.ReadLine();
                    if (line == null)
                    {
                        throw new InvalidDataException("ASC header has fewer than six lines.");
                    }

                    string[] parts = SplitWhitespace(line);
                    if (parts.Length < 2)
                    {
                        throw new InvalidDataException("Invalid ASC header line: " + line);
                    }

                    values[parts[0]] = parts[1];
                }
            }

            var header = new AscGridHeader
            {
                FilePath = filePath,
                NCols = ParseInt(Get(values, "ncols")),
                NRows = ParseInt(Get(values, "nrows")),
                CellSize = ParseDouble(Get(values, "cellsize")),
                NoData = values.TryGetValue("NODATA_value", out string? nodata) ? ParseDouble(nodata) : -9999.0
            };

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
