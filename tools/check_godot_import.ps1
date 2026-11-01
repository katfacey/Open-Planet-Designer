# Run actual Vulkan renders and save editable Godot scenes for the exported sites.
param(
    [string]$GodotPath = 'E:\Apps\Godot\Godot-4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64_console.exe',
    [string[]]$Sites = @('Forest','Grassland','Alpine','Desert','Ocean'),
    [switch]$Reload
)
$ErrorActionPreference = 'Stop'
$repositoryPath = Split-Path $PSScriptRoot -Parent
$projectFolder = Join-Path $repositoryPath 'godot'
$outputFolder = Join-Path $repositoryPath 'output'
$checkOutput = & $GodotPath --headless --path $projectFolder --check-only --script res://scripts/viewer.gd 2>&1
if ($LASTEXITCODE -ne 0 -or ($checkOutput -match 'SCRIPT ERROR|ERROR:')) { throw ('Godot script validation failed: '+($checkOutput -join "`n")) }
foreach ($site in $Sites) {
    if ($site -notin @('Forest','Grassland','Alpine','Desert','Ocean')) { throw 'Unknown review location' }
    $suffix = if ($Reload) { '-reload' } else { '' }
    $stem = 'godot-' + $site.ToLowerInvariant() + $suffix
    $imagePath = Join-Path $outputFolder ($stem+'.png')
    $reportPath = Join-Path $outputFolder ($stem+'.json')
    $stdoutPath = Join-Path $outputFolder ($stem+'.log')
    $stderrPath = Join-Path $outputFolder ($stem+'-errors.log')
    $startedUtc = [DateTime]::UtcNow
    $arguments = @('--path',('"'+$projectFolder+'"'),'--rendering-driver','vulkan','--audio-driver','Dummy','--quit-after','20000','res://main.tscn','--',
        '--smoke',('--site='+$site),('"--screenshot='+$imagePath+'"'),('"--report='+$reportPath+'"'))
    if (-not $Reload) { $arguments += '--save-scene' }
    $job = Start-Process -FilePath $GodotPath -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    if ($job.ExitCode -ne 0) { throw ('Godot failed for '+$site) }
    $errors = Get-Content -LiteralPath $stderrPath -Raw
    if ($errors -match 'SCRIPT ERROR|ERROR:') { throw ('Godot reported errors for '+$site+': '+$errors) }
    if (-not (Test-Path -LiteralPath $reportPath) -or -not (Test-Path -LiteralPath $imagePath)) { throw 'Missing Godot outputs' }
    if ((Get-Item -LiteralPath $reportPath).LastWriteTimeUtc -lt $startedUtc -or (Get-Item -LiteralPath $imagePath).LastWriteTimeUtc -lt $startedUtc) { throw 'Godot did not produce fresh outputs' }
    $report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
    [pscustomobject]@{Site=$site;Instances=$report.instances;Terrain=$report.terrain_triangles;FPS=$report.fps_at_capture;LoadSeconds=$report.load_seconds;Reload=[bool]$Reload}
}
