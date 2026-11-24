[CmdletBinding(DefaultParameterSetName = 'Plan')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Plan')][string]$Plan,
    [Parameter(Mandatory, ParameterSetName = 'Single')][string]$Workflow,
    [Parameter(Mandatory, ParameterSetName = 'Single')][string]$WatchFile,
    [Parameter(Mandatory)][string]$Report,
    [ValidateRange(5, 3600)][int]$TimeoutSeconds = 45,
    [int]$DesignerProcessId,
    [string]$DesignerLauncher,
    [ValidateSet('auto', 'wand', 'options')][string]$AppLaunch = 'auto',
    [switch]$ManualAppInputs,
    [Parameter(DontShow)][switch]$Worker
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This runner requires Windows Designer.' }

function Move-DesignerReport([string]$Source, [string]$Destination, [string]$Operation) {
    for ($attempt = 0; $attempt -lt 3; $attempt++) {
        try {
            [IO.File]::Move($Source, $Destination, $true)
            return
        } catch {
            $cause = $_.Exception.InnerException ?? $_.Exception
            if ($attempt -eq 2 -or ($cause -isnot [IO.IOException] -and $cause -isnot [UnauthorizedAccessException])) {
                throw "$Operation failed. Source: '$Source'. Destination: '$Destination'. $($cause.Message)"
            }
            Start-Sleep -Milliseconds (75 * ($attempt + 1))
        }
    }
}

function Write-DesignerJson($Value, [string]$Path) {
    $temporary = "$Path.tmp"
    try {
        ConvertTo-Json -InputObject $Value -Depth 6 | Set-Content -LiteralPath $temporary -Encoding utf8 -ErrorAction Stop
    } catch {
        throw "Write Designer report data failed at '$temporary' for destination '$Path'. $($_.Exception.Message)"
    }
    $operation = if ($Path.EndsWith('.progress')) { 'Publish Designer progress' } else { 'Publish Designer report' }
    Move-DesignerReport $temporary $Path $operation
}

function Set-DesignerStage([string]$Stage, [int]$Seconds = 20) {
    $script:stage = @{
        stage = $Stage; workflow = $script:currentWorkflow; case_index = $script:caseIndex
        designer_pid = $script:sessionId; session = $script:sessionMode
        stage_deadline = [DateTimeOffset]::UtcNow.AddSeconds([Math]::Min($Seconds, $TimeoutSeconds)).ToUnixTimeMilliseconds()
        case_deadline = $script:caseDeadline
    }
    Write-DesignerJson $script:stage "$Report.progress"
    Write-Host "Designer: $Stage"
}

function New-DesignerBlocked($Progress, [string]$Detail, [string]$Reason) {
    @{
        status = 'blocked'; workflow = $Progress.workflow; stage = $Progress.stage
        designer_pid = $Progress.designer_pid; session = $Progress.session
        reason = $Reason; detail = $Detail
    }
}

function Read-DesignerProgress([string]$Path) {
    if (-not [IO.File]::Exists($Path)) { return }
    $sharing = [IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete
    $reader = [IO.StreamReader]::new([IO.File]::Open($Path, 'Open', 'Read', $sharing))
    try { ConvertFrom-Json -InputObject $reader.ReadToEnd() -AsHashtable }
    finally { $reader.Dispose() }
}

function Invoke-DesignerSupervisor([string]$ScriptPath, [string]$ReportPath, $Arguments, [int]$Seconds) {
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($ReportPath))
    $scratch = "$ReportPath.$([guid]::NewGuid().ToString('N'))"
    $progress = @{ stage = 'start automation'; case_index = 0 }
    $process = $null
    $preserveScratch = $false
    $mutex = [Threading.Mutex]::new($false, 'Local\Alteryx2Python.DesignerBatch')
    $hasLock = $false
    try {
        try { $hasLock = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $hasLock = $true }
        if (-not $hasLock) { throw 'A Designer parity batch is already running in this Windows session.' }
        $startInfo = [Diagnostics.ProcessStartInfo]::new((Get-Process -Id $PID).Path)
        $startInfo.UseShellExecute = $false
        foreach ($argument in @('-NoProfile', '-File', $ScriptPath, '-Worker', '-Report', $scratch)) {
            $startInfo.ArgumentList.Add($argument)
        }
        foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add([string]$argument) }
        $process = [Diagnostics.Process]::Start($startInfo)
        $startupDeadline = [DateTimeOffset]::UtcNow.AddSeconds([Math]::Min(30, $Seconds)).ToUnixTimeMilliseconds()
        while (-not $process.WaitForExit(250)) {
            $latest = Read-DesignerProgress "$scratch.progress"
            if ($latest) { $progress = $latest }
            $deadline = $progress.stage_deadline ?? $startupDeadline
            if ($progress.case_deadline) { $deadline = [Math]::Min($deadline, $progress.case_deadline) }
            if ([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() -ge $deadline) {
                if (-not $process.HasExited) { $process.Kill() }
                [void]$process.WaitForExit(2000)
                $completed = @(Get-Content -LiteralPath $scratch -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json -AsHashtable)
                $completed = @($completed | Select-Object -First ([int]$progress.case_index))
                $detail = "Designer automation timed out during '$($progress.stage)'."
                $completed += New-DesignerBlocked $progress $detail 'automation_timeout'
                Write-DesignerJson $completed $ReportPath
                Write-Host $detail
                return 1
            }
        }
        if (-not [IO.File]::Exists($scratch)) {
            $latest = Read-DesignerProgress "$scratch.progress"
            if ($latest) { $progress = $latest }
            throw "Designer automation exited during '$($progress.stage)' (code $($process.ExitCode))."
        }
        try {
            Move-DesignerReport $scratch $ReportPath 'Publish the final Designer run report'
        } catch {
            $preserveScratch = $true
            throw
        }
        return $process.ExitCode
    } catch {
        $detail = $_.Exception.Message
        Write-Host $detail
        try {
            Write-DesignerJson @((New-DesignerBlocked $progress $detail 'automation_blocked')) $ReportPath
        } catch {
            Write-Host "Could not save the blocked run report. $($_.Exception.Message)"
        }
        return 1
    } finally {
        if ($process) {
            if (-not $process.HasExited) { $process.Kill() }
            $process.Dispose()
        }
        if ($hasLock) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
        foreach ($path in @($scratch, "$scratch.tmp", "$scratch.progress", "$scratch.progress.tmp")) {
            if ($preserveScratch -and $path -eq $scratch) { continue }
            try { [IO.File]::Delete($path) }
            catch { Write-Host "Could not remove Designer scratch file '$path'. $($_.Exception.Message)" }
        }
    }
}

if (-not $Worker) {
    $arguments = @('-TimeoutSeconds', $TimeoutSeconds)
    foreach ($parameter in $PSBoundParameters.GetEnumerator()) {
        if ($parameter.Key -in @('Report', 'TimeoutSeconds', 'Worker')) { continue }
        if ($parameter.Value -is [switch]) {
            if ($parameter.Value) { $arguments += "-$($parameter.Key)" }
        } else {
            $arguments += @("-$($parameter.Key)", $parameter.Value)
        }
    }
    $reportPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Report)
    exit (Invoke-DesignerSupervisor $PSCommandPath $reportPath $arguments $TimeoutSeconds)
}

Set-DesignerStage 'load Windows automation'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase
$drawingAssemblies = @([System.Drawing.Bitmap].Assembly.Location, [System.Drawing.Rectangle].Assembly.Location)
$drawingAssemblies += @(Get-ChildItem -LiteralPath $PSHOME -File -Filter 'System.Private.Windows.*.dll' | ForEach-Object FullName)
Add-Type -ReferencedAssemblies $drawingAssemblies -TypeDefinition @'
using System;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Text;

