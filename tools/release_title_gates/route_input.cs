// SPDX-License-Identifier: GPL-2.0-or-later
// Original diagnostic adapter using the owned runner's public Win32 SendInput approach.
using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
public static class DoaOwnedInput {
    [StructLayout(LayoutKind.Sequential)] private struct Input { public uint Type; public InputUnion Union; }
    [StructLayout(LayoutKind.Explicit)] private struct InputUnion {
        [FieldOffset(0)] public KeyboardInput Keyboard; [FieldOffset(0)] public MouseInput Mouse;
    }
    [StructLayout(LayoutKind.Sequential)] private struct KeyboardInput { public ushort VirtualKey, ScanCode; public uint Flags, Time; public UIntPtr ExtraInfo; }
    [StructLayout(LayoutKind.Sequential)] private struct MouseInput { public int X,Y; public uint MouseData,Flags,Time; public UIntPtr ExtraInfo; }
    [DllImport("user32.dll",SetLastError=true)] private static extern uint SendInput(uint n, Input[] inputs, int size);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr window, out int pid);
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr window);
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr window,int command);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern bool GetClientRect(IntPtr window,out Rect rect);
    [DllImport("user32.dll")] private static extern bool ClientToScreen(IntPtr window,ref Point point);
    [DllImport("user32.dll",CharSet=CharSet.Unicode,SetLastError=true)] private static extern bool SetWindowText(IntPtr window,string title);
    [DllImport("user32.dll")] private static extern IntPtr GetProcessWindowStation();
    [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] private static extern IntPtr GetThreadDesktop(uint thread);
    [DllImport("user32.dll",CharSet=CharSet.Unicode,SetLastError=true)] private static extern bool GetUserObjectInformation(IntPtr handle,int index,StringBuilder text,int bytes,out int needed);
    [StructLayout(LayoutKind.Sequential)] private struct Rect { public int Left,Top,Right,Bottom; }
    [StructLayout(LayoutKind.Sequential)] private struct Point { public int X,Y; }
    private static string Name(IntPtr handle) {
        StringBuilder value=new StringBuilder(256); int needed;
        if(!GetUserObjectInformation(handle,2,value,value.Capacity*2,out needed)) throw new InvalidOperationException("Desktop name unavailable");
        return value.ToString();
    }
    public static string Station() { return Name(GetProcessWindowStation()); }
    public static string Desktop() { return Name(GetThreadDesktop(GetCurrentThreadId())); }
    public static void ValidateBounds(int pid,long ticks,int session,int scan,int holdMs) {
        if(pid<=0 || ticks<=0 || session<=0 || scan<=0 || scan>127 || holdMs<25 || holdMs>30000) throw new InvalidOperationException("Invalid bounded input request");
    }
    private static IntPtr OwnedWindow(int pid,long ticks,int session,string exe) {
        using(Process process=Process.GetProcessById(pid)) {
            process.Refresh();
            if(process.HasExited || process.SessionId!=session || process.StartTime.ToUniversalTime().Ticks!=ticks ||
               !String.Equals(process.MainModule.FileName,exe,StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException("Owned guest lifetime changed");
            IntPtr window=process.MainWindowHandle; int owner;
            GetWindowThreadProcessId(window,out owner);
            if(window==IntPtr.Zero || owner!=pid || !IsWindowVisible(window)) throw new InvalidOperationException("Visible owned child window unavailable");
            return window;
        }
    }
    private static void Send(ushort scan,bool extended,bool down) {
        Input input=new Input(); input.Type=1;
        input.Union.Keyboard.ScanCode=scan; input.Union.Keyboard.Flags=8u|(extended?1u:0u)|(down?0u:2u);
        if(SendInput(1,new Input[]{input},Marshal.SizeOf(typeof(Input)))!=1) throw new InvalidOperationException("SendInput failed: "+Marshal.GetLastWin32Error());
    }
    private static Bitmap CaptureClient(IntPtr window) {
        Rect bounds; Point origin=new Point();
        if(!GetClientRect(window,out bounds) || !ClientToScreen(window,ref origin)) throw new InvalidOperationException("Owned window client bounds unavailable");
        int width=bounds.Right-bounds.Left, height=bounds.Bottom-bounds.Top;
        if(width<640 || height<400 || width>4096 || height>2160) throw new InvalidOperationException("Unexpected owned window capture bounds");
        Bitmap bitmap=new Bitmap(width,height,PixelFormat.Format24bppRgb);
        using(Graphics graphics=Graphics.FromImage(bitmap)) graphics.CopyFromScreen(origin.X,origin.Y,0,0,new Size(width,height),CopyPixelOperation.SourceCopy);
        return bitmap;
    }
    private static int GuideOffset(Bitmap bitmap,out int pixels) {
        long total=0, weight=0; pixels=0;
        int x0=bitmap.Width*24/100, x1=bitmap.Width*76/100;
        int y0=bitmap.Height*43/100, y1=bitmap.Height*76/100;
        for(int y=y0;y<y1;y+=2) for(int x=x0;x<x1;x+=2) {
            Color c=bitmap.GetPixel(x,y);
            // Forza's suggested line is saturated green on the opening sector.
            // Require both absolute and relative separation to reject road/sky.
            if(c.G>=80 && c.G-c.R>=32 && c.G-c.B>=20) {
                int w=1+(y-y0)/12; total+=(long)x*w; weight+=w; pixels++;
            }
        }
        return weight==0 ? 0 : (int)(total/weight)-bitmap.Width/2;
    }
    public static void DriveGuided(int pid,long ticks,int session,string exe,string outputDir,int durationMs) {
        const ushort RTrigger=0x18, LStickLeft=0x1f, LStickRight=0x21;
        if(durationMs<10000 || durationMs>45000 || String.IsNullOrEmpty(outputDir)) throw new InvalidOperationException("Invalid guided route request");
        outputDir=Path.GetFullPath(outputDir); Directory.CreateDirectory(outputDir);
        IntPtr window=OwnedWindow(pid,ticks,session,exe);
        ShowWindow(window,9); SetForegroundWindow(window); Thread.Sleep(30);
        if(OwnedWindow(pid,ticks,session,exe)!=window) throw new InvalidOperationException("Owned window changed before route");
        int focused; GetWindowThreadProcessId(GetForegroundWindow(),out focused);
        if(focused!=pid || GetForegroundWindow()!=window) throw new InvalidOperationException("Owned child focus was not granted; no route sent");
        Stopwatch timer=Stopwatch.StartNew(); bool throttleDown=false,steerDown=false; ushort steer=0; int frame=0; long nextCapture=0;
        string telemetry=Path.Combine(outputDir,"route-telemetry.jsonl");
        try {
            Send(RTrigger,false,true); throttleDown=true;
            while(timer.ElapsedMilliseconds<durationMs) {
                int offset=0,count=0; string action="coast";
                using(Bitmap bitmap=CaptureClient(window)) {
                    offset=GuideOffset(bitmap,out count);
                    if(timer.ElapsedMilliseconds>=nextCapture) {
                        string path=Path.Combine(outputDir,"route-live-"+frame.ToString("D2",CultureInfo.InvariantCulture)+".png");
                        bitmap.Save(path,ImageFormat.Png); frame++; nextCapture+=2000;
                    }
                }
                if(count>=8 && Math.Abs(offset)>=28) {
                    steer=offset<0 ? LStickLeft : LStickRight; action=offset<0 ? "left" : "right";
                    Send(steer,false,true); steerDown=true; Thread.Sleep(Math.Min(55,25+Math.Abs(offset)/12));
                    Send(steer,false,false); steerDown=false;
                }
                File.AppendAllText(telemetry,String.Format(CultureInfo.InvariantCulture,"{{\"elapsed_ms\":{0},\"guide_offset\":{1},\"guide_pixels\":{2},\"steer\":\"{3}\"}}\n",timer.ElapsedMilliseconds,offset,count,action));
                Thread.Sleep(65);
            }
        }
        finally { if(steerDown) Send(steer,false,false); if(throttleDown) Send(RTrigger,false,false); }
        using(Bitmap final=CaptureClient(window)) final.Save(Path.Combine(outputDir,"route-live-final.png"),ImageFormat.Png);
        GetWindowThreadProcessId(GetForegroundWindow(),out focused);
        if(focused!=pid) throw new InvalidOperationException("Focus changed during guided route; all key releases attempted");
    }
    public static void Press(int pid,long ticks,int session,string exe,int scan,bool extended,int holdMs) {
        ValidateBounds(pid,ticks,session,scan,holdMs);
        IntPtr window=OwnedWindow(pid,ticks,session,exe);
        ShowWindow(window,9); SetForegroundWindow(window); Thread.Sleep(30);
        if(OwnedWindow(pid,ticks,session,exe)!=window) throw new InvalidOperationException("Owned window changed before input");
        int focused; GetWindowThreadProcessId(GetForegroundWindow(),out focused);
        if(focused!=pid || GetForegroundWindow()!=window) throw new InvalidOperationException("Owned child focus was not granted; no key sent");
        bool down=false;
        try { Send((ushort)scan,extended,true); down=true; Thread.Sleep(holdMs); }
        finally { if(down) Send((ushort)scan,extended,false); }
        GetWindowThreadProcessId(GetForegroundWindow(),out focused);
        if(focused!=pid) throw new InvalidOperationException("Focus changed during bounded press; own key release attempted");
    }
    public static void PressChord(int pid,long ticks,int session,string exe,int[] scans,bool[] extended,int holdMs) {
        if(scans==null || extended==null || scans.Length<1 || scans.Length>4 || scans.Length!=extended.Length || holdMs<25 || holdMs>30000)
            throw new InvalidOperationException("Invalid bounded chord request");
        for(int i=0;i<scans.Length;i++) {
            if(scans[i]<=0 || scans[i]>127) throw new InvalidOperationException("Invalid chord scan code");
            for(int j=0;j<i;j++) if(scans[i]==scans[j]) throw new InvalidOperationException("Duplicate chord scan code");
        }
        IntPtr window=OwnedWindow(pid,ticks,session,exe);
        ShowWindow(window,9); SetForegroundWindow(window); Thread.Sleep(30);
        if(OwnedWindow(pid,ticks,session,exe)!=window) throw new InvalidOperationException("Owned window changed before chord");
        int focused; GetWindowThreadProcessId(GetForegroundWindow(),out focused);
        if(focused!=pid || GetForegroundWindow()!=window) throw new InvalidOperationException("Owned child focus was not granted; no chord sent");
        int down=0;
        try { for(;down<scans.Length;down++) Send((ushort)scans[down],extended[down],true); Thread.Sleep(holdMs); }
        finally { for(int i=down-1;i>=0;i--) Send((ushort)scans[i],extended[i],false); }
        GetWindowThreadProcessId(GetForegroundWindow(),out focused);
        if(focused!=pid) throw new InvalidOperationException("Focus changed during bounded chord; all key releases attempted");
    }
    public static void Rename(int pid,long ticks,int session,string exe,string title) {
        if(String.IsNullOrEmpty(title)||title.Length>100||title.IndexOfAny(new char[]{'\r','\n','\0'})>=0) throw new InvalidOperationException("Invalid window label");
        IntPtr window=OwnedWindow(pid,ticks,session,exe);
        if(!SetWindowText(window,title)) throw new InvalidOperationException("Owned window rename failed");
    }
}
