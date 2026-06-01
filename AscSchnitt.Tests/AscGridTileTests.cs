using Xunit;

namespace AscSchnitt.Tests
{
    public class AscGridTileTests
    {
        // 3x3 grid, cellsize 1, lower-left (0,0). Row 0 is the north/top row.
        private static readonly string[] Grid3x3 =
        {
            "ncols 3",
            "nrows 3",
            "xllcorner 0",
            "yllcorner 0",
            "cellsize 1",
            "NODATA_value -9999",
            "10 20 30",
            "40 50 60",
            "70 80 90"
        };

        [Fact]
        public void SixLineHeader_IsParsed()
        {
            using var f = new TempAsc(Grid3x3);
            var h = AscGridHeader.Read(f.Path);
            Assert.Equal(3, h.NCols);
            Assert.Equal(3, h.NRows);
            Assert.Equal(6, h.HeaderLineCount);
            Assert.Equal(0.0, h.XMin);
            Assert.Equal(3.0, h.XMax);
            Assert.Equal(0.0, h.YMin);
            Assert.Equal(3.0, h.YMax);
        }

        [Fact]
        public void FiveLineHeader_WithoutNodata_LoadsAndDefaultsNodata()
        {
            // Regression for C1: a spec-legal ASC without NODATA_value must not be misparsed.
            using var f = new TempAsc(
                "ncols 3",
                "nrows 3",
                "xllcorner 0",
                "yllcorner 0",
                "cellsize 1",
                "10 20 30",
                "40 50 60",
                "70 80 90");

            var h = AscGridHeader.Read(f.Path);
            Assert.Equal(5, h.HeaderLineCount);
            Assert.Equal(-9999.0, h.NoData);

            var tile = AscGridTile.Load(h);
            Assert.Equal(10.0, tile.Sample(0.5, 2.5)!.Value);   // top-left cell, NOT shifted
            Assert.Equal(90.0, tile.Sample(2.5, 0.5)!.Value);   // bottom-right cell
        }

        [Fact]
        public void NonPositiveCellsize_Throws()
        {
            using var f = new TempAsc(
                "ncols 2",
                "nrows 2",
                "xllcorner 0",
                "yllcorner 0",
                "cellsize 0",
                "NODATA_value -9999",
                "1 2",
                "3 4");

            Assert.ThrowsAny<System.Exception>(() => AscGridHeader.Read(f.Path));
        }

        [Theory]
        [InlineData(0.5, 2.5, 10)]
        [InlineData(1.5, 2.5, 20)]
        [InlineData(2.5, 2.5, 30)]
        [InlineData(0.5, 1.5, 40)]
        [InlineData(1.5, 1.5, 50)]
        [InlineData(2.5, 1.5, 60)]
        [InlineData(0.5, 0.5, 70)]
        [InlineData(1.5, 0.5, 80)]
        [InlineData(2.5, 0.5, 90)]
        public void CellCentres_MapToExpectedValues(double x, double y, double expected)
        {
            using var f = new TempAsc(Grid3x3);
            var tile = AscGridTile.Load(AscGridHeader.Read(f.Path));
            Assert.Equal(expected, tile.Sample(x, y)!.Value);
        }

        [Fact]
        public void Bilinear_InteriorMidpoint_AveragesNeighbours()
        {
            using var f = new TempAsc(Grid3x3);
            var tile = AscGridTile.Load(AscGridHeader.Read(f.Path));
            // Midpoint of cells 10,20,40,50 -> 30.
            Assert.Equal(30.0, tile.Sample(1.0, 2.0)!.Value, 9);
        }

        [Fact]
        public void Nodata_PreventsInterpolation_ReturnsNull()
        {
            using var f = new TempAsc(
                "ncols 3",
                "nrows 3",
                "xllcorner 0",
                "yllcorner 0",
                "cellsize 1",
                "NODATA_value -9999",
                "10 20 30",
                "40 -9999 60",
                "70 80 90");

            var tile = AscGridTile.Load(AscGridHeader.Read(f.Path));
            Assert.Null(tile.Sample(1.0, 2.0));   // bilinear touches the hole; nearest hits it too
        }

        [Fact]
        public void EastEdge_ReturnsEdgeCell_NotNull()
        {
            // C2/C3 fix: a point exactly on the far edge resolves to the boundary cell.
            using var f = new TempAsc(Grid3x3);
            var tile = AscGridTile.Load(AscGridHeader.Read(f.Path));
            Assert.Equal(60.0, tile.Sample(3.0, 1.5)!.Value);   // east edge, middle row
        }

        [Fact]
        public void OutsideTile_ReturnsNull()
        {
            using var f = new TempAsc(Grid3x3);
            var tile = AscGridTile.Load(AscGridHeader.Read(f.Path));
            Assert.Null(tile.Sample(5.0, 5.0));
        }

        [Fact]
        public void CommaDecimals_AreParsed()
        {
            using var f = new TempAsc(
                "ncols 2",
                "nrows 1",
                "xllcorner 23749,5",
                "yllcorner 268999,25",
                "cellsize 1",
                "NODATA_value -9999",
                "12,5 13,5");

            var h = AscGridHeader.Read(f.Path);
            Assert.Equal(23749.5, h.XMin, 9);

            var tile = AscGridTile.Load(h);
            // Centre of column 0: x = 23749.5 + 0.5, y = 268999.25 + 0.5.
            Assert.Equal(12.5, tile.Sample(23750.0, 268999.75)!.Value, 9);
        }
    }
}