public static class DesignerMouse {
    [StructLayout(LayoutKind.Sequential)] public struct Box { public int Left, Top, Right, Bottom; }
    [StructLayout(LayoutKind.Sequential)] public struct Point { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)] private struct TitleBarInfo {
        public int Size;
        public Box Bounds;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 6)] public uint[] State;
    }
    private delegate bool ChildCallback(IntPtr hwnd, IntPtr state);
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
    [DllImport("user32.dll")] private static extern bool GetWindowRect(IntPtr hwnd, out Box box);
    [DllImport("user32.dll")] private static extern bool PrintWindow(IntPtr hwnd, IntPtr dc, uint flags);
    [DllImport("user32.dll")] private static extern bool EnumChildWindows(IntPtr hwnd, ChildCallback callback, IntPtr state);
    [DllImport("user32.dll")] private static extern bool EnumWindows(ChildCallback callback, IntPtr state);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetClassName(IntPtr hwnd, StringBuilder name, int size);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] private static extern int GetWindowText(IntPtr hwnd, StringBuilder title, int size);
    [DllImport("user32.dll")] private static extern int GetDlgCtrlID(IntPtr hwnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint message, IntPtr wParam,
        string text, uint flags, uint milliseconds, out IntPtr result);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint message, IntPtr wParam,
        StringBuilder text, uint flags, uint milliseconds, out IntPtr result);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint message, IntPtr wParam,
        IntPtr lParam, uint flags, uint milliseconds, out IntPtr result);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsHungAppWindow(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern bool ShowWindowAsync(IntPtr hwnd, int command);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern bool GetTitleBarInfo(IntPtr hwnd, ref TitleBarInfo info);
    [DllImport("user32.dll")] private static extern bool SetWindowPos(IntPtr hwnd, IntPtr after,
        int x, int y, int width, int height, uint flags);
    [DllImport("user32.dll")] private static extern IntPtr WindowFromPoint(Point point);
    [DllImport("user32.dll")] private static extern bool IsChild(IntPtr parent, IntPtr child);
    [DllImport("user32.dll")] private static extern IntPtr GetParent(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern bool GetCursorPos(out Point point);
    [DllImport("user32.dll")] private static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] private static extern void mouse_event(uint flags, uint x, uint y, uint data, UIntPtr extra);
    [DllImport("user32.dll")] private static extern void keybd_event(byte key, byte scan, uint flags, UIntPtr extra);
    [DllImport("user32.dll")] private static extern short GetAsyncKeyState(int key);
    [DllImport("user32.dll")] public static extern IntPtr GetLastActivePopup(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern bool ScreenToClient(IntPtr hwnd, ref Point point);
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll", SetLastError = true)] private static extern bool PostMessage(IntPtr hwnd, uint message, IntPtr wParam, IntPtr lParam);

    public static void Restore(IntPtr hwnd, uint expectedProcess) {
        uint pid;
        GetWindowThreadProcessId(hwnd, out pid);
        if (pid != expectedProcess || !ShowWindowAsync(hwnd, 9))
            throw new InvalidOperationException("Cannot restore the selected Designer window.");
    }

    private static Bitmap Capture(IntPtr hwnd, out Box window) {
        if (!GetWindowRect(hwnd, out window) || window.Right <= window.Left || window.Bottom <= window.Top)
            throw new InvalidOperationException("Designer window is not available.");
        var image = new Bitmap(window.Right - window.Left, window.Bottom - window.Top);
        try {
            using (var graphics = Graphics.FromImage(image)) {
                IntPtr dc = graphics.GetHdc();
                try {
                    if (!PrintWindow(hwnd, dc, 2)) throw new InvalidOperationException("Cannot capture Designer.");
                } finally { graphics.ReleaseHdc(dc); }
            }
            return image;
        } catch { image.Dispose(); throw; }
    }

    public static void Save(IntPtr hwnd, string path) {
        Box window;
        using (var image = Capture(hwnd, out window)) { image.Save(path, System.Drawing.Imaging.ImageFormat.Png); }
    }

    public static bool IsRunReady(IntPtr hwnd) {
        if (!IsWindowEnabled(hwnd)) return false;
        Box window;
        try {
            using (var image = Capture(hwnd, out window)) { FindRun(image); }
            return true;
        } catch (InvalidOperationException) { return false; }
    }

    private static int PaintedWidth(Bitmap image) {
        // Some DPI combinations render a smaller window into the top-left of PrintWindow's bitmap.
        int contentRight = image.Width;
        while (contentRight > 0) {
            bool painted = false;
            for (int y = 24; y < Math.Min(240, image.Height); y += 12) {
                Color pixel = image.GetPixel(contentRight - 1, y);
                if ((pixel.R | pixel.G | pixel.B) != 0) {
                    painted = true;
                    break;
                }
            }
            if (painted) return contentRight;
            contentRight--;
        }
        return image.Width;
    }

    private static Rectangle FindRun(Bitmap image) {
        int contentRight = PaintedWidth(image);
        int width = Math.Min(520, contentRight);
        int height = Math.Min(500, image.Height);
        int originX = contentRight - width;
        var blue = new bool[height, width];
        for (int y = 80; y < height; y++)
            for (int x = 0; x < width; x++) {
                Color c = image.GetPixel(originX + x, y);
                blue[y, x] = c.R == 10 && c.G == 113 && c.B == 208;
            }
        Rectangle match = Rectangle.Empty;
        int matches = 0;
        var queue = new Point[width * height];
        int[] dx = {1, -1, 0, 0}, dy = {0, 0, 1, -1};
        for (int y = 80; y < height; y++)
            for (int x = 0; x < width; x++) {
                if (!blue[y, x]) continue;
                int left = x, right = x, top = y, bottom = y, pixels = 0;
                blue[y, x] = false;
                int head = 0, tail = 0;
                queue[tail++] = new Point { X = x, Y = y };
                while (head < tail) {
                    Point p = queue[head++];
                    left = Math.Min(left, p.X); right = Math.Max(right, p.X);
                    top = Math.Min(top, p.Y); bottom = Math.Max(bottom, p.Y);
                    pixels++;
                    for (int direction = 0; direction < 4; direction++) {
                        int nx = p.X + dx[direction], ny = p.Y + dy[direction];
                        if (nx < 0 || nx >= width || ny < 0 || ny >= height || !blue[ny, nx]) continue;
                        blue[ny, nx] = false;
                        queue[tail++] = new Point { X = nx, Y = ny };
                    }
                }
                int w = right - left + 1, h = bottom - top + 1;
                if (w >= 42 && w <= 190 && h >= 15 && h <= 76 && width - right < 135 &&
                    (double)w / h >= 2.1 && (double)w / h <= 3.3 && pixels > 0.48 * w * h) {
                    match = Rectangle.FromLTRB(originX + left, top, originX + right + 1, bottom + 1);
                    matches++;
                }
            }
        if (matches != 1)
            throw new InvalidOperationException("Could not uniquely identify the blue Designer Run button.");
        return match;
    }

    private static Point ToolbarMenuPoint(IntPtr root, int x, int y) {
        Box window;
        using (var image = Capture(root, out window)) {
            double scale = (double)image.Width / PaintedWidth(image);
            return new Point { X = window.Left + (int)(x * scale), Y = window.Top + (int)(y * scale) };
        }
    }

    public static string WindowTitle(IntPtr hwnd, uint expectedProcess) {
        uint pid;
        GetWindowThreadProcessId(hwnd, out pid);
        if (pid != expectedProcess) throw new InvalidOperationException("The selected Designer window is no longer available.");
        var title = new StringBuilder(1024);
        GetWindowText(hwnd, title, title.Capacity);
        return title.ToString();
    }

    public static void RaiseForActivation(IntPtr root, uint expectedProcess) {
        RequireVisibleWindow(root, expectedProcess);
        // HWND_TOP, NOSIZE | NOMOVE | NOACTIVATE | ASYNCWINDOWPOS.
        SetWindowPos(root, IntPtr.Zero, 0, 0, 0, 0, 0x4013);
    }

    public static bool TryActivateCaption(IntPtr root, uint expectedProcess) {
        RequireVisibleWindow(root, expectedProcess);
        if (GetForegroundWindow() == root) return true;
        if (GetAsyncKeyState(1) < 0 || GetAsyncKeyState(0x10) < 0 ||
            GetAsyncKeyState(0x11) < 0 || GetAsyncKeyState(0x12) < 0) return false;
        var bar = new TitleBarInfo { Size = Marshal.SizeOf<TitleBarInfo>() };
        if (!GetTitleBarInfo(root, ref bar)) return false;
        Box bounds = bar.Bounds;
        for (int fraction = 1; fraction <= 3; fraction++) {
            var point = new Point {
                X = bounds.Left + fraction * (bounds.Right - bounds.Left) / 4,
                Y = bounds.Top + (bounds.Bottom - bounds.Top) / 2
            };
            if (WindowFromPoint(point) != root) continue;
            // Ask Windows whether this is a caption, excluding buttons and Designer controls.
            var position = new IntPtr(((point.Y & 65535) << 16) | (point.X & 65535));
            IntPtr hit;
            if (SendMessageTimeout(root, 0x0084, IntPtr.Zero, position, 2, 500, out hit) == IntPtr.Zero ||
                hit.ToInt64() != 2) continue;
            Point original;
            if (!GetCursorPos(out original) || !SetCursorPos(point.X, point.Y)) return false;
            try {
                if (WindowFromPoint(point) != root || !IsWindowEnabled(root)) return false;
                mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
                mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
                return true;
            } finally { SetCursorPos(original.X, original.Y); }
        }
        return false;
    }

    public static bool TryShortcut(IntPtr root, uint expectedProcess, byte key) {
        FocusModal(root, expectedProcess);
        const byte Control = 0x11;
        if (GetForegroundWindow() != root || GetAsyncKeyState(Control) < 0 ||
            GetAsyncKeyState(0x10) < 0 || GetAsyncKeyState(0x12) < 0) return false;
        keybd_event(Control, 0, 0, UIntPtr.Zero);
        try {
            if (GetForegroundWindow() != root) return false;
            keybd_event(key, 0, 0, UIntPtr.Zero);
            keybd_event(key, 0, 2, UIntPtr.Zero);
        } finally {
            keybd_event(Control, 0, 2, UIntPtr.Zero);
        }
        return true;
    }

    public static void ClickMenuItem(IntPtr popup, uint expectedProcess, int x, int y) {
        Box window;
        if (!GetWindowRect(popup, out window) || x <= 0 || x >= window.Right - window.Left ||
            y <= 0 || y >= window.Bottom - window.Top)
            throw new InvalidOperationException("Unexpected Designer menu layout.");
        Click(popup, expectedProcess, window.Left + x, window.Top + y);
    }

    public static IntPtr[] VisibleMenus(uint expectedProcess) {
        var menus = new IntPtr[16];
        int count = 0;
        EnumWindows((hwnd, state) => {
            uint pid;
            GetWindowThreadProcessId(hwnd, out pid);
            if (pid != expectedProcess || !IsWindowVisible(hwnd)) return true;
            var name = new StringBuilder(128);
            GetClassName(hwnd, name, name.Capacity);
            if (name.ToString().StartsWith("WindowsForms10.Window.20808.") && count < menus.Length)
                menus[count++] = hwnd;
            return true;
        }, IntPtr.Zero);
        Array.Resize(ref menus, count);
        return menus;
    }

    public static IntPtr FindDialog(uint expectedProcess, string expectedTitle) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((hwnd, state) => {
            uint pid;
            GetWindowThreadProcessId(hwnd, out pid);
            if (pid != expectedProcess || !IsWindowVisible(hwnd) || !IsWindowEnabled(hwnd)) return true;
            var title = new StringBuilder(256);
            GetWindowText(hwnd, title, title.Capacity);
            if (!String.Equals(title.ToString().Trim(), expectedTitle, StringComparison.Ordinal)) return true;
            found = hwnd;
            return false;
        }, IntPtr.Zero);
        return found;
    }

    private static bool IsOneRegistration(IntPtr hwnd, IntPtr mainWindow, uint expectedProcess) {
        uint pid;
        GetWindowThreadProcessId(hwnd, out pid);
        if (hwnd == mainWindow || pid != expectedProcess || !IsWindowVisible(hwnd) || !IsWindowEnabled(hwnd))
            return false;
        var title = new StringBuilder(256);
        GetWindowText(hwnd, title, title.Capacity);
        switch (title.ToString().Trim().ToLowerInvariant()) {
            case "alteryx one":
            case "welcome to alteryx one":
            case "register for alteryx one":
            case "alteryx one registration":
                return true;
            default:
                return false;
        }
    }

    public static IntPtr FindOneRegistration(IntPtr mainWindow, uint expectedProcess) {
        IntPtr popup = GetLastActivePopup(mainWindow);
        if (IsOneRegistration(popup, mainWindow, expectedProcess)) return popup;
        IntPtr found = IntPtr.Zero;
        EnumWindows((hwnd, state) => {
            if (!IsOneRegistration(hwnd, mainWindow, expectedProcess)) return true;
            found = hwnd;
            return false;
        }, IntPtr.Zero);
        return found;
    }

    public static void ClickControl(IntPtr control, uint expectedProcess) {
        Box bounds;
        if (!GetWindowRect(control, out bounds) || !IsWindowEnabled(control) || !IsWindowVisible(control))
            throw new InvalidOperationException("Dialog button is not available.");
        Click(control, expectedProcess, (bounds.Left + bounds.Right) / 2, (bounds.Top + bounds.Bottom) / 2);
    }

    private static bool IsNumericEdit(IntPtr control, uint expectedProcess) {
        uint pid;
        GetWindowThreadProcessId(control, out pid);
        if (pid != expectedProcess || !IsWindowVisible(control) || !IsWindowEnabled(control)) return false;
        var name = new StringBuilder(100);
        GetClassName(control, name, name.Capacity);
        return name.ToString().StartsWith("WindowsForms10.EDIT.");
    }

    public static string ReadNumericEdit(IntPtr control, uint expectedProcess) {
        if (!IsNumericEdit(control, expectedProcess))
            throw new InvalidOperationException("Expected a Designer numeric edit control.");
        var text = new StringBuilder(Math.Max(64, GetTextLength(control) + 1));
        IntPtr length;
        // WM_GETTEXT reads the edit value across processes. UI Automation Name is a label.
        if (SendMessageTimeout(control, 0x000D, new IntPtr(text.Capacity), text, 2, 3000, out length) == IntPtr.Zero)
            throw new InvalidOperationException("Designer did not return the numeric edit value.");
        return text.ToString();
    }

    private static int GetTextLength(IntPtr control) {
        IntPtr length;
        if (SendMessageTimeout(control, 0x000E, IntPtr.Zero, (string)null, 2, 3000, out length) == IntPtr.Zero)
            throw new InvalidOperationException("Designer did not return the edit length.");
        return length.ToInt32();
    }

    public static bool NumericEditMatches(IntPtr control, uint expectedProcess, decimal expected) {
        decimal actual;
        return decimal.TryParse(ReadNumericEdit(control, expectedProcess), out actual) && actual == expected;
    }

    public static void SetNumericEdit(IntPtr control, uint expectedProcess, string value) {
        if (!IsNumericEdit(control, expectedProcess))
            throw new InvalidOperationException("Expected a Designer numeric edit control.");
        if (!PostMessage(control, 0x00B1, IntPtr.Zero, new IntPtr(-1)))
            throw new InvalidOperationException("Designer rejected the numeric app answer.");
        foreach (char digit in value)
            if (!PostMessage(control, 0x0102, new IntPtr(digit), new IntPtr(1)))
                throw new InvalidOperationException("Designer rejected a character in the numeric app answer.");
    }

    public static void SetTextEdit(IntPtr control, uint expectedProcess, string value) {
        IntPtr result;
        if (!IsNumericEdit(control, expectedProcess) ||
            SendMessageTimeout(control, 0x000C, IntPtr.Zero, value, 2, 3000, out result) == IntPtr.Zero)
            throw new InvalidOperationException("Designer rejected the text app answer.");
    }

    private static IntPtr UniqueVisibleChild(IntPtr root, uint expectedProcess, Func<IntPtr, string, bool> match) {
        IntPtr found = IntPtr.Zero;
        EnumChildWindows(root, (child, state) => {
            uint pid;
            GetWindowThreadProcessId(child, out pid);
            if (pid != expectedProcess || !IsWindowVisible(child) || !IsWindowEnabled(child)) return true;
            var name = new StringBuilder(100);
            GetClassName(child, name, name.Capacity);
            if (!match(child, name.ToString())) return true;
            if (found == IntPtr.Zero) {
                found = child;
                return true;
            }
            found = IntPtr.Zero;
            return false;
        }, IntPtr.Zero);
        return found;
    }

    private static string NormalizeCaption(string text) {
        return String.Join(" ", text.Split((char[])null, StringSplitOptions.RemoveEmptyEntries));
    }

    private static IntPtr FindCaptionedControl(IntPtr app, uint expectedProcess, string[] captions,
                                                params string[] classPrefixes) {
        // Caption reads must stay bounded even if Designer's UI thread stalls.
        DateTime deadline = DateTime.UtcNow.AddMilliseconds(1000);
        bool complete = true;
        IntPtr control = UniqueVisibleChild(app, expectedProcess, (window, name) => {
            if (!Array.Exists(classPrefixes, prefix => name.StartsWith(prefix, StringComparison.Ordinal))) return false;
            var text = new StringBuilder(1024);
            IntPtr length;
            if (DateTime.UtcNow >= deadline ||
                SendMessageTimeout(window, 0x000D, new IntPtr(text.Capacity), text, 2, 200, out length) == IntPtr.Zero) {
                complete = false;
                return false;
            }
            return Array.IndexOf(captions, NormalizeCaption(text.ToString())) >= 0;
        });
        return complete ? control : IntPtr.Zero;
    }

    public static IntPtr FindAppQuestionControl(IntPtr app, uint expectedProcess, string caption, bool date) {
        RequireVisibleWindow(app, expectedProcess);
        IntPtr label = FindCaptionedControl(app, expectedProcess, new[] { NormalizeCaption(caption) }, "WindowsForms10.STATIC.");
        Box labelBounds;
        if (label == IntPtr.Zero || !GetWindowRect(label, out labelBounds)) return IntPtr.Zero;
        IntPtr panel = GetParent(label);
        if (panel != app && !IsChild(app, panel)) return IntPtr.Zero;
        return UniqueVisibleChild(panel, expectedProcess, (window, name) => {
            if (!date) return name.StartsWith("WindowsForms10.EDIT.", StringComparison.Ordinal);
            Box bounds;
            if (!name.StartsWith("WindowsForms10.Window.", StringComparison.Ordinal) ||
                !GetWindowRect(window, out bounds) || bounds.Top < labelBounds.Bottom) return false;
            int height = bounds.Bottom - bounds.Top;
            if (height < 110) return false;
            double ratio = (double)(bounds.Right - bounds.Left) / height;
            return ratio > 1.06 && ratio < 1.20;
        });
    }

    public static IntPtr FindAppFinish(IntPtr app, uint expectedProcess) {
        RequireVisibleWindow(app, expectedProcess);
        return FindCaptionedControl(app, expectedProcess, new[] { "Finish", "&Finish" },
                                    "WindowsForms10.Window.", "WindowsForms10.BUTTON.");
    }

    public static string ReadAppErrorText(IntPtr dialog, uint expectedProcess) {
        RequireVisibleWindow(dialog, expectedProcess);
        DateTime deadline = DateTime.UtcNow.AddMilliseconds(1500);
        var details = new StringBuilder();
        EnumChildWindows(dialog, (child, state) => {
            if (DateTime.UtcNow >= deadline || details.Length >= 8000) return false;
            uint pid;
            GetWindowThreadProcessId(child, out pid);
            if (pid != expectedProcess || !IsWindowVisible(child)) return true;
            var name = new StringBuilder(100);
            GetClassName(child, name, name.Capacity);
            string type = name.ToString();
            if (!type.StartsWith("WindowsForms10.", StringComparison.Ordinal) &&
                !type.StartsWith("RichEdit", StringComparison.OrdinalIgnoreCase) &&
                type != "Static" && type != "Edit") return true;
            var message = new StringBuilder(4096);
            IntPtr length;
            if (SendMessageTimeout(child, 0x000D, new IntPtr(message.Capacity), message, 2, 150, out length) != IntPtr.Zero) {
                string text = message.ToString().Trim();
                if (text.Length > 0 && text != "&OK" && text != "OK" && text != "Close" && text != "&Close")
                    details.AppendLine(text);
            }
            return true;
        }, IntPtr.Zero);
        return details.ToString().Trim();
    }

    private static bool CalendarBlue(Color pixel) {
        return pixel.B >= 110 && pixel.G >= 80 && pixel.B - pixel.R >= 55 && pixel.G - pixel.R >= 30;
    }

    private static Point CalendarCell(int width, int height, int index) {
        // Designer 2025.1's painted calendar has six day rows under the weekday header.
        return new Point { X = (int)((18 + 36 * (index % 7)) * width / 257.0),
                           Y = (int)((60 + 30 * (index / 7)) * height / 227.0) };
    }

    public static string CalendarHeader(IntPtr calendar) {
        Box bounds;
        using (var image = Capture(calendar, out bounds)) {
            ulong checksum = 14695981039346656037UL;
            for (int y = image.Height / 30; y < image.Height / 10; y++)
                for (int x = image.Width / 4; x < image.Width * 3 / 4; x++)
                    checksum = unchecked((checksum ^ (uint)image.GetPixel(x, y).ToArgb()) * 1099511628211UL);
            return checksum.ToString("X16");
        }
    }

    public static int[] CalendarHighlights(IntPtr calendar, bool selectedOnly) {
        Box bounds;
        var cells = new int[42];
        int count = 0;
        using (var image = Capture(calendar, out bounds)) {
            int radiusX = Math.Max(2, image.Width / 28);
            int radiusY = Math.Max(2, image.Height / 37);
            for (int index = 0; index < 42; index++) {
                Point cell = CalendarCell(image.Width, image.Height, index);
                int blue = 0;
                for (int y = cell.Y - radiusY; y <= cell.Y + radiusY; y++)
                    for (int x = cell.X - radiusX; x <= cell.X + radiusX; x++)
                    {
                        Color pixel = image.GetPixel(x, y);
                        // Today uses a blue glyph; ordinary text produces coloured
                        // subpixel fringes which are not the calendar accent.
                        if (selectedOnly ? CalendarBlue(pixel) :
                            pixel.R <= 16 && pixel.G >= 116 && pixel.G <= 128 && pixel.B >= 195 && pixel.B <= 213)
                            blue++;
                    }
                int area = (2 * radiusX + 1) * (2 * radiusY + 1);
                if (selectedOnly ? blue > area * 3 / 5 : blue >= 3 && blue < area / 2) cells[count++] = index;
            }
        }
        Array.Resize(ref cells, count);
        return cells;
    }

    public static void ClickCalendar(IntPtr app, IntPtr calendar, uint expectedProcess, int cellOrArrow) {
        Box bounds;
        if (!IsChild(app, calendar) || !GetWindowRect(calendar, out bounds))
            throw new InvalidOperationException("Expected a calendar in the managed Designer app.");
        int width = bounds.Right - bounds.Left, height = bounds.Bottom - bounds.Top;
        Point point = cellOrArrow >= 0
            ? CalendarCell(width, height, cellOrArrow)
            : new Point { X = (int)((cellOrArrow == -1 ? 39 : 217) * width / 257.0),
                          Y = (int)(14 * height / 227.0) };
        ClickWindowPoint(app, expectedProcess, bounds.Left + point.X, bounds.Top + point.Y);
    }

    public static IntPtr FindNumericEdit(IntPtr app, uint expectedProcess) {
        IntPtr found = IntPtr.Zero;
        EnumChildWindows(app, (child, state) => {
            if (!IsNumericEdit(child, expectedProcess)) return true;
            if (found != IntPtr.Zero) {
                found = IntPtr.Zero;
                return false;
            }
            found = child;
            return true;
        }, IntPtr.Zero);
        return found;
    }

    public static void CloseModal(IntPtr dialog, uint expectedProcess) {
        uint pid;
        GetWindowThreadProcessId(dialog, out pid);
        if (pid != expectedProcess || !IsWindowEnabled(dialog) || !IsWindowVisible(dialog) ||
            !PostMessage(dialog, 0x0010, IntPtr.Zero, IntPtr.Zero))
            throw new InvalidOperationException("Cannot close the selected Designer dialog.");
    }

    private static void RequireVisibleWindow(IntPtr dialog, uint expectedProcess) {
        uint pid;
        GetWindowThreadProcessId(dialog, out pid);
        if (pid != expectedProcess || !IsWindowEnabled(dialog) || !IsWindowVisible(dialog))
            throw new InvalidOperationException("Expected a managed Designer dialog.");
    }

    public static void FocusModal(IntPtr dialog, uint expectedProcess) {
        RequireVisibleWindow(dialog, expectedProcess);
        SetForegroundWindow(dialog);
    }

    public static void ClickFocusedButton(IntPtr dialog, IntPtr button, uint expectedProcess) {
        Box bounds;
        if (!IsChild(dialog, button) || !GetWindowRect(button, out bounds) || !IsWindowEnabled(button))
            throw new InvalidOperationException("The managed app exit button is not available.");
        var point = new Point { X = (bounds.Left + bounds.Right) / 2, Y = (bounds.Top + bounds.Bottom) / 2 };
        ClickFocusedPoint(dialog, expectedProcess, point, button);
    }

    public static void OpenOptionsMenu(IntPtr root, uint expectedProcess) {
        Point point = ToolbarMenuPoint(root, 205, 46);
        ClickFocusedPoint(root, expectedProcess, point, IntPtr.Zero);
    }

    public static void ClickWindowPoint(IntPtr root, uint expectedProcess, int x, int y) {
        Box bounds;
        if (!IsWindowEnabled(root) || !GetWindowRect(root, out bounds) ||
            x < bounds.Left || x >= bounds.Right || y < bounds.Top || y >= bounds.Bottom)
            throw new InvalidOperationException("The Designer control lies outside the managed window.");
        try {
            ClickFocusedPoint(root, expectedProcess, new Point { X = x, Y = y }, IntPtr.Zero);
        } catch (InvalidOperationException) {
            Click(root, expectedProcess, x, y);
        }
    }

    private static void ClickFocusedPoint(IntPtr root, uint expectedProcess, Point point, IntPtr expectedControl) {
        FocusModal(root, expectedProcess);
        Point original;
        IntPtr target = WindowFromPoint(point);
        if (GetForegroundWindow() != root || (target != root && !IsChild(root, target)) ||
            (expectedControl != IntPtr.Zero && target != expectedControl) ||
            !GetCursorPos(out original) || !SetCursorPos(point.X, point.Y))
            throw new InvalidOperationException("The managed Designer control is obscured.");
        try {
            if (GetForegroundWindow() != root || WindowFromPoint(point) != target)
                throw new InvalidOperationException("The managed Designer window lost focus before the click.");
            mouse_event(0x0002, 0, 0, 0, UIntPtr.Zero);
            mouse_event(0x0004, 0, 0, 0, UIntPtr.Zero);
        } finally { SetCursorPos(original.X, original.Y); }
    }

    public static bool SelectFile(IntPtr dialog, uint expectedProcess, string path) {
        IntPtr editor = IntPtr.Zero, open = IntPtr.Zero;
        EnumChildWindows(dialog, (child, state) => {
            uint pid;
            GetWindowThreadProcessId(child, out pid);
            if (pid != expectedProcess || !IsWindowVisible(child)) return true;
            var name = new StringBuilder(80);
            GetClassName(child, name, name.Capacity);
            int id = GetDlgCtrlID(child);
            if (id == 1148 && name.ToString() == "Edit") editor = child;
            if (id == 1 && name.ToString() == "Button") open = child;
            return true;
        }, IntPtr.Zero);
        if (editor == IntPtr.Zero || open == IntPtr.Zero || !IsWindowEnabled(open)) return false;
        IntPtr result;
        if (SendMessageTimeout(editor, 0x000C, IntPtr.Zero, path, 2, 3000, out result) == IntPtr.Zero)
            throw new InvalidOperationException("Designer file picker rejected the filename.");
        ClickControl(open, expectedProcess);
        return true;
    }

    public static void CloseOnlyTab(IntPtr root, uint expectedProcess) {
        if (!IsWindowEnabled(root)) throw new InvalidOperationException("Designer has an open dialog.");
        Box window;
        Point match = new Point();
        int matches = 0;
        string[] cross = {"#....#", ".#..#.", "..##..", "..##..", ".#..#.", "#....#"};
        using (var image = Capture(root, out window)) {
            for (int y = 120; y < Math.Min(image.Height - 6, 206); y++)
                for (int x = 190; x < Math.Min(image.Width - 6, 1250); x++) {
                    bool matchesCross = true;
                    for (int row = 0; row < 6 && matchesCross; row++)
                        for (int col = 0; col < 6; col++) {
                            Color c = image.GetPixel(x + col, y + row);
                            bool blueGray = c.R < 200 && c.B - c.R >= 35 && c.G - c.R >= 12;
                            if (blueGray != (cross[row][col] == '#')) { matchesCross = false; break; }
                        }
                    if (matchesCross && x >= 2 && x + 8 < image.Width &&
                        image.GetPixel(x - 2, y - 2).ToArgb() == Color.White.ToArgb() &&
                        image.GetPixel(x + 8, y + 7).ToArgb() == Color.White.ToArgb()) {
                        match = new Point { X = x + 3, Y = y + 3 }; matches++;
                    }
                }
        }
        if (matches != 1) throw new InvalidOperationException("Could not uniquely identify the workflow tab close button.");
        Click(root, expectedProcess, window.Left + match.X, window.Top + match.Y);
    }

    private static void Click(IntPtr root, uint expectedProcess, int x, int y) {
        IntPtr target = IntPtr.Zero;
        EnumChildWindows(root, (child, state) => {
            Box bounds;
            uint pid;
            GetWindowThreadProcessId(child, out pid);
            if (pid == expectedProcess && IsWindowVisible(child) && IsWindowEnabled(child) &&
                GetWindowRect(child, out bounds) && x >= bounds.Left && x < bounds.Right &&
                y >= bounds.Top && y < bounds.Bottom) target = child;
            return true;
        }, IntPtr.Zero);
        var point = new Point { X = x, Y = y };
        if (target == IntPtr.Zero) {
            uint pid;
            GetWindowThreadProcessId(root, out pid);
            if (pid == expectedProcess) target = root;
        }
        if (target == IntPtr.Zero || !ScreenToClient(target, ref point))
            throw new InvalidOperationException("Click did not resolve to the expected Designer window.");
        var position = new IntPtr(((point.Y & 65535) << 16) | (point.X & 65535));
        if (!PostMessage(target, 0x200, IntPtr.Zero, position) ||
            !PostMessage(target, 0x201, new IntPtr(1), position) ||
            !PostMessage(target, 0x202, IntPtr.Zero, position))
            throw new InvalidOperationException("Designer rejected the mouse messages.");
    }
}
'@
[void][DesignerMouse]::SetProcessDPIAware()

