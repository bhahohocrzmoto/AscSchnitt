using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using Application = Autodesk.AutoCAD.ApplicationServices.Application;

namespace AscSchnitt
{
    public sealed class SchnittCommand
    {
        private const string ProfileLayer = "ASC_SCHNITT_PROFILE";
        private const string RouteLayer = "ASC_SCHNITT_ROUTE";
        private const string TextLayer = "ASC_SCHNITT_TEXT";

        [CommandMethod("ASC_SCHNITT")]
        public void CreateSchnitt()
        {
            Document doc = Application.DocumentManager.MdiActiveDocument;
            Editor ed = doc.Editor;
            Database db = doc.Database;

            try
            {
                string? rootFolder = PromptString(ed, "\nASC root folder: ", allowSpaces: true);
                if (string.IsNullOrWhiteSpace(rootFolder))
                {
                    return;
                }

                rootFolder = rootFolder.Trim('"');
                ed.WriteMessage("\nScanning ASC headers...");
                AscGridIndex index = AscGridIndex.BuildFromFolder(rootFolder);
                if (index.Headers.Count == 0)
                {
                    ed.WriteMessage("\nNo .asc files found under the selected root folder.");
                    return;
                }

                Point3d start = PromptPoint(ed, "\nStart point of section: ");
                Point3d end = PromptPoint(ed, "\nEnd point of section: ");
                double sampleSpacing = PromptDouble(ed, "\nSample spacing <1.0>: ", 1.0, minExclusive: 0.0);
                double verticalExaggeration = PromptDouble(ed, "\nVertical exaggeration <1.0>: ", 1.0, minExclusive: 0.0);
                Point3d insertion = PromptPoint(ed, "\nInsertion point for profile: ");

                double xmin = Math.Min(start.X, end.X);
                double xmax = Math.Max(start.X, end.X);
                double ymin = Math.Min(start.Y, end.Y);
                double ymax = Math.Max(start.Y, end.Y);
                List<AscGridHeader> intersectingTiles = index.FindTilesIntersectingBoundingBox(xmin, ymin, xmax, ymax);

                // Cache only the tiles that are actually touched by samples.
                var cache = new Dictionary<string, AscGridTile>(StringComparer.OrdinalIgnoreCase);
                List<SchnittSample> samples = SampleRoute(start, end, sampleSpacing, intersectingTiles, cache);

                List<SchnittSample> validSamples = samples.Where(s => s.Z.HasValue).ToList();
                if (validSamples.Count == 0)
                {
                    ed.WriteMessage("\nNo valid terrain samples found along the section line.");
                    return;
                }

                double minZ = validSamples.Min(s => s.Z!.Value);
                double maxZ = validSamples.Max(s => s.Z!.Value);
                double autoDatum = Math.Floor(minZ / 10.0) * 10.0;
                double datum = PromptDouble(ed, string.Format(CultureInfo.InvariantCulture, "\nDatum <{0:0.###}>: ", autoDatum), autoDatum, minExclusive: null);

                string defaultCsv = GetDefaultCsvPath(db);
                string? csvPath = PromptString(ed, "\nCSV export path <" + defaultCsv + ">: ", allowSpaces: true);
                if (string.IsNullOrWhiteSpace(csvPath))
                {
                    csvPath = defaultCsv;
                }
                csvPath = csvPath.Trim('"');

                using (Transaction tr = db.TransactionManager.StartTransaction())
                {
                    EnsureLayer(db, tr, ProfileLayer);
                    EnsureLayer(db, tr, RouteLayer);
                    EnsureLayer(db, tr, TextLayer);

                    BlockTable blockTable = (BlockTable)tr.GetObject(db.BlockTableId, OpenMode.ForRead);
                    BlockTableRecord modelSpace = (BlockTableRecord)tr.GetObject(blockTable[BlockTableRecord.ModelSpace], OpenMode.ForWrite);

                    DrawRoute(modelSpace, tr, start, end);
                    DrawProfile(modelSpace, tr, samples, insertion, datum, verticalExaggeration);
                    DrawLabels(modelSpace, tr, insertion, start, end, samples, minZ, maxZ, datum, verticalExaggeration);

                    tr.Commit();
                }

                ExportCsv(csvPath, samples);

                int invalid = samples.Count - validSamples.Count;
                ed.WriteMessage("\nASC_SCHNITT complete.");
                ed.WriteMessage("\nASC files scanned: {0}", index.Headers.Count);
                ed.WriteMessage("\nTiles intersecting section bounding box: {0}", intersectingTiles.Count);
                ed.WriteMessage("\nSamples: {0}", samples.Count);
                ed.WriteMessage("\nValid samples: {0}", validSamples.Count);
                ed.WriteMessage("\nInvalid/NODATA samples: {0}", invalid);
                ed.WriteMessage("\nMin elevation: {0:0.###} m", minZ);
                ed.WriteMessage("\nMax elevation: {0:0.###} m", maxZ);
                ed.WriteMessage("\nCSV exported: {0}", csvPath);
            }
            catch (System.Exception ex)
            {
                ed.WriteMessage("\nASC_SCHNITT failed: {0}", ex.Message);
            }
        }

