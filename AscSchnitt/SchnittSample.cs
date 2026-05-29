namespace AscSchnitt
{
    public sealed class SchnittSample
    {
        public double Distance { get; set; }
        public double X { get; set; }
        public double Y { get; set; }
        public double? Z { get; set; }
        public string SourceFile { get; set; } = string.Empty;
    }
}