function Test-Designer2025_1([string]$Path) {
    if (-not $Path -or [IO.Path]::GetFileName($Path) -ne 'AlteryxGui.exe') { return $false }
    $file = Get-Item -LiteralPath $Path -ErrorAction SilentlyContinue
    return $null -ne $file -and $file.VersionInfo.ProductVersion -match '^(?:20)?25\.1(?:\.|$)'
}

function Resolve-DesignerExecutable {
    if ($DesignerLauncher) {
        if (-not (Test-Designer2025_1 $DesignerLauncher)) {
            throw "DesignerLauncher must point to the Designer 2025.1 AlteryxGui.exe: $DesignerLauncher"
        }
        return (Resolve-Path -LiteralPath $DesignerLauncher).Path
    }
    $candidates = @(
        foreach ($root in @($env:APPDATA, $env:ProgramData)) {
            $installInfo = Join-Path $root 'Alteryx/Engine/2025.1/InstallInfo.xml'
            if (Test-Path -LiteralPath $installInfo -PathType Leaf) {
                [xml]$install = Get-Content -LiteralPath $installInfo -Raw
                if ($install.Settings.InstallDir64) {
                    Join-Path ([string]$install.Settings.InstallDir64) 'AlteryxGui.exe'
                }
            }
        }
        Join-Path $env:ProgramFiles 'Alteryx/bin/AlteryxGui.exe'
        Join-Path $env:LOCALAPPDATA 'Alteryx/bin/AlteryxGui.exe'
    )
    foreach ($path in $candidates) {
        if (Test-Designer2025_1 $path) { return (Resolve-Path -LiteralPath $path).Path }
    }
    throw 'Designer 2025.1 was not found. Pass -DesignerLauncher with the full path to its AlteryxGui.exe.'
}

