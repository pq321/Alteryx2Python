param([string]$Root)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Media.Ocr, ContentType=WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
function Await($operation,[Type]$type) {
  $task = $asTask.MakeGenericMethod($type).Invoke($null,@($operation))
  $task.Wait(-1) | Out-Null
  $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage([Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]::new('en-US'))
if (!$engine) { throw 'English OCR is unavailable' }
$rows = foreach($p in (Get-ChildItem -LiteralPath $Root -Recurse -Filter designer-result.png)) {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($p.FullName)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode, Windows.Storage, ContentType=WindowsRuntime]::Read)) ([Windows.Storage.Streams.IRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime])
    try {
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType=WindowsRuntime])
        $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult, Windows.Media.Ocr, ContentType=WindowsRuntime])
        [ordered]@{run=$p.Directory.Name; lines=@($result.Lines | ForEach-Object Text)}
    } finally { $stream.Dispose() }
}
ConvertTo-Json -InputObject @($rows) -Depth 5 | Set-Content -Encoding UTF8 (Join-Path $Root 'designer-ocr.json')
