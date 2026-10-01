$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$rendererRoot = (Resolve-Path (Join-Path $projectRoot '../oilpaint-renderer')).Path
$executable = Join-Path $rendererRoot 'target/release/examples/forward_paint.exe'
$inputDir = Join-Path $projectRoot 'target/measured-oils/balanced-eight/comparison/balanced'
$outputDir = Join-Path $projectRoot 'target/measured-oils/forward-math/painting'
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
foreach ($width in @(512, 1024, 2048)) {
    Write-Output "Starting forward comparison width $width"
    $log = Join-Path $outputDir "process-$width.txt"
    $err = Join-Path $outputDir "process-$width.err"
    $process = Start-Process -FilePath $executable -ArgumentList @("`"$inputDir`"", "`"$outputDir`"", "$width") -WindowStyle Hidden -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "Forward comparison width $width failed. See $err" }
    Write-Output "Finished forward comparison width $width"
}