function Get-PreparedCase($Entry) {
    $folder = (Resolve-Path -LiteralPath $Entry.run_dir).Path
    $manifest = Get-Content -LiteralPath (Join-Path $folder 'manifest.json') -Raw | ConvertFrom-Json -AsHashtable
    $filename = $manifest.instrumented_file
    if (-not $filename) { $filename = 'instrumented.yxmd' }
    $path = Join-Path $folder $filename
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    if ($hash -ne $manifest.instrumented_sha256) { throw "Prepared workflow hash changed: $path" }
    if ($manifest.source_probe_hashes) {
        foreach ($source in $manifest.source_probe_hashes.GetEnumerator()) {
            $inputPath = Join-Path (Split-Path -Parent $folder) $source.Key
            if ((Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash -ne $source.Value) {
                throw "AMP probe input changed: $inputPath"
            }
        }
    }
    foreach ($dependency in $manifest.macro_dependencies_sha256.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $dependency.Key -PathType Leaf)) {
            throw "Missing macro dependency: $($dependency.Key)"
        }
        $macroHash = (Get-FileHash -LiteralPath $dependency.Key -Algorithm SHA256).Hash
        if ($macroHash -ne $dependency.Value) { throw "Macro dependency changed: $($dependency.Key)" }
        [xml]$macro = Get-Content -LiteralPath $dependency.Key -Raw
        if ($macro.DocumentElement.Name -ne 'AlteryxDocument' -or
            -not $macro.DocumentElement.GetAttribute('yxmdVer')) {
            throw "Macro is missing a Designer document version: $($dependency.Key)"
        }
        $topQuestions = $macro.SelectNodes('/AlteryxDocument/Properties/RuntimeProperties/Questions/Question')
        if (@($topQuestions | Where-Object { $_.SelectSingleNode('Type').InnerText -ne 'Tab' }).Count) {
            throw "Designer requires every top-level macro question to be a Tab: $($dependency.Key)"
        }
    }
    $artifacts = @($manifest.probes | ForEach-Object { Join-Path $folder $_.file })
    if ($manifest.sink_files) {
        $artifacts += @($manifest.sink_files.Values | ForEach-Object { Join-Path $folder $_ })
    }
    $renderFolders = @()
    if ($manifest.Contains('render_folders')) {
        $renderFolders = @($manifest.render_folders.Values | ForEach-Object { Join-Path $folder $_ })
    }
    $app = $filename.EndsWith('.yxwz')
    $numeric = $null
    $answers = @()
    $questionCount = 0
    if ($app) {
        [xml]$workflow = Get-Content -LiteralPath $path -Raw
        $questions = @($workflow.SelectNodes('/AlteryxDocument/Properties/RuntimeProperties/Questions//Question[Type != "Tab"]'))
        $questionCount = $questions.Count
        $answers = @(
            foreach ($question in $questions) {
                $kind = $question.SelectSingleNode('Type').InnerText
                if ($kind -notin @('Date', 'TextBox', 'QuestionTextBox', 'FolderBrowse', 'FileBrowse', 'QuestionFileBrowse')) { continue }
                $key = $question.SelectSingleNode('Name').InnerText
                if (-not $manifest.answers -or -not $manifest.answers.Contains($key)) { continue }
                $description = $question.SelectSingleNode('Description')
                $label = if ($description -and $description.InnerText) { $description.InnerText } else { $key }
                $value = [string]$manifest.answers[$key]
                if ($kind -eq 'Date') {
                    [void][datetime]::ParseExact($value, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
                }
                @{ name = $key; label = $label; kind = $kind; value = $value }
            }
        )
        if ($questions.Count -eq 1 -and $questions[0].SelectSingleNode('Type').InnerText -eq 'NumericUpDown') {
            $question = $questions[0]
            $key = $question.SelectSingleNode('Name').InnerText
            $default = $question.SelectSingleNode('Default').GetAttribute('value')
            $value = if (-not $manifest.answers -or $manifest.answers.Count -eq 0) {
                $default
            } elseif ($manifest.answers.Count -eq 1 -and $manifest.answers.Contains($key)) {
                $manifest.answers[$key]
            }
            $min = $question.SelectSingleNode('Minimum').GetAttribute('value')
            $max = $question.SelectSingleNode('Maximum').GetAttribute('value')
            if ($value -match '^-?[0-9]+$' -and [decimal]$value -ge [decimal]$min -and [decimal]$value -le [decimal]$max) {
                $numeric = @{ value = [string]$value }
            }
        }
    }
    @{
        path = $path; artifacts = $artifacts; renderFolders = $renderFolders; app = $app
        numeric = $numeric; answers = $answers; questionCount = $questionCount; folder = $folder
    }
}

