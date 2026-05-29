using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace AscSchnitt
{
    public sealed class AscGridIndex
    {
        public List<AscGridHeader> Headers { get; private set; } = new List<AscGridHeader>();

        public static AscGridIndex BuildFromFolder(string rootFolder)
        {
            if (!Directory.Exists(rootFolder))
            {
                throw new DirectoryNotFoundException(rootFolder);
            }

            var index = new AscGridIndex();
            foreach (string file in Directory.EnumerateFiles(rootFolder, "*.asc", SearchOption.AllDirectories))
            {
                // Only headers are read during indexing; raster values are loaded lazily by the sampler.
                index.Headers.Add(AscGridHeader.Read(file));
            }

            return index;
        }

        public List<AscGridHeader> FindTilesIntersectingBoundingBox(double xmin, double ymin, double xmax, double ymax)
        {
            return Headers.Where(h => h.Intersects(xmin, ymin, xmax, ymax)).ToList();
        }

        public AscGridHeader? FindTileContainingPoint(double x, double y)
        {
            return Headers.FirstOrDefault(h => h.Contains(x, y));
        }
    }
}
