using System;
using System.Collections.Generic;

namespace AscSchnitt
{
    // A 2D world coordinate, deliberately independent of the AutoCAD API so the sampling
    // logic can be unit-tested without loading AutoCAD.
    public readonly struct SamplePoint2d
    {
        public double X { get; }
        public double Y { get; }

        public SamplePoint2d(double x, double y)
        {
            X = x;
            Y = y;
        }
    }

    // Samples a terrain section across one or more ASC tiles. Pure logic with no AutoCAD
    // dependency; owns the loaded-tile cache for the lifetime of one section.
    public sealed class SectionSampler
    {
        private readonly AscGridIndex _index;
        private readonly Dictionary<string, AscGridTile> _cache =
            new Dictionary<string, AscGridTile>(StringComparer.OrdinalIgnoreCase);

        public SectionSampler(AscGridIndex index)
        {
            _index = index ?? throw new ArgumentNullException(nameof(index));
        }

        // Tiles whose bounding box intersected the most recent section.
        public int LastCandidateCount { get; private set; }

        // Tiles actually loaded into memory so far.
        public int LoadedTileCount => _cache.Count;

        public List<SchnittSample> SampleLine(SamplePoint2d start, SamplePoint2d end, double spacing)
        {
            if (!(spacing > 0.0))
            {
                throw new ArgumentOutOfRangeException(nameof(spacing), "Sample spacing must be positive.");
            }

            double dx = end.X - start.X;
            double dy = end.Y - start.Y;
            double length = Math.Sqrt(dx * dx + dy * dy);
            int segmentCount = length <= 0.0 ? 0 : Math.Max(1, (int)Math.Ceiling(length / spacing));

            double xmin = Math.Min(start.X, end.X);
            double xmax = Math.Max(start.X, end.X);
            double ymin = Math.Min(start.Y, end.Y);
            double ymax = Math.Max(start.Y, end.Y);

            // The section line lies inside its own bounding box, so every tile the line
            // crosses is in this set. Each sample then resolves its own tile, which is how
            // a single section spans multiple tiles.
            List<AscGridHeader> candidates = _index.FindTilesIntersectingBoundingBox(xmin, ymin, xmax, ymax);
            LastCandidateCount = candidates.Count;

            var samples = new List<SchnittSample>(segmentCount + 1);
            for (int i = 0; i <= segmentCount; i++)
            {
                double distance = Math.Min(i * spacing, length);
                double t = length <= 0.0 ? 0.0 : distance / length;
                double x = start.X + t * dx;
                double y = start.Y + t * dy;

                AscGridHeader? header = SelectTile(candidates, x, y);
                if (header == null)
                {
                    // No tile covers this point: record a gap so the profile is split here.
                    samples.Add(new SchnittSample { Distance = distance, X = x, Y = y, Z = null, SourceFile = string.Empty });
                    continue;
                }

                if (!_cache.TryGetValue(header.FilePath, out AscGridTile? tile))
                {
                    tile = AscGridTile.Load(header);
                    _cache.Add(header.FilePath, tile);
                }

                samples.Add(new SchnittSample
                {
                    Distance = distance,
                    X = x,
                    Y = y,
                    Z = tile.Sample(x, y),
                    SourceFile = header.FilePath
                });
            }

            return samples;
        }

        // Tiles share their edges, so a point on a seam falls inside two footprints. Prefer
        // the tile that holds the point in its interior (so it can interpolate). When the
        // point sits exactly on a seam (interior of neither), fall back deterministically to
        // the lower-left-most tile so the result does not depend on file enumeration order.
        private static AscGridHeader? SelectTile(List<AscGridHeader> candidates, double x, double y)
        {
            AscGridHeader? boundaryMatch = null;
            for (int i = 0; i < candidates.Count; i++)
            {
                AscGridHeader header = candidates[i];
                if (!header.Contains(x, y))
                {
                    continue;
                }

                if (header.ContainsInterior(x, y))
                {
                    return header;
                }

                if (boundaryMatch == null || IsLowerLeft(header, boundaryMatch))
                {
                    boundaryMatch = header;
                }
            }

            return boundaryMatch;
        }

        private static bool IsLowerLeft(AscGridHeader candidate, AscGridHeader current)
        {
            if (candidate.XMin != current.XMin)
            {
                return candidate.XMin < current.XMin;
            }

            return candidate.YMin < current.YMin;
        }
    }
}
