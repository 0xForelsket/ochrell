param([ValidateSet('baseline', 'accelerated')][string]$Phase = 'baseline')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$rendererRoot = (Resolve-Path (Join-Path $projectRoot '../oilpaint-renderer')).Path
$executable = Join-Path $rendererRoot 'target/release/examples/canvas_scaling.exe'
$inputDir = Join-Path $projectRoot 'target/measured-oils/balanced-eight/comparison/balanced'
$outputDir = Join-Path $projectRoot "target/measured-oils/canvas-scaling/$Phase"
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
Copy-Item -LiteralPath (Join-Path $rendererRoot 'crates/oil-palette/examples/canvas_scaling.rs') -Destination (Join-Path $outputDir 'canvas_scaling.rs')
$observations = @()
foreach ($width in @(512, 1024, 2048)) {
    $log = Join-Path $outputDir "process-$width.txt"
    $err = Join-Path $outputDir "process-$width.err"
    Write-Output "Starting $Phase width $width"
    $process = Start-Process -FilePath $executable -ArgumentList @("`"$inputDir`"", "`"$outputDir`"", "$width") -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    $observedPeak = 0L
    while (-not $process.HasExited) {
        $process.Refresh()
        if (-not $process.HasExited) { $observedPeak = [Math]::Max($observedPeak, $process.PeakWorkingSet64) }
        Start-Sleep -Milliseconds 100
    }
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "Profiler width $width failed with code $($process.ExitCode). See $err" }
    $observations += [pscustomobject]@{width=$width; observed_peak_working_set_bytes=$observedPeak; exit_code=$process.ExitCode}
    $observations | Export-Csv -LiteralPath (Join-Path $outputDir 'process-memory.csv') -NoTypeInformation -Encoding utf8
    Write-Output "Finished $Phase width $width; observed process peak $observedPeak bytes"
}
