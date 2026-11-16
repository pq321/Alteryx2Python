[CmdletBinding(DefaultParameterSetName = 'Plan')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Plan')][string]$Plan,
    [Parameter(Mandatory, ParameterSetName = 'Single')][string]$Workflow,
    [Parameter(Mandatory, ParameterSetName = 'Single')][string]$WatchFile,
    [Parameter(Mandatory)][string]$Report,
    [ValidateRange(5, 3600)][int]$TimeoutSeconds = 45,
    [int]$DesignerProcessId,
    [string]$DesignerLauncher
)

$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This runner requires Windows Designer.' }
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
    [DllImport("user32.dll")] private static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern bool ShowWindowAsync(IntPtr hwnd, int command);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] private static extern IntPtr WindowFromPoint(Point point);
    [DllImport("user32.dll")] private static extern bool IsChild(IntPtr parent, IntPtr child);
    [DllImport("user32.dll")] private static extern bool GetCursorPos(out Point point);
    [DllImport("user32.dll")] private static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] private static extern void mouse_event(uint flags, uint x, uint y, uint data, UIntPtr extra);
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

    private static Rectangle FindRun(Bitmap image) {
        int width = Math.Min(330, image.Width);
        int height = Math.Min(340, image.Height);
        int originX = image.Width - width;
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
                if (w >= 42 && w <= 125 && h >= 15 && h <= 48 && width - right < 75 &&
                    (double)w / h >= 2.1 && (double)w / h <= 3.3 && pixels > 0.48 * w * h) {
                    match = Rectangle.FromLTRB(originX + left, top, originX + right + 1, bottom + 1);
                    matches++;
                }
            }
        if (matches != 1)
            throw new InvalidOperationException("Could not uniquely identify the blue Designer Run button.");
        return match;
    }

    public static void ClickRun(IntPtr root, uint expectedProcess) {
        if (!IsWindowEnabled(root)) throw new InvalidOperationException("Designer has an open dialog.");
        Box window;
        Rectangle button;
        using (var image = Capture(root, out window)) { button = FindRun(image); }
        Click(root, expectedProcess, window.Left + button.Left + button.Width / 2,
            window.Top + button.Top + button.Height / 2);
    }

    public static void OpenFileMenu(IntPtr root, uint expectedProcess) {
        if (!IsWindowEnabled(root)) throw new InvalidOperationException("Designer has an open dialog.");
        Box window;
        if (!GetWindowRect(root, out window)) throw new InvalidOperationException("Designer window is not available.");
        Click(root, expectedProcess, window.Left + 36, window.Top + 46);
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
        var text = new StringBuilder(64);
        IntPtr length;
        // WM_GETTEXT reads the edit value across processes. UI Automation Name is a label.
        if (SendMessageTimeout(control, 0x000D, new IntPtr(text.Capacity), text, 2, 3000, out length) == IntPtr.Zero)
            throw new InvalidOperationException("Designer did not return the numeric edit value.");
        return text.ToString();
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

    public static void FocusModal(IntPtr dialog, uint expectedProcess) {
        uint pid;
        GetWindowThreadProcessId(dialog, out pid);
        if (pid != expectedProcess || !IsWindowEnabled(dialog) || !IsWindowVisible(dialog))
            throw new InvalidOperationException("Expected a managed Designer dialog.");
        SetForegroundWindow(dialog);
    }

    public static bool IsForeground(IntPtr hwnd) {
        return GetForegroundWindow() == hwnd;
    }

    public static void ClickFocusedButton(IntPtr dialog, IntPtr button, uint expectedProcess) {
        Box bounds;
        if (!IsChild(dialog, button) || !GetWindowRect(button, out bounds) || !IsWindowEnabled(button))
            throw new InvalidOperationException("The managed app exit button is not available.");
        var point = new Point { X = (bounds.Left + bounds.Right) / 2, Y = (bounds.Top + bounds.Bottom) / 2 };
        ClickFocusedPoint(dialog, expectedProcess, point, button);
    }

    public static void OpenOptionsMenu(IntPtr root, uint expectedProcess) {
        Box bounds;
        if (!GetWindowRect(root, out bounds))
            throw new InvalidOperationException("The managed Designer window is not available.");
        var point = new Point { X = bounds.Left + 205, Y = bounds.Top + 46 };
        ClickFocusedPoint(root, expectedProcess, point, IntPtr.Zero);
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
    $app = $filename.EndsWith('.yxwz')
    $numeric = $null
    if ($app) {
        [xml]$workflow = Get-Content -LiteralPath $path -Raw
        $questions = @($workflow.SelectNodes('/AlteryxDocument/Properties/RuntimeProperties/Questions//Question[Type != "Tab"]'))
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
    @{ path = $path; artifacts = $artifacts; app = $app; numeric = $numeric; folder = $folder }
}

function Wait-For([scriptblock]$Condition, [int]$Seconds) {
    $limit = [DateTime]::UtcNow.AddSeconds($Seconds)
    do {
        $result = & $Condition
        if ($result) { return $result }
        Start-Sleep -Milliseconds 350
    } while ([DateTime]::UtcNow -lt $limit)
}

function Get-SessionWindow {
    $process = Get-Process -Id $script:sessionId
    if ($process.ProcessName -ne 'AlteryxGui' -or $process.MainWindowHandle -ne $script:sessionHandle) {
        throw 'The selected Designer session changed.'
    }
    $process
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

function Close-ManagedWorkflow([string]$Filename) {
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
    $executable = Resolve-DesignerExecutable
    $started = Start-Process -FilePath $executable -WindowStyle Normal -PassThru
    $target = Wait-For {
        $process = Get-Process -Id $started.Id -ErrorAction SilentlyContinue
        if ($process -and $process.MainWindowHandle -ne 0 -and
            $process.MainWindowTitle -match '^Alteryx Designer.* - New Workflow\d+$') {
            $process
        }
    } $TimeoutSeconds
    if (-not $target) { throw "Timed out waiting for the new Designer 2025.1 window (PID $($started.Id))." }
    $script:sessionId = $target.Id
    $script:sessionHandle = $target.MainWindowHandle
}

function Open-WorkflowInSession([string]$Path) {
    $name = [IO.Path]::GetFileName($Path)
    if (-not $script:sessionId) { Start-DesignerSession }
    [void](Get-SessionWindow)
    if ([DesignerMouse]::IsIconic($script:sessionHandle)) {
        [DesignerMouse]::Restore($script:sessionHandle, $script:sessionId)
        if (-not (Wait-For { -not [DesignerMouse]::IsIconic($script:sessionHandle) } 5)) {
            throw 'The selected Designer window stayed minimized.'
        }
    }
    if (@([DesignerMouse]::VisibleMenus($script:sessionId)).Count) {
        throw 'Close the open Designer menu before starting the batch.'
    }
    [DesignerMouse]::OpenFileMenu($script:sessionHandle, $script:sessionId)
    $fileMenu = Wait-For {
        $menus = @([DesignerMouse]::VisibleMenus($script:sessionId))
        if ($menus.Count -eq 1) { $menus[0] }
    } 5
    if (-not $fileMenu) { throw 'Designer did not open its File menu.' }
    [DesignerMouse]::ClickMenuItem($fileMenu, $script:sessionId, 80, 90)
    $browseMenu = Wait-For {
        $dialog = Get-SessionDialog
        if ($dialog -and $dialog.Current.Name -eq 'Alteryx - Open File') { return 'picker' }
        $menus = @([DesignerMouse]::VisibleMenus($script:sessionId) | Where-Object { $_ -ne $fileMenu })
        if ($menus.Count -eq 1) { $menus[0] }
    } ([Math]::Min(15, $TimeoutSeconds))
    if (-not $browseMenu) { throw 'Designer did not open its Open Workflow submenu.' }
    if ($browseMenu -is [IntPtr]) { [DesignerMouse]::ClickMenuItem($browseMenu, $script:sessionId, 58, 18) }
    $dialog = Wait-For {
        $candidate = Get-SessionDialog
        if ($candidate -and $candidate.Current.Name -eq 'Alteryx - Open File') { $candidate }
    } ([Math]::Min(15, $TimeoutSeconds))
    if (-not $dialog) { throw 'Designer did not open its file picker.' }
    $selected = Wait-For {
        $candidate = Get-SessionDialog
        if ($candidate -and $candidate.Current.Name -eq 'Alteryx - Open File') {
            [DesignerMouse]::SelectFile([IntPtr]$candidate.Current.NativeWindowHandle, $script:sessionId, $Path)
        }
    } 10
    if (-not $selected) { throw 'Designer file picker did not expose its filename and Open controls.' }
    $loaded = Wait-For {
        $process = Get-SessionWindow
        $popup = Get-SessionDialog
        if ($popup -and $popup.Current.Name -eq 'Update Missing Macros') {
            $messages = @($popup.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition
            ) | ForEach-Object { $_.Current.Name } | Where-Object { $_ -match 'missing|inaccessible|\.yxmc' })
            throw ('Designer rejected macro dependencies: ' + ($messages -join ' '))
        }
        if ($popup -and $popup.Current.Name -ne 'Alteryx - Open File') {
            $message = @($popup.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition
            ) | Where-Object { $_.Current.ControlType -eq [System.Windows.Automation.ControlType]::Text } |
                ForEach-Object { $_.Current.Name })
            throw "Designer dialog while opening ${name}: $($popup.Current.Name) $($message -join ' ')"
        }
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

function Run-NumericApp($Case) {
    if (-not $script:sessionId) { throw 'Select an existing Designer 2025.1 session to run an analytic app.' }
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
    $appName = 'Alteryx Designer x64 Analytic App - ' + [IO.Path]::GetFileNameWithoutExtension($Case.path)
    $appHandle = Wait-ForNamedDialog $appName
    $app = [System.Windows.Automation.AutomationElement]::FromHandle($appHandle)
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
    [DesignerMouse]::Save([IntPtr]$app.Current.NativeWindowHandle, (Join-Path $Case.folder 'designer-app-answer.png'))
    if (-not $verified) {
        $observed = [DesignerMouse]::ReadNumericEdit($editHandle, $script:sessionId)
        [DesignerMouse]::CloseModal($appHandle, $script:sessionId)
        throw "Designer numeric answer differs from the prepared value (expected $expected, observed '$observed')."
    }
    Invoke-DialogButton $app @('Finish')
    $result = Wait-For {
        foreach ($name in @('App Results', 'Analytic App Error(s)')) {
            $dialog = [DesignerMouse]::FindDialog($script:sessionId, $name)
            if ($dialog -ne [IntPtr]::Zero) { return @{ handle = $dialog; name = $name } }
        }
    } $TimeoutSeconds
    if (-not $result) { throw 'Designer app did not report an outcome before timeout.' }
    $capture = Join-Path $Case.folder 'designer-result.png'
    [DesignerMouse]::Save($result.handle, $capture)
    $ok = $result.name -eq 'App Results'
    [DesignerMouse]::CloseModal($result.handle, $script:sessionId)
    $remainingApp = Wait-For {
        $dialog = [DesignerMouse]::FindDialog($script:sessionId, $appName)
        if ($dialog -ne [IntPtr]::Zero) { $dialog }
        elseif ([DesignerMouse]::IsWindowEnabled($script:sessionHandle)) { 'closed' }
    } 8
    if ($remainingApp -is [IntPtr]) {
        $form = [System.Windows.Automation.AutomationElement]::FromHandle($remainingApp)
        if (-not (Wait-For { Find-EnabledDialogControls $form @('Close', 'Exit') } 8)) {
            throw 'The managed Analytic App has no enabled Close or Exit button.'
        }
        $buttons = @(Find-EnabledDialogControls $form @('Close', 'Exit'))
        if ($buttons.Count -ne 1) { throw 'Expected one managed app exit button.' }
        try {
            [DesignerMouse]::FocusModal($remainingApp, $script:sessionId)
            if (Wait-For { [DesignerMouse]::IsForeground($remainingApp) } 5) {
                [DesignerMouse]::ClickFocusedButton(
                    $remainingApp, [IntPtr]$buttons[0].Current.NativeWindowHandle, $script:sessionId)
            } else {
                Invoke-DialogButton $form @('Close', 'Exit')
            }
        } catch {
            Invoke-DialogButton $form @('Close', 'Exit')
        }
    }
    if (-not (Wait-For { [DesignerMouse]::IsWindowEnabled($script:sessionHandle) } ([Math]::Min(20, $TimeoutSeconds)))) {
        throw 'The managed Analytic App remained open.'
    }
    $files = @($Case.artifacts | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
    return @{
        status = if (-not $ok) { 'app_failed' } elseif ($files.Count -ne $Case.artifacts.Count) { 'output_timeout' } else { 'outputs_ready' }
        workflow = $Case.path
        designer_pid = $script:sessionId
        expected_output_count = $Case.artifacts.Count
        output_files = $files
        screenshot = $capture
        app_answer = $Case.numeric.value
    }
}

function Run-Case($Case) {
    if ($Case.app -and -not $Case.numeric) { return @{ status = 'requires_app_inputs'; workflow = $Case.path } }
    if (-not $Case.artifacts.Count) { throw 'No probe or output file was declared for the workflow.' }
    foreach ($path in $Case.artifacts) {
        if (Test-Path -LiteralPath $path) { throw "Output already exists. Use a fresh run: $path" }
    }
    if ($Case.app) { return Run-NumericApp $Case }
    $name = [IO.Path]::GetFileName($Case.path)
    Open-WorkflowInSession $Case.path
    $handle = $script:sessionHandle
    $before = [DateTime]::UtcNow
    $clicked = Wait-For {
        $same = Get-SessionWindow
        if (-not $same.MainWindowTitle.EndsWith($name, [StringComparison]::OrdinalIgnoreCase)) { return }
        try { [DesignerMouse]::ClickRun($handle, $script:sessionId); $true }
        catch { $script:lastClickError = $_.Exception.Message }
    } ([Math]::Min(15, $TimeoutSeconds))
    if (-not $clicked) { throw "Could not click Run in $name. $script:lastClickError" }
    $complete = Wait-For {
        $missing = @($Case.artifacts | Where-Object {
            $item = Get-Item -LiteralPath $_ -ErrorAction SilentlyContinue
            -not $item -or $item.Length -le 0 -or $item.LastWriteTimeUtc -lt $before.AddSeconds(-1)
        })
        if ($missing.Count -eq 0) { $true }
    } $TimeoutSeconds
    $idle = Wait-For { [DesignerMouse]::IsRunReady($handle) } $TimeoutSeconds
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
        detail = $closeError
        designer_pid = $script:sessionId
        output_files = @($Case.artifacts | Where-Object { Test-Path -LiteralPath $_ })
        expected_output_count = $Case.artifacts.Count
        screenshot = $capture
    }
}

function Invoke-DesignerBatch {
    $rows = @()
    $script:sessionId = 0
    $script:sessionHandle = [IntPtr]::Zero
    if (-not $DesignerProcessId) {
        $existing = @(Get-Process AlteryxGui -ErrorAction SilentlyContinue | Where-Object {
            $_.MainWindowHandle -ne 0 -and (Test-Designer2025_1 $_.Path)
        })
        $blank = @($existing | Where-Object MainWindowTitle -match '^Alteryx Designer.* - New Workflow\d+$')
        if ($blank.Count -eq 1) { $DesignerProcessId = $blank[0].Id }
        elseif ($existing.Count) { throw 'Use -DesignerProcessId to select a single Designer window with a blank workflow tab.' }
    }
    if ($DesignerProcessId) {
        $initial = Get-Process -Id $DesignerProcessId
        if ($initial.ProcessName -ne 'AlteryxGui' -or $initial.MainWindowHandle -eq 0 -or
            $initial.MainWindowTitle -notmatch '^Alteryx Designer.* - New Workflow\d+$' -or
            -not (Test-Designer2025_1 $initial.Path)) {
            throw 'Choose an existing Designer 2025.1 window with a blank workflow tab.'
        }
        $script:sessionId = $initial.Id
        $script:sessionHandle = $initial.MainWindowHandle
    }
    $reportPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Report)
    [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($reportPath))
    if ($PSCmdlet.ParameterSetName -eq 'Plan') {
        $entries = @(Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json)
        foreach ($entry in $entries) {
            if ($entry.status -notin @('ready', 'already_prepared')) {
                $rows += @{ workflow = $entry.workflow; status = 'not_prepared'; detail = $entry.reason }
            } else {
                $prepared = $null
                try { $prepared = Get-PreparedCase $entry }
                catch { $rows += @{ workflow = $entry.workflow; status = 'preflight_blocked'; detail = $_.Exception.Message } }
                if ($prepared) {
                    try { $rows += Run-Case $prepared }
                    catch { $rows += @{ workflow = $entry.workflow; status = 'blocked'; detail = $_.Exception.Message } }
                }
            }
            ConvertTo-Json -InputObject $rows -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding utf8
            if ($rows[-1].status -in @('blocked', 'tab_close_blocked', 'designer_not_idle')) { break }
        }
    } else {
        $path = (Resolve-Path -LiteralPath $Workflow).Path
        $artifacts = @($ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($WatchFile))
        $case = @{ path = $path; artifacts = $artifacts; app = $path.EndsWith('.yxwz'); folder = Split-Path -Parent $reportPath }
        try { $rows += Run-Case $case }
        catch { $rows += @{ workflow = $path; status = 'blocked'; detail = $_.Exception.Message } }
    }
    ConvertTo-Json -InputObject $rows -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding utf8
    $rows | ForEach-Object { Write-Output "$($_.status) $($_.workflow) $($_.detail)" }
    $script:batchFailed = -not $rows.Count -or @($rows | Where-Object status -ne 'outputs_ready').Count
}

$batchLock = [Threading.Mutex]::new($false, 'Local\Alteryx2Python.DesignerBatch')
$hasLock = $false
try {
    try { $hasLock = $batchLock.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $hasLock = $true }
    if (-not $hasLock) { throw 'A Designer parity batch is already running in this Windows session.' }
    Invoke-DesignerBatch
} finally {
    if ($hasLock) { $batchLock.ReleaseMutex() }
    $batchLock.Dispose()
}
if ($script:batchFailed) { exit 1 }
