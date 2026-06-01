using System;
using System.IO;

namespace AscSchnitt.Tests
{
    // Writes a temporary .asc file and deletes it on dispose.
    internal sealed class TempAsc : IDisposable
    {
        public string Path { get; }

        public TempAsc(params string[] lines)
        {
            Path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "asc_" + Guid.NewGuid().ToString("N") + ".asc");
            File.WriteAllLines(Path, lines);
        }

        public void Dispose()
        {
            try { File.Delete(Path); } catch { /* best effort */ }
        }
    }

    // Writes several .asc files into a temporary folder and deletes the folder on dispose.
    internal sealed class TempAscFolder : IDisposable
    {
        public string Root { get; }

        public TempAscFolder()
        {
            Root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "ascdir_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Root);
        }

        public string Add(string name, params string[] lines)
        {
            string path = System.IO.Path.Combine(Root, name);
            File.WriteAllLines(path, lines);
            return path;
        }

        public void Dispose()
        {
            try { Directory.Delete(Root, recursive: true); } catch { /* best effort */ }
        }
    }
}
