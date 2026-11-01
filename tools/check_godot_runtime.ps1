param(
    [string]$GodotPath='E:\Apps\Godot\Godot-4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64_console.exe',
    [string]$Executable='', [int]$Seconds=60, [int]$Warmup=15,
    [ValidateSet('woodland','forest','orbit','seam')][string]$Route='woodland', [string]$Tag='native-flight', [string]$CacheNamespace='',
    [string]$Resolution='1920x1080'
)
$ErrorActionPreference='Stop'
$repositoryPath=Split-Path $PSScriptRoot -Parent
$outputFolder=Join-Path $repositoryPath 'output'
$projectFolder=Join-Path $repositoryPath 'godot'
if ($Tag -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Use a plain output tag' }
$reportPath=Join-Path $outputFolder ($Tag+'.json')
$imagePath=Join-Path $outputFolder ($Tag+'.png')
$stdoutPath=Join-Path $outputFolder ($Tag+'.log')
$stderrPath=Join-Path $outputFolder ($Tag+'-errors.log')
$arguments=@('--rendering-driver','vulkan','--audio-driver','Dummy','--quit-after','100000','--resolution',$Resolution)
$standalone=[bool]$Executable
if (-not $Executable) {
    $validation=& $GodotPath --headless --path $projectFolder --check-only --script res://scripts/runtime.gd 2>&1
    if ($LASTEXITCODE -ne 0 -or ($validation -match 'ERROR:')) { throw ($validation -join "`n") }
    $Executable=$GodotPath -replace '_console\.exe$','.exe'
    if (-not (Test-Path -LiteralPath $Executable)) { $Executable=$GodotPath }
    $arguments+=@('--path',('"'+$projectFolder+'"'),'res://runtime.tscn')
}
$arguments+=@('--','--benchmark',('--seconds='+$Seconds),('--warmup='+$Warmup),('--route='+$Route),('"--report='+$reportPath+'"'),('"--screenshot='+$imagePath+'"'))
if ($CacheNamespace) { $arguments+=('"--cache-namespace='+$CacheNamespace+'"') }
$startUtc=[DateTime]::UtcNow
$process=Start-Process -FilePath $Executable -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
$peakRss=0L
$modulesChecked=$false
$managedRuntimeDetected=$false
while (-not $process.HasExited) {
    if (([DateTime]::UtcNow-$startUtc).TotalSeconds -gt ($Seconds+$Warmup+120)) { $process.Kill();throw 'Native Godot route timed out' }
    $process.Refresh()
    try { $peakRss=[Math]::Max($peakRss,$process.PeakWorkingSet64) } catch { }
    if (-not $modulesChecked -and ([DateTime]::UtcNow-$startUtc).TotalSeconds -gt 5) {
        try { $managedRuntimeDetected=[bool]($process.Modules | Where-Object { $_.ModuleName -match 'coreclr|hostfxr|GodotSharp' });$modulesChecked=$true } catch { }
    }
    Start-Sleep -Milliseconds 250
}
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw ('Godot runtime failed, exit '+$process.ExitCode) }
if ((Get-Content -LiteralPath @($stdoutPath,$stderrPath) -Raw) -match 'SCRIPT ERROR|ERROR:') { throw ('Godot errors in '+$stdoutPath+' or '+$stderrPath) }
if (-not (Test-Path -LiteralPath $reportPath) -or (Get-Item -LiteralPath $reportPath).LastWriteTimeUtc -lt $startUtc) { throw 'No fresh profiling report' }
if (-not (Test-Path -LiteralPath $imagePath) -or (Get-Item -LiteralPath $imagePath).LastWriteTimeUtc -lt $startUtc) { throw 'No fresh screenshot' }
$report=Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
$harness=[ordered]@{route=$Route;seconds=$Seconds;warmup_seconds=$Warmup;cache_namespace=$CacheNamespace;requested_resolution=$Resolution;actual_framebuffer=$report.resolution;observed_peak_working_set_bytes=$peakRss;managed_module_check_completed=$modulesChecked;managed_runtime_modules_detected=$managedRuntimeDetected;exit_code=$process.ExitCode;engine_errors=$false;report=$reportPath;standalone=$standalone}
$harness | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $outputFolder ($Tag+'-process.json'))
$report.flight_distributions | ConvertTo-Json -Depth 5
$harness | ConvertTo-Json