function Close-OneRegistration([int]$ProcessId, [IntPtr]$MainWindow) {
    if (-not $ProcessId) { return }
    $dialog = [DesignerMouse]::FindOneRegistration($MainWindow, $ProcessId)
    if ($dialog -eq [IntPtr]::Zero) { return }
    [DesignerMouse]::CloseModal($dialog, $ProcessId)
    $limit = [DateTime]::UtcNow.AddSeconds(4)
    do {
        if (-not [DesignerMouse]::IsWindowVisible($dialog)) {
            $script:dismissedOne++
            return
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $limit)
    throw 'Designer did not close its Alteryx One registration window.'
}

function Wait-For([scriptblock]$Condition, [int]$Seconds) {
    $limit = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        if ($script:sessionId) { Close-OneRegistration $script:sessionId $script:sessionHandle }
        $result = & $Condition
        if ($result) { return $result }
        Start-Sleep -Milliseconds 350
    } while ([DateTime]::UtcNow -lt $limit)
}

function Get-SessionWindow {
    # Windows may temporarily report a modal dialog as the process's main window.
    @{ MainWindowTitle = [DesignerMouse]::WindowTitle($script:sessionHandle, $script:sessionId) }
}

function Select-DesignerCandidate($Candidates) {
    $candidates = @($Candidates | Where-Object { $_.ready })
    if ($candidates.Count -eq 1) { return $candidates[0] }
    $blank = @($candidates | Where-Object { $_.blank })
    if ($blank.Count -eq 1) { return $blank[0] }
    if ($candidates.Count -gt 1) {
        throw "Multiple Designer windows are available (PIDs $($candidates.id -join ', ')). Use -DesignerProcessId to select one."
    }
}

function Connect-DesignerSession {
    if ($script:sessionId) { return }
    Set-DesignerStage 'detect an existing Designer session'
    $windowsSession = (Get-Process -Id $PID).SessionId
    if ($DesignerProcessId) {
        $processes = @(Get-Process -Id $DesignerProcessId -ErrorAction SilentlyContinue)
    } else {
        $processes = @(Get-Process -Name AlteryxGui -ErrorAction SilentlyContinue)
    }
    $executable = if ($DesignerLauncher) { Resolve-DesignerExecutable }
    $compatible = @($processes | Where-Object {
        $_.SessionId -eq $windowsSession -and $_.ProcessName -eq 'AlteryxGui' -and
            (Test-Designer2025_1 $_.Path) -and (-not $executable -or $_.Path -eq $executable)
    })
    if (-not $compatible.Count) {
        if ($DesignerProcessId) { throw "Designer PID $DesignerProcessId is unavailable or incompatible in this Windows session." }
        Start-DesignerSession
        return
    }
    $candidates = @(
        foreach ($process in $compatible) {
            $handle = $process.MainWindowHandle
            $title = $process.MainWindowTitle
            $blank = $title -match '^Alteryx Designer.* - New Workflow\d+$'
            $ready = $handle -ne 0 -and $title -match '^Alteryx Designer(?: x64)?(?: - .+)?$' -and
                -not [DesignerMouse]::IsHungAppWindow($handle) -and
                -not @([DesignerMouse]::VisibleMenus($process.Id)).Count -and
                ([DesignerMouse]::IsWindowEnabled($handle) -or
                    [DesignerMouse]::FindOneRegistration($handle, $process.Id) -ne [IntPtr]::Zero)
            @{ id = $process.Id; handle = $handle; ready = $ready; blank = $blank }
        }
    )
    $selected = Select-DesignerCandidate $candidates
    if (-not $selected) {
        throw "Existing Designer session unavailable (PIDs $($compatible.Id -join ', ')). Check its window, dialogs or running workflows."
    }
    $script:sessionId = $selected.id
    $script:sessionHandle = $selected.handle
    $script:sessionMode = 'reused'
    Set-DesignerStage "reuse Designer PID $script:sessionId"
    Close-OneRegistration $script:sessionId $script:sessionHandle
    if (-not [DesignerMouse]::IsWindowEnabled($script:sessionHandle) -or (Get-SessionDialog)) {
        throw "Designer PID $script:sessionId has an open dialog."
    }
}

function Get-SessionDialog {
    $popup = [DesignerMouse]::GetLastActivePopup($script:sessionHandle)
    if ($popup -ne 0 -and $popup -ne $script:sessionHandle) {
        $dialog = [System.Windows.Automation.AutomationElement]::FromHandle($popup)
        if ($dialog.Current.ProcessId -eq $script:sessionId -and $dialog.Current.IsEnabled -and
            -not $dialog.Current.IsOffscreen) { return $dialog }
    }
    if ([DesignerMouse]::IsWindowEnabled($script:sessionHandle)) { return }
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty, [int]$script:sessionId)
    $dialogs = @([System.Windows.Automation.AutomationElement]::RootElement.FindAll(
        [System.Windows.Automation.TreeScope]::Children, $condition
    ) | Where-Object {
        $_.Current.NativeWindowHandle -ne $script:sessionHandle -and $_.Current.IsEnabled -and
        -not $_.Current.IsOffscreen -and $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Window
    })
    if ($dialogs.Count -eq 1) { $dialogs[0] }
}

function Find-EnabledDialogControls($Dialog, [string[]]$Names) {
    foreach ($name in $Names) {
        $condition = [System.Windows.Automation.AndCondition]::new(
            [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::NameProperty, $name),
            [System.Windows.Automation.PropertyCondition]::new(
                [System.Windows.Automation.AutomationElement]::IsEnabledProperty, $true)
        )
        $Dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition)
    }
}

function Invoke-DialogButton($Dialog, [string[]]$Names) {
    $buttons = @(Find-EnabledDialogControls $Dialog $Names)
    if ($buttons.Count -ne 1) { throw 'Expected dialog button could not be identified.' }
    $control = $buttons[0]
    if ($control.Current.NativeWindowHandle) {
        [DesignerMouse]::ClickControl([IntPtr]$control.Current.NativeWindowHandle, $script:sessionId)
    } else {
        $control.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
    }
}

function Find-DesignerRunButton {
    if (-not [DesignerMouse]::IsWindowEnabled($script:sessionHandle)) { return }
    $window = [System.Windows.Automation.AutomationElement]::FromHandle($script:sessionHandle)
    $id = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, 'btnRun')
    $buttons = @($window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $id) |
        Where-Object { $_.Current.IsEnabled -and -not $_.Current.IsOffscreen })
    if (-not $buttons.Count) {
        $buttons = @(Find-EnabledDialogControls $window @('btnRun') | Where-Object { -not $_.Current.IsOffscreen })
    }
    if ($buttons.Count -eq 1) { $buttons[0] }
}

function Click-DesignerToolbarButton($Button) {
    $bounds = $Button.Current.BoundingRectangle
    if ($bounds.IsEmpty) { throw 'The Designer toolbar button has no screen position.' }
    [DesignerMouse]::ClickWindowPoint(
        $script:sessionHandle, $script:sessionId, [int]($bounds.X + $bounds.Width / 2),
        [int]($bounds.Y + $bounds.Height / 2))
}

