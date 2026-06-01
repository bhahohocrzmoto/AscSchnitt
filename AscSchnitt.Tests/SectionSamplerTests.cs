using System.Linq;
using Xunit;

namespace AscSchnitt.Tests
{
    public class SectionSamplerTests
    {
        private static readonly string[] TileA =
        {
            "ncols 3", "nrows 3", "xllcorner 0", "yllcorner 0", "cellsize 1", "NODATA_value -9999",
            "10 20 30",
            "40 50 60",
            "70 80 90"
        };

        // Same value pattern, placed immediately east of TileA (shares the x = 3 edge).
        private static readonly string[] TileB =
        {
            "ncols 3", "nrows 3", "xllcorner 3", "yllcorner 0", "cellsize 1", "NODATA_value -9999",
            "10 20 30",
            "40 50 60",
            "70 80 90"
        };

        private static SectionSampler SamplerFor(TempAscFolder folder)
        {
            return new SectionSampler(AscGridIndex.BuildFromFolder(folder.Root));
        }

        [Fact]
        public void Horizontal_NorthEdge_ReturnsRowValues()
        {
            using var dir = new TempAscFolder();
            dir.Add("a.asc", TileA);
            var sampler = SamplerFor(dir);

            var s = sampler.SampleLine(new SamplePoint2d(0.5, 2.5), new SamplePoint2d(2.5, 2.5), 1.0);

            Assert.Equal(new[] { 0.0, 1.0, 2.0 }, s.Select(p => p.Distance));
            Assert.Equal(new double?[] { 10.0, 20.0, 30.0 }, s.Select(p => p.Z));
        }

        [Fact]
        public void Diagonal_ReturnsExpectedProfile()
        {
            using var dir = new TempAscFolder();
            dir.Add("a.asc", TileA);
            var sampler = SamplerFor(dir);

            var s = sampler.SampleLine(new SamplePoint2d(0.5, 0.5), new SamplePoint2d(2.5, 2.5), 1.0);

            Assert.Equal(4, s.Count);
            Assert.Equal(70.0, s[0].Z!.Value, 6);
            Assert.Equal(55.857864, s[1].Z!.Value, 6);
            Assert.Equal(41.715729, s[2].Z!.Value, 6);
            Assert.Equal(30.0, s[3].Z!.Value, 6);
        }

        [Fact]
        public void SectionCrossingTwoTiles_HasNoGaps()
        {
            using var dir = new TempAscFolder();
            dir.Add("a.asc", TileA);
            dir.Add("b.asc", TileB);
            var sampler = SamplerFor(dir);

            // No sample lands exactly on the x = 3 seam here.
            var s = sampler.SampleLine(new SamplePoint2d(0.5, 1.5), new SamplePoint2d(5.5, 1.5), 1.0);

            Assert.Equal(6, s.Count);
            Assert.All(s, p => Assert.True(p.Z.HasValue));
            Assert.Equal(2, sampler.LastCandidateCount);   // both tiles considered
            Assert.Equal(2, sampler.LoadedTileCount);      // both tiles loaded on demand
        }

        [Fact]
        public void SampleExactlyOnSeam_ReturnsValue_NotGap()
        {
            using var dir = new TempAscFolder();
            dir.Add("a.asc", TileA);
            dir.Add("b.asc", TileB);
            var sampler = SamplerFor(dir);

            // x = 3.0 lands exactly on the shared edge of the two tiles.
            var s = sampler.SampleLine(new SamplePoint2d(1.0, 1.5), new SamplePoint2d(5.0, 1.5), 1.0);

            var seam = s.Single(p => p.X == 3.0);
            Assert.True(seam.Z.HasValue);          // regression: previously NODATA on both tiles
            Assert.Equal(60.0, seam.Z!.Value, 6);  // deterministically resolved to tile A's east column
        }

        [Fact]
        public void PointsOutsideTerrain_ProduceGaps()
        {
            using var dir = new TempAscFolder();
            dir.Add("a.asc", TileA);
            var sampler = SamplerFor(dir);

            // Starts inside tile A, runs east past its extent into empty space.
            var s = sampler.SampleLine(new SamplePoint2d(1.5, 1.5), new SamplePoint2d(8.5, 1.5), 1.0);

            Assert.Contains(s, p => p.Z.HasValue);
            Assert.Contains(s, p => !p.Z.HasValue && p.SourceFile.Length == 0);
        }
    }
}