        private static List<SchnittSample> SampleRoute(
            Point3d start,
            Point3d end,
            double sampleSpacing,
            List<AscGridHeader> candidateTiles,
            Dictionary<string, AscGridTile> cache)
        {
            double dx = end.X - start.X;
            double dy = end.Y - start.Y;
            double length = Math.Sqrt(dx * dx + dy * dy);
            int segmentCount = length <= 0.0 ? 0 : Math.Max(1, (int)Math.Ceiling(length / sampleSpacing));
            var samples = new List<SchnittSample>(segmentCount + 1);

            for (int i = 0; i <= segmentCount; i++)
            {
                double distance = Math.Min(i * sampleSpacing, length);
                double t = length <= 0.0 ? 0.0 : distance / length;
                double x = start.X + t * dx;
                double y = start.Y + t * dy;

                AscGridHeader? header = candidateTiles.FirstOrDefault(tile => tile.Contains(x, y));
                if (header == null)
                {
                    // Missing tile: keep the sample in the CSV and split the drawn profile at this point.
                    samples.Add(new SchnittSample { Distance = distance, X = x, Y = y, Z = null, SourceFile = string.Empty });
                    continue;
                }

                if (!cache.TryGetValue(header.FilePath, out AscGridTile? tile))
                {
                    tile = AscGridTile.Load(header);
                    cache.Add(header.FilePath, tile);
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

        private static void DrawProfile(
            BlockTableRecord modelSpace,
            Transaction tr,
            List<SchnittSample> samples,
            Point3d insertion,
            double datum,
            double verticalExaggeration)
        {
            Polyline? current = null;
            int vertexIndex = 0;

            foreach (SchnittSample sample in samples)
            {
                if (!sample.Z.HasValue)
                {
                    // Invalid samples break the profile so gaps are visible instead of being bridged.
                    current = null;
                    vertexIndex = 0;
                    continue;
                }

                if (current == null)
                {
                    current = new Polyline();
                    current.Layer = ProfileLayer;
                    modelSpace.AppendEntity(current);
                    tr.AddNewlyCreatedDBObject(current, true);
                    vertexIndex = 0;
                }

                double px = insertion.X + sample.Distance;
                double py = insertion.Y + (sample.Z.Value - datum) * verticalExaggeration;
                current.AddVertexAt(vertexIndex++, new Point2d(px, py), 0.0, 0.0, 0.0);
            }
        }

        private static void DrawRoute(BlockTableRecord modelSpace, Transaction tr, Point3d start, Point3d end)
        {
            var route = new Line(start, end) { Layer = RouteLayer };
            modelSpace.AppendEntity(route);
            tr.AddNewlyCreatedDBObject(route, true);
        }

        private static void DrawLabels(
            BlockTableRecord modelSpace,
            Transaction tr,
            Point3d insertion,
            Point3d start,
            Point3d end,
            List<SchnittSample> samples,
            double minZ,
            double maxZ,
            double datum,
            double verticalExaggeration)
        {
            double length = samples.Count == 0 ? 0.0 : samples[samples.Count - 1].Distance;
            double textHeight = 2.5;
            double lineStep = textHeight * 1.6;
            double x = insertion.X;
            double y = insertion.Y - lineStep;

            AddText(modelSpace, tr, new Point3d(start.X, start.Y, 0.0), "Start", textHeight);
            AddText(modelSpace, tr, new Point3d(end.X, end.Y, 0.0), "End", textHeight);

            string[] labels =
            {
                string.Format(CultureInfo.InvariantCulture, "Profile length: {0:0.###} m", length),
                string.Format(CultureInfo.InvariantCulture, "Min elevation: {0:0.###} m", minZ),
                string.Format(CultureInfo.InvariantCulture, "Max elevation: {0:0.###} m", maxZ),
                string.Format(CultureInfo.InvariantCulture, "Datum: {0:0.###} m", datum),
                string.Format(CultureInfo.InvariantCulture, "Vertical exaggeration: {0:0.###}", verticalExaggeration)
            };

            for (int i = 0; i < labels.Length; i++)
            {
                AddText(modelSpace, tr, new Point3d(x, y - i * lineStep, 0.0), labels[i], textHeight);
            }
        }

        private static void AddText(BlockTableRecord modelSpace, Transaction tr, Point3d position, string text, double height)
        {
            var dbText = new DBText
            {
                Position = position,
                Height = height,
                TextString = text,
                Layer = TextLayer
            };
            modelSpace.AppendEntity(dbText);
            tr.AddNewlyCreatedDBObject(dbText, true);
        }

        private static void EnsureLayer(Database db, Transaction tr, string layerName)
        {
            LayerTable layerTable = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            if (layerTable.Has(layerName))
            {
                return;
            }

            layerTable.UpgradeOpen();
            var record = new LayerTableRecord { Name = layerName };
            layerTable.Add(record);
            tr.AddNewlyCreatedDBObject(record, true);
        }

        private static void ExportCsv(string path, List<SchnittSample> samples)
        {
            string? directory = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }

            using (var writer = new StreamWriter(path, false))
            {
                writer.WriteLine("distance_m,x,y,z_m,source_asc_file");
                foreach (SchnittSample sample in samples)
                {
                    string z = sample.Z.HasValue ? sample.Z.Value.ToString("0.###", CultureInfo.InvariantCulture) : string.Empty;
                    writer.WriteLine(string.Join(",", new[]
                    {
                        sample.Distance.ToString("0.###", CultureInfo.InvariantCulture),
                        sample.X.ToString("0.###", CultureInfo.InvariantCulture),
                        sample.Y.ToString("0.###", CultureInfo.InvariantCulture),
                        z,
                        CsvEscape(sample.SourceFile)
                    }));
                }
            }
        }

        private static string CsvEscape(string value)
        {
            if (value.IndexOfAny(new[] { ',', '"', '\r', '\n' }) < 0)
            {
                return value;
            }

            return "\"" + value.Replace("\"", "\"\"") + "\"";
        }

        private static string GetDefaultCsvPath(Database db)
        {
            string drawingPath = db.Filename;
            string directory = string.IsNullOrWhiteSpace(drawingPath)
                ? Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments)
                : Path.GetDirectoryName(drawingPath) ?? Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);

            string drawingName = string.IsNullOrWhiteSpace(drawingPath)
                ? "ASC_SCHNITT"
                : Path.GetFileNameWithoutExtension(drawingPath);

            return Path.Combine(directory, drawingName + "_ASC_SCHNITT.csv");
        }