function Close-ManagedWorkflow([string]$Filename) {
    # Leave all tabs in a borrowed window in place, including the test copy.
    if ($script:sessionMode -eq 'reused') { return }
    Set-DesignerStage "close managed tab $Filename"
    if (-not (Get-SessionWindow).MainWindowTitle.EndsWith($Filename, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The current tab is no longer the workflow opened by the script.'
    }
    [DesignerMouse]::CloseOnlyTab($script:sessionHandle, $script:sessionId)
    $closed = Wait-For {
        $dialog = Get-SessionDialog
        if ($dialog) {
            $names = @($dialog.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition
            ) | ForEach-Object { $_.Current.Name })
            if ($dialog.Current.Name -ne 'Save Files' -or ($names -join ' ') -notmatch [regex]::Escape($Filename)) {
                throw "Unexpected dialog while closing $Filename."
            }
            Invoke-DialogButton $dialog @("Don't Save", "Don't save", 'No', '&No')
            return
        }
        if (-not (Get-SessionWindow).MainWindowTitle.EndsWith($Filename, [StringComparison]::OrdinalIgnoreCase)) { $true }
    } ([Math]::Min(15, $TimeoutSeconds))
    if (-not $closed) { throw "Timed out closing the run tab: $Filename" }
}

function Start-DesignerSession {
    $script:sessionMode = 'launched'
    Set-DesignerStage 'start Designer and wait for its window' 30
    $executable = Resolve-DesignerExecutable
    $started = Start-Process -FilePath $executable -WindowStyle Normal -PassThru
    $script:sessionId = $started.Id
    Set-DesignerStage "wait for Designer PID $script:sessionId" 30
    $target = Wait-For {
        $process = Get-Process -Id $started.Id -ErrorAction SilentlyContinue
        if (-not $process) { throw "Designer exited before opening its window (PID $($started.Id))." }
        if ($process -and $process.MainWindowHandle -ne 0 -and
            $process.MainWindowTitle -match '^Alteryx Designer.* - New Workflow\d+$') {
            $process
        }
    } ([Math]::Min(28, $TimeoutSeconds))
    if (-not $target) { throw "Timed out waiting for the new Designer 2025.1 window (PID $($started.Id))." }
    $script:sessionId = $target.Id
    $script:sessionHandle = $target.MainWindowHandle
}

function Open-WorkflowFilePicker {
    # Ctrl+O is Designer's Open Workflow command. Wait for asynchronous activation
    # and verify the target again before sending keys from the automation worker.
    $shortcutSent = Wait-For {
        [DesignerMouse]::TryShortcut($script:sessionHandle, $script:sessionId, 0x4F)
    } 2
    if (-not $shortcutSent) {
        Write-Host 'Designer: bring the existing window forward through its title bar'
        [DesignerMouse]::RaiseForActivation($script:sessionHandle, $script:sessionId)
        [void](Wait-For {
            [DesignerMouse]::TryActivateCaption($script:sessionHandle, $script:sessionId)
        } 2)
        $shortcutSent = Wait-For {
            [DesignerMouse]::TryShortcut($script:sessionHandle, $script:sessionId, 0x4F)
        } 3
    }
    if (-not $shortcutSent) {
        throw "Could not activate Designer PID $script:sessionId for Ctrl+O. Check that its window is available on this desktop."
    }
    $file = Wait-For {
        $file = [DesignerMouse]::FindDialog($script:sessionId, 'Alteryx - Open File')
        if ($file -ne [IntPtr]::Zero) { return $file }
    } 6
    if (-not $file) {
        $dialog = Get-SessionDialog
        if ($dialog -and $dialog.Current.Name -ne 'Alteryx - Open File') {
            throw "Designer opened '$($dialog.Current.Name)' instead of the file picker."
        }
    }
    $file
}

function Get-WorkflowOpeningDialog {
    try {
        $dialog = Get-SessionDialog
        if (-not $dialog) { return }
        if (-not [DesignerMouse]::IsWindowEnabled($script:sessionHandle)) { return $dialog }
        $pattern = $null
        if ($dialog.TryGetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern, [ref]$pattern) -and
            $pattern.Current.IsModal) { return $dialog }
    }
    catch [System.Windows.Automation.ElementNotAvailableException] {
        # The popup disappeared while Designer was loading the workflow.
    }
}

function Open-WorkflowInSession([string]$Path) {
    $name = [IO.Path]::GetFileName($Path)
    Set-DesignerStage "open $name in Designer" 30
    Close-OneRegistration $script:sessionId $script:sessionHandle
    $active = (Get-SessionWindow).MainWindowTitle
    if ($active.EndsWith($name, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Designer already has a tab named $name selected. Switch tabs before running this case."
    }
    if ([DesignerMouse]::IsIconic($script:sessionHandle)) {
        [DesignerMouse]::Restore($script:sessionHandle, $script:sessionId)
        if (-not (Wait-For { -not [DesignerMouse]::IsIconic($script:sessionHandle) } 5)) {
            throw 'The selected Designer window stayed minimized.'
        }
    }
    if (@([DesignerMouse]::VisibleMenus($script:sessionId)).Count) {
        throw 'Close the open Designer menu before starting the batch.'
    }
    Set-DesignerStage 'activate Designer and open the workflow file picker' 15
    $file = Open-WorkflowFilePicker
    if (-not $file) { throw 'Designer did not open Alteryx - Open File after Ctrl+O.' }
    Set-DesignerStage "select and load $name in Designer" 25
    $selected = Wait-For {
        [DesignerMouse]::SelectFile($file, $script:sessionId, $Path)
    } 10
    if (-not $selected) { throw 'Designer file picker did not expose its filename and Open controls.' }
    $seen = @{ handle = 0; since = [DateTime]::MinValue }
    $loaded = Wait-For {
        $process = Get-SessionWindow
        $popup = Get-WorkflowOpeningDialog
        if ($popup -and $popup.Current.Name -eq 'Update Missing Macros') {
            $messages = @($popup.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition
            ) | ForEach-Object { $_.Current.Name } | Where-Object { $_ -match 'missing|inaccessible|\.yxmc' })
            throw ('Designer rejected macro dependencies: ' + ($messages -join ' '))
        }
        if ($popup -and $popup.Current.Name -ne 'Alteryx - Open File') {
            try {
                $handle = $popup.Current.NativeWindowHandle
                if ($seen.handle -ne $handle) {
                    $seen.handle = $handle
                    $seen.since = [DateTime]::UtcNow
                }
                if (([DateTime]::UtcNow - $seen.since).TotalMilliseconds -lt 1000) { return }
                $title = $popup.Current.Name
                $class = $popup.Current.ClassName
                $message = @($popup.FindAll(
                    [System.Windows.Automation.TreeScope]::Descendants,
                    [System.Windows.Automation.Condition]::TrueCondition
                ) | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text } |
                    ForEach-Object { $_.Current.Name })
            }
            catch [System.Windows.Automation.ElementNotAvailableException] {
                $seen.handle = 0
                return
            }
            $detail = "Designer dialog while opening ${name}: [$class] $title $($message -join ' ')"
            $capture = Join-Path (Split-Path -Parent $Path) "designer-open-dialog-$([guid]::NewGuid().ToString('N')).png"
            try {
                [DesignerMouse]::Save([IntPtr]$handle, $capture)
                $detail += " Screenshot: $capture"
            }
            catch { Write-Host "Designer dialog screenshot unavailable: $($_.Exception.Message)" }
            throw $detail
        }
        $seen.handle = 0
        if ($process.MainWindowTitle.EndsWith($name, [StringComparison]::OrdinalIgnoreCase) -and
            -not $popup) { $true }
    } $TimeoutSeconds
    if (-not $loaded) { throw "Timed out opening $name in Designer PID $script:sessionId." }
}

function Wait-ForNamedDialog([string]$Name, [int]$Seconds = [Math]::Min(45, $TimeoutSeconds)) {
    $handle = Wait-For {
        $candidate = [DesignerMouse]::FindDialog($script:sessionId, $Name)
        if ($candidate -ne [IntPtr]::Zero) { $candidate }
    } $Seconds
    if (-not $handle) { throw "Designer did not open $Name." }
    $handle
}

function Open-AppFromOptions($Case) {
    Set-DesignerStage 'open the prepared Analytic App through Options' 30
    if (-not $script:sessionId) { throw 'Select an existing Designer 2025.1 session to run an analytic app.' }
    Close-OneRegistration $script:sessionId $script:sessionHandle
    [void](Get-SessionWindow)
    if ([DesignerMouse]::IsIconic($script:sessionHandle)) {
        [DesignerMouse]::Restore($script:sessionHandle, $script:sessionId)
        if (-not (Wait-For { -not [DesignerMouse]::IsIconic($script:sessionHandle) } 5)) {
            throw 'The selected Designer window stayed minimized.'
        }
    }
    if ((Get-SessionDialog) -or @([DesignerMouse]::VisibleMenus($script:sessionId)).Count) {
        throw 'An open Designer menu or dialog prevents app automation.'
    }
    # Designer 2025.1 light-theme Options menu, Run Analytic Apps.
    try { [DesignerMouse]::OpenOptionsMenu($script:sessionHandle, $script:sessionId) }
    catch { [DesignerMouse]::ClickMenuItem($script:sessionHandle, $script:sessionId, 205, 46) }
    $options = Wait-For {
        $menus = @([DesignerMouse]::VisibleMenus($script:sessionId))
        if ($menus.Count -eq 1) { $menus[0] }
    } ([Math]::Min(20, $TimeoutSeconds))
    if (-not $options) { throw 'Designer did not open its Options menu.' }
    [DesignerMouse]::ClickMenuItem($options, $script:sessionId, 81, 107)
    $choose = [System.Windows.Automation.AutomationElement]::FromHandle((Wait-ForNamedDialog 'Choose Analytic App'))
    Invoke-DialogButton $choose @('External File')
    $browseEnabled = Wait-For { Find-EnabledDialogControls $choose @('Browse') } 6
    if (-not $browseEnabled) { throw 'Designer did not enable the external app Browse button.' }
    Invoke-DialogButton $choose @('Browse')
    $file = Wait-ForNamedDialog 'Alteryx - Open File'
    $selected = Wait-For { [DesignerMouse]::SelectFile($file, $script:sessionId, $Case.path) } 10
    if (-not $selected) { throw 'Designer did not select the prepared app.' }
    $choose = [System.Windows.Automation.AutomationElement]::FromHandle((Wait-ForNamedDialog 'Choose Analytic App'))
    Invoke-DialogButton $choose @('Run')
}

