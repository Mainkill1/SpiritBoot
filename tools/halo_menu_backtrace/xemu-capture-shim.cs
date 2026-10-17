using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

internal static class Program
{
    [StructLayout(LayoutKind.Sequential)]
    private struct Rect { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetWindowRect(IntPtr window, out Rect rect);

    private static string Quote(string value)
    {
        if (value.Length != 0 && value.IndexOfAny(new[] { ' ', '\t', '\n', '\v', '"' }) < 0) return value;
        var text = new StringBuilder("\"");
        var slashes = 0;
        foreach (var c in value) {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { text.Append('\\', slashes * 2 + 1).Append(c); slashes = 0; continue; }
            text.Append('\\', slashes).Append(c); slashes = 0;
        }
        text.Append('\\', slashes * 2).Append('"');
        return text.ToString();
    }

    private static void AppendReceipt(string receipt, string line)
    {
        lock (typeof(Program)) File.AppendAllText(receipt, DateTime.UtcNow.ToString("o") + " " + line + Environment.NewLine);
    }

    private static void Capture(Process child, string evidence, string receipt, int second)
    {
        try {
            child.Refresh();
            var handle = child.MainWindowHandle;
            if (handle == IntPtr.Zero) throw new InvalidOperationException("real xemu has no main window");
            Rect rect;
            if (!GetWindowRect(handle, out rect)) throw new InvalidOperationException("GetWindowRect failed");
            var width = rect.Right - rect.Left;
            var height = rect.Bottom - rect.Top;
            if (width <= 0 || height <= 0) throw new InvalidOperationException("invalid window bounds");
            var path = Path.Combine(evidence, "shim-capture-" + second + "s.png");
            using (var image = new Bitmap(width, height))
            using (var graphics = Graphics.FromImage(image)) {
                graphics.CopyFromScreen(rect.Left, rect.Top, 0, 0, new Size(width, height), CopyPixelOperation.SourceCopy);
                image.Save(path, ImageFormat.Png);
            }
            AppendReceipt(receipt, "capture=" + second + "s status=ok pid=" + child.Id + " hwnd=0x" + handle.ToInt64().ToString("x") + " size=" + width + "x" + height + " path=" + path);
        } catch (Exception ex) {
            AppendReceipt(receipt, "capture=" + second + "s status=error type=" + ex.GetType().FullName + " message=" + ex.Message.Replace('\r', ' ').Replace('\n', ' '));
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        var package = AppDomain.CurrentDomain.BaseDirectory;
        var real = Path.Combine(package, "xemu-real.exe");
        var evidence = Environment.GetEnvironmentVariable("PR248_NATIVE_EVIDENCE");
        if (String.IsNullOrWhiteSpace(evidence)) evidence = package;
        Directory.CreateDirectory(evidence);
        var receipt = Path.Combine(evidence, "shim-capture-receipt.txt");
        File.WriteAllText(receipt, DateTime.UtcNow.ToString("o") + " shim_start package=" + package + " real=" + real + Environment.NewLine);
        try {
            var info = new ProcessStartInfo {
                FileName = real,
                WorkingDirectory = package,
                UseShellExecute = false,
                Arguments = String.Join(" ", Array.ConvertAll(args, Quote))
            };
            var child = Process.Start(info);
            if (child == null) throw new InvalidOperationException("Process.Start returned null");
            AppendReceipt(receipt, "child_start pid=" + child.Id + " arguments=" + info.Arguments);
            var start = Stopwatch.StartNew();
            var thread = new Thread(delegate() {
                foreach (var second in new[] { 12, 30, 60 }) {
                    while (!child.HasExited && start.Elapsed < TimeSpan.FromSeconds(second)) Thread.Sleep(50);
                    if (child.HasExited) { AppendReceipt(receipt, "capture=" + second + "s status=skipped child_exited=true"); break; }
                    Capture(child, evidence, receipt, second);
                }
            });
            thread.IsBackground = true;
            thread.Start();
            child.WaitForExit();
            AppendReceipt(receipt, "child_exit pid=" + child.Id + " code=" + child.ExitCode + " elapsed_ms=" + start.ElapsedMilliseconds);
            return child.ExitCode;
        } catch (Exception ex) {
            AppendReceipt(receipt, "shim_error type=" + ex.GetType().FullName + " message=" + ex.ToString().Replace('\r', ' ').Replace('\n', ' '));
            return 111;
        }
    }
}
