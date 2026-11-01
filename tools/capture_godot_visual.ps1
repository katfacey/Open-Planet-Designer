param(
    [string]$GodotPath='E:\Apps\Godot\Godot-4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64.exe',
    [ValidateSet('native','reference','study')][string[]]$Modes=@('native'),
    [ValidateSet('daylight','overcast','backlight')][string]$Lighting='daylight',
    [ValidateSet('eye','ground','canopy','meadow')][string]$View='eye',
    [string]$Tag='visual', [int]$Settle=25, [switch]$GI
)
$ErrorActionPreference='Stop'
if($Tag -notmatch '^[a-zA-Z0-9_-]+$') { throw 'Use a plain output tag' }
$repositoryPath=Split-Path $PSScriptRoot -Parent
$projectPath=Join-Path $repositoryPath 'godot'
$consolePath=$GodotPath -replace '\.exe$','_console.exe'
$validation=& $consolePath --headless --path $projectPath --check-only --script res://tests/capture_visual.gd 2>&1
if($LASTEXITCODE -ne 0 -or $validation -match 'SCRIPT ERROR|ERROR:') { throw ($validation -join "`n") }
foreach($mode in $Modes) {
    $stem=Join-Path $repositoryPath ('output/'+$Tag+'-'+$mode+'-'+$Lighting+'-'+$View)
    $arguments=@('--path',('"'+$projectPath+'"'),'--rendering-driver','vulkan','--audio-driver','Dummy','--resolution','1280x720','--script','res://tests/capture_visual.gd','--',('--mode='+$mode),('--lighting='+$Lighting),('--view='+$View),('--settle='+$Settle),('"--output='+$stem+'.png"'))
    if($GI) { $arguments+='--gi' }
    $started=[DateTime]::UtcNow
    $process=Start-Process -FilePath $GodotPath -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput ($stem+'.log') -RedirectStandardError ($stem+'-errors.log')
    if(-not $process.WaitForExit(($Settle+120)*1000)) { $process.Kill(); throw 'Visual capture timed out' }
    $process.WaitForExit()
    if($process.ExitCode -ne 0 -or (Get-Content -LiteralPath @(($stem+'.log'),($stem+'-errors.log')) -Raw) -match 'SCRIPT ERROR|ERROR:') { throw ('Visual capture failed: '+$stem) }
    if(-not (Test-Path ($stem+'.png')) -or (Get-Item ($stem+'.png')).LastWriteTimeUtc -lt $started) { throw 'Missing fresh visual capture' }
    Write-Output ($stem+'.png')
}