function Invoke-DesignerWandProbe([scriptblock]$Probe, [IntPtr]$Window, [int]$ProcessId,
                                  [int]$Milliseconds = 4000) {
    # FindAll can block inside the UI Automation provider. The probe cannot click or launch an app.
    $command = "`$ErrorActionPreference = 'Stop'`n& { $Probe } $($Window.ToInt64()) $ProcessId"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($command))
    $start = [Diagnostics.ProcessStartInfo]::new((Get-Process -Id $PID).Path)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    foreach ($argument in @('-NoProfile', '-NonInteractive', '-EncodedCommand', $encoded)) {
        $start.ArgumentList.Add($argument)
    }
    $probeProcess = [Diagnostics.Process]::Start($start)
    try {
        $stdout = $probeProcess.StandardOutput.ReadToEndAsync()
        [void]$probeProcess.StandardError.ReadToEndAsync()
        if (-not $probeProcess.WaitForExit($Milliseconds)) {
            Write-Host 'Designer: magic-wand lookup timed out'
            return
        }
        if ($probeProcess.ExitCode -ne 0) {
            Write-Host 'Designer: magic-wand lookup could not query the toolbar'
            return
        }
        $output = $stdout.GetAwaiter().GetResult().Trim()
        if ($output) { ConvertFrom-Json -InputObject $output }
    } finally {
        if (-not $probeProcess.HasExited) {
            try { $probeProcess.Kill() }
            catch [InvalidOperationException] { if (-not $probeProcess.HasExited) { throw } }
        }
        $probeProcess.Dispose()
    }
}

function Find-DesignerAppWand {
    Invoke-DesignerWandProbe {
        param([long]$WindowHandle, [int]$ExpectedProcess)
        Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,WindowsBase
        $element = [System.Windows.Automation.AutomationElement]
        $window = $element::FromHandle([IntPtr]$WindowHandle)
        if ($window.Current.ProcessId -ne $ExpectedProcess) { return }
        $selector = [System.Windows.Automation.OrCondition]::new(
            [System.Windows.Automation.PropertyCondition]::new($element::AutomationIdProperty, 'btnRunApp'),
            [System.Windows.Automation.PropertyCondition]::new($element::NameProperty, 'btnRunApp'),
            [System.Windows.Automation.PropertyCondition]::new($element::NameProperty, 'Run as Analytic App')
        )
        $buttons = @($window.FindAll([System.Windows.Automation.TreeScope]::Descendants, $selector) |
            Where-Object { $_.Current.ProcessId -eq $ExpectedProcess -and $_.Current.IsEnabled -and
                -not $_.Current.IsOffscreen -and $_.Current.ControlType -ne [System.Windows.Automation.ControlType]::Text })
        if ($buttons.Count -ne 1) { return }
        $bounds = $buttons[0].Current.BoundingRectangle
        if ($bounds.IsEmpty) { return }
        @{ x = [int]($bounds.X + $bounds.Width / 2); y = [int]($bounds.Y + $bounds.Height / 2) } |
            ConvertTo-Json -Compress
    } $script:sessionHandle $script:sessionId
}