        private static string? PromptString(Editor ed, string message, bool allowSpaces)
        {
            var options = new PromptStringOptions(message)
            {
                AllowSpaces = allowSpaces
            };
            PromptResult result = ed.GetString(options);
            return result.Status == PromptStatus.OK ? result.StringResult : null;
        }

        private static Point3d PromptPoint(Editor ed, string message)
        {
            PromptPointResult result = ed.GetPoint(new PromptPointOptions(message));
            if (result.Status != PromptStatus.OK)
            {
                throw new OperationCanceledException("Command canceled.");
            }

            return result.Value;
        }

        private static double PromptDouble(Editor ed, string message, double defaultValue, double? minExclusive)
        {
            var options = new PromptDoubleOptions(message)
            {
                AllowNone = true,
                DefaultValue = defaultValue
            };

            PromptDoubleResult result = ed.GetDouble(options);
            if (result.Status == PromptStatus.None)
            {
                return defaultValue;
            }

            if (result.Status != PromptStatus.OK)
            {
                throw new OperationCanceledException("Command canceled.");
            }

            if (minExclusive.HasValue && result.Value <= minExclusive.Value)
            {
                throw new ArgumentOutOfRangeException("Value must be greater than " + minExclusive.Value.ToString(CultureInfo.InvariantCulture) + ".");
            }

            return result.Value;
        }
    }
}