function Open-AppFromWand($Case) {
    $previousTitle = (Get-SessionWindow).MainWindowTitle
    try {
        Open-WorkflowInSession $Case.path
    } catch {
        if ($AppLaunch -ne 'auto' -or $_.Exception.Message -ne 'Designer did not open Alteryx - Open File after Ctrl+O.' -or
            (Get-SessionWindow).MainWindowTitle -ne $previousTitle -or
            (Get-SessionDialog) -or @([DesignerMouse]::VisibleMenus($script:sessionId)).Count) {
            throw
        }
        return $false
    }
    Set-DesignerStage 'locate Run as Analytic App'
    $point = Find-DesignerAppWand
    if (-not (Get-SessionWindow).MainWindowTitle.EndsWith(
        [IO.Path]::GetFileName($Case.path), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The active Designer tab changed while locating the Analytic App button.'
    }
    if (-not $point) { return $false }
    Set-DesignerStage 'click Run as Analytic App'
    [DesignerMouse]::ClickWindowPoint($script:sessionHandle, $script:sessionId, $point.x, $point.y)
    return $true
}

function Get-CalendarCell([datetime]$Date) {
    $first = $Date.AddDays(1 - $Date.Day)
    $offset = [int]$first.DayOfWeek
    # The control always draws preceding-month days in its first row.
    if ($offset -eq 0) { $offset = 7 }
    return $offset + $Date.Day - 1
}

function Set-AppDate([IntPtr]$AppHandle, [IntPtr]$Calendar, [datetime]$Expected) {
    $targetDate = $Expected.ToString('yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
    Set-DesignerStage "read the calendar month for $targetDate"
    $today = [DateTime]::Today
    $anchor = @([DesignerMouse]::CalendarHighlights($Calendar, $false))
    if ($anchor.Count -ne 1 -or $anchor[0] -ne (Get-CalendarCell $today)) {
        throw 'Designer calendar could not be anchored to its initial today marker.'
    }
    $monthOffset = ($Expected.Year - $today.Year) * 12 + $Expected.Month - $today.Month
    $arrow = if ($monthOffset -lt 0) { -1 } else { -2 }
    $headers = [System.Collections.Generic.HashSet[string]]::new()
    [void]$headers.Add([DesignerMouse]::CalendarHeader($Calendar))
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    for ($move = 0; $move -lt [Math]::Abs($monthOffset); $move++) {
        if ([DateTime]::UtcNow -ge $deadline) { throw 'Designer calendar month navigation timed out.' }
        $month = $today.AddMonths(($move + 1) * [Math]::Sign($monthOffset)).ToString(
            'yyyy-MM', [Globalization.CultureInfo]::InvariantCulture)
        Set-DesignerStage "navigate calendar to $month" 8
        [DesignerMouse]::ClickCalendar($AppHandle, $Calendar, $script:sessionId, $arrow)
        $changed = Wait-For {
            $header = [DesignerMouse]::CalendarHeader($Calendar)
            if (-not $headers.Contains($header)) { $header }
        } 3
        if (-not $changed) { throw 'Designer calendar did not change to the adjacent month.' }
        [void]$headers.Add($changed)
    }
    Set-DesignerStage "select and verify calendar day $targetDate" 8
    Close-OneRegistration $script:sessionId $script:sessionHandle
    $cell = Get-CalendarCell $Expected
    [DesignerMouse]::ClickCalendar($AppHandle, $Calendar, $script:sessionId, $cell)
    $selected = Wait-For {
        $cells = @([DesignerMouse]::CalendarHighlights($Calendar, $true))
        if ($cells.Count -eq 1 -and $cells[0] -eq $cell) { $true }
    } 4
    if (-not $selected) { throw "Designer did not select date $targetDate." }
}

function Run-AnalyticApp($Case) {
    $usedWand = $false
    if ($AppLaunch -ne 'options') {
        $usedWand = Open-AppFromWand $Case
        if (-not $usedWand -and $AppLaunch -eq 'wand') { throw 'Designer did not expose a unique Run as Analytic App button.' }
    }
    $appName = 'Alteryx Designer x64 Analytic App - ' + [IO.Path]::GetFileNameWithoutExtension($Case.path)
    if ($usedWand) {
        Set-DesignerStage 'wait for the Analytic App questions'
        try { $appHandle = Wait-ForNamedDialog $appName ([Math]::Min(12, $TimeoutSeconds)) }
        catch {
            if ($AppLaunch -ne 'auto' -or (Get-SessionDialog) -or
                -not [DesignerMouse]::IsWindowEnabled($script:sessionHandle)) { throw }
            Close-ManagedWorkflow ([IO.Path]::GetFileName($Case.path))
            $usedWand = $false
        }
    }
    if (-not $usedWand) {
        if ($AppLaunch -eq 'auto') { Write-Host 'Designer: continue through Options > Run Analytic Apps' }
        Open-AppFromOptions $Case
        Set-DesignerStage 'wait for the Analytic App questions'
        $appHandle = Wait-ForNamedDialog $appName
    }
    Set-DesignerStage 'inspect the Analytic App questions'
    $verifiedAnswers = @{}
    $answerReview = 'operator'
    $finish = $false
    if ($Case.numeric) {
        Set-DesignerStage 'enter and verify the numeric App answer' 35
        $editHandle = Wait-For {
            $candidate = [DesignerMouse]::FindNumericEdit($appHandle, $script:sessionId)
            if ($candidate -ne [IntPtr]::Zero) { $candidate }
        } ([Math]::Min(30, $TimeoutSeconds))
        if (-not $editHandle) { throw 'Expected exactly one editable numeric answer.' }
        $expected = [decimal]$Case.numeric.value
        if (-not [DesignerMouse]::NumericEditMatches($editHandle, $script:sessionId, $expected)) {
            [DesignerMouse]::SetNumericEdit($editHandle, $script:sessionId, $Case.numeric.value)
        }
        $verified = Wait-For { [DesignerMouse]::NumericEditMatches($editHandle, $script:sessionId, $expected) } 8
        [DesignerMouse]::Save($appHandle, (Join-Path $Case.folder 'designer-app-answer.png'))
        if (-not $verified) {
            $observed = [DesignerMouse]::ReadNumericEdit($editHandle, $script:sessionId)
            [DesignerMouse]::CloseModal($appHandle, $script:sessionId)
            throw "Designer numeric answer differs from the prepared value (expected $expected, observed '$observed')."
        }
        $finish = $true
        $answerReview = 'numeric_readback'
    } elseif ($Case.answers.Count) {
        foreach ($answer in $Case.answers) {
            Set-DesignerStage "locate App control for '$($answer.name)'" 10
            $control = Wait-For {
                $candidate = [DesignerMouse]::FindAppQuestionControl(
                    $appHandle, $script:sessionId, $answer.label, $answer.kind -eq 'Date')
                if ($candidate -ne [IntPtr]::Zero) { $candidate }
            } 6
            if (-not $control) { throw "Designer could not match the app control for '$($answer.name)'." }
            if ($answer.kind -eq 'Date') {
                $date = [datetime]::ParseExact($answer.value, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
                Set-AppDate $appHandle $control $date
            } else {
                Set-DesignerStage "enter and verify App answer '$($answer.name)'"
                if ([DesignerMouse]::ReadNumericEdit($control, $script:sessionId) -cne $answer.value) {
                    [DesignerMouse]::SetTextEdit($control, $script:sessionId, $answer.value)
                }
                if ([DesignerMouse]::ReadNumericEdit($control, $script:sessionId) -cne $answer.value) {
                    throw "Designer did not confirm the prepared answer for '$($answer.name)'."
                }
            }
            $verifiedAnswers[$answer.name] = $answer.value
        }
        $finish = $verifiedAnswers.Count -eq $Case.questionCount
        $answerReview = if ($finish) { 'verified_controls' } else { 'operator_with_verified_controls' }
    }
    if (-not $finish) {
        if (-not $ManualAppInputs) { throw 'The app contains questions requiring operator input.' }
        Write-Host "Review the prepared answers in Designer, then click Finish. Case directory: $($Case.folder)"
    }
    Set-DesignerStage 'capture the Analytic App answers'
    [DesignerMouse]::Save($appHandle, (Join-Path $Case.folder 'designer-app-answer.png'))
    if ($finish) {
        Set-DesignerStage 'click Finish on the Analytic App'
        Close-OneRegistration $script:sessionId $script:sessionHandle
        $finishButton = Wait-For {
            $candidate = [DesignerMouse]::FindAppFinish($appHandle, $script:sessionId)
            if ($candidate -ne [IntPtr]::Zero) { $candidate }
        } 6
        if (-not $finishButton) { throw 'Designer did not expose an enabled Finish button.' }
        try { [DesignerMouse]::ClickFocusedButton($appHandle, $finishButton, $script:sessionId) }
        catch { [DesignerMouse]::ClickControl($finishButton, $script:sessionId) }
    }
    Set-DesignerStage 'wait for the Analytic App result' $TimeoutSeconds
    $result = Wait-For {
        foreach ($name in @('App Results', 'Analytic App Error(s)')) {
            $dialog = [DesignerMouse]::FindDialog($script:sessionId, $name)
            if ($dialog -ne [IntPtr]::Zero) { return @{ handle = $dialog; name = $name } }
        }
    } $TimeoutSeconds
    if (-not $result) { throw 'Designer app did not report an outcome before timeout.' }
    Set-DesignerStage 'capture and close the Analytic App result' 30
    $capture = Join-Path $Case.folder 'designer-result.png'
    [DesignerMouse]::Save($result.handle, $capture)
    $ok = $result.name -eq 'App Results'
    $detail = if (-not $ok) {
        try { [DesignerMouse]::ReadAppErrorText($result.handle, $script:sessionId) }
        catch { "Could not read the Designer error dialog. See screenshot: $capture" }
    }
    [DesignerMouse]::CloseModal($result.handle, $script:sessionId)
    Set-DesignerStage 'close the completed Analytic App' 20
    $remainingApp = Wait-For {
        $dialog = [DesignerMouse]::FindDialog($script:sessionId, $appName)
        if ($dialog -ne [IntPtr]::Zero) { $dialog }
        elseif ([DesignerMouse]::IsWindowEnabled($script:sessionHandle)) { 'closed' }
    } 8
    if ($remainingApp -is [IntPtr]) {
        [DesignerMouse]::CloseModal($remainingApp, $script:sessionId)
    }
    if (-not (Wait-For { [DesignerMouse]::IsWindowEnabled($script:sessionHandle) } ([Math]::Min(20, $TimeoutSeconds)))) {
        throw 'The managed Analytic App remained open.'
    }
    if ($usedWand) { Close-ManagedWorkflow ([IO.Path]::GetFileName($Case.path)) }
    $files = @($Case.artifacts | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    $workbooks = @(Get-RenderWorkbooks $Case | ForEach-Object FullName)
    return @{
        status = if (-not $ok) { 'app_failed' } elseif ($files.Count -ne $Case.artifacts.Count -or -not (Test-RenderFolders $Case)) { 'output_timeout' } else { 'outputs_ready' }
        app_outcome = if ($ok) { 'success' } else { 'failed' }
        detail = $detail
        workflow = $Case.path
        designer_pid = $script:sessionId
        expected_output_count = $Case.artifacts.Count
        output_files = $files + $workbooks
        screenshot = $capture
        app_answer = $Case.numeric.value
        app_launch = if ($usedWand) { 'wand' } else { 'options' }
        answer_review = $answerReview
        verified_answers = $verifiedAnswers
        finish_clicked = $finish
    }
}

function Get-RenderWorkbooks($Case) {
    foreach ($folder in $Case.renderFolders) {
        Get-ChildItem -LiteralPath $folder -Filter '*.xlsx' -File | Where-Object { $_.Length -gt 0 }
    }
}

function Test-RenderFolders($Case) {
    foreach ($folder in $Case.renderFolders) {
        if (-not (Get-ChildItem -LiteralPath $folder -Filter '*.xlsx' -File | Where-Object { $_.Length -gt 0 } | Select-Object -First 1)) {
            return $false
        }
    }
    return $true
}

function Run-Case($Case) {
    if ($Case.app -and -not $Case.numeric -and -not $ManualAppInputs -and
        (-not $Case.answers.Count -or $Case.answers.Count -ne $Case.questionCount)) {
        return @{ status = 'requires_app_inputs'; workflow = $Case.path }
    }
    if (-not $Case.artifacts.Count -and -not $Case.renderFolders.Count) { throw 'No probe or output file was declared for the workflow.' }
    if (@(Get-RenderWorkbooks $Case).Count) { throw 'Render output already exists. Use a fresh run.' }
    foreach ($path in $Case.artifacts) {
        if (Test-Path -LiteralPath $path) { throw "Output already exists. Use a fresh run: $path" }
    }
    Connect-DesignerSession
    if ($Case.app) { return Run-AnalyticApp $Case }
    $name = [IO.Path]::GetFileName($Case.path)
    Open-WorkflowInSession $Case.path
    $handle = $script:sessionHandle
    $before = [DateTime]::UtcNow
    Set-DesignerStage "click Run for $name"
    if (-not (Get-SessionWindow).MainWindowTitle.EndsWith($name, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The active tab changed before the prepared workflow could run.'
    }
    if (-not [DesignerMouse]::TryShortcut($handle, $script:sessionId, 0x52)) {
        $button = Find-DesignerRunButton
        if (-not $button) { throw "Designer did not expose an enabled Run button for $name." }
        Click-DesignerToolbarButton $button
    }
    Set-DesignerStage "wait for $name outputs" $TimeoutSeconds
    $complete = Wait-For {
        $missing = @($Case.artifacts | Where-Object {
            $item = Get-Item -LiteralPath $_ -ErrorAction SilentlyContinue
            -not $item -or $item.Length -le 0 -or $item.LastWriteTimeUtc -lt $before.AddSeconds(-1)
        })
        if ($missing.Count -eq 0 -and (Test-RenderFolders $Case)) { $true }
    } $TimeoutSeconds
    Set-DesignerStage "wait for $name to finish"
    $idle = Wait-For {
        if ([DesignerMouse]::IsRunReady($handle)) { $true }
        else { Find-DesignerRunButton }
    } ([Math]::Min(15, $TimeoutSeconds))
    Set-DesignerStage "capture the $name result"
    $capture = Join-Path $Case.folder 'designer-result.png'
    try { [DesignerMouse]::Save($handle, $capture) }
    catch { $capture = $null }
    $closeError = $null
    if ($idle) {
        try { Close-ManagedWorkflow $name }
        catch { $closeError = $_.Exception.Message }
    }
    return @{
        workflow = $Case.path
        status = if (-not $idle) { 'designer_not_idle' } elseif ($closeError) { 'tab_close_blocked' } elseif (-not $complete) { 'output_timeout' } else { 'outputs_ready' }
        detail = if (-not $idle) { 'Designer did not show the ready Run control after producing output.' }
            elseif (-not $complete) { 'Designer did not produce all expected outputs.' } else { $closeError }
        stage = if (-not $idle) { "wait for $name to finish" }
        designer_pid = $script:sessionId
        output_files = @($Case.artifacts | Where-Object { Test-Path -LiteralPath $_ }) + @(Get-RenderWorkbooks $Case | ForEach-Object FullName)
        expected_output_count = $Case.artifacts.Count
        screenshot = $capture
    }
}

function Invoke-DesignerBatch {
    $rows = @()
    $script:sessionId = 0
    $script:sessionHandle = [IntPtr]::Zero
    $script:dismissedOne = 0
    $reportPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Report)
    if ($PSCmdlet.ParameterSetName -eq 'Plan') {
        $entries = @(Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json)
    } else {
        $entries = @(@{ workflow = $Workflow; status = 'ready' })
    }
    foreach ($entry in $entries) {
        $script:caseIndex = $rows.Count
        $script:currentWorkflow = $entry.workflow
        $script:caseDeadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds).ToUnixTimeMilliseconds()
        Set-DesignerStage 'validate the prepared workflow' $TimeoutSeconds
        if ($entry.status -notin @('ready', 'already_prepared')) {
            $row = @{ workflow = $entry.workflow; status = 'not_prepared'; detail = $entry.reason }
        } else {
            $prepared = $null
            try {
                if ($PSCmdlet.ParameterSetName -eq 'Plan') {
                    $prepared = Get-PreparedCase $entry
                } else {
                    $path = (Resolve-Path -LiteralPath $Workflow).Path
                    $artifacts = @($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($WatchFile))
                    $prepared = @{ path = $path; artifacts = $artifacts; app = $path.EndsWith('.yxwz')
                        folder = Split-Path -Parent $reportPath }
                }
            } catch {
                $row = @{ workflow = $entry.workflow; status = 'preflight_blocked'; detail = $_.Exception.Message }
            }
            if ($prepared) {
                $script:currentWorkflow = $prepared.path
                try { $row = Run-Case $prepared }
                catch { $row = New-DesignerBlocked $script:stage $_.Exception.Message 'automation_blocked' }
            }
        }
        $row.dismissed_alteryx_one = $script:dismissedOne
        $row.session = $script:sessionMode
        $rows += $row
        Write-DesignerJson $rows $reportPath
        if ($row.status -in @('blocked', 'tab_close_blocked', 'designer_not_idle')) { break }
    }
    if (-not $rows.Count) { Write-DesignerJson $rows $reportPath }
    $rows | ForEach-Object { Write-Output "$($_.status) $($_.workflow) $($_.detail)" }
    $script:batchFailed = -not $rows.Count -or @($rows | Where-Object status -ne 'outputs_ready').Count
}

Invoke-DesignerBatch
if ($script:batchFailed) { exit 1 }
