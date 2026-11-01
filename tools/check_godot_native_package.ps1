# Extract into new task-owned folders and check both distributable archives.
param([string]$GodotPath='E:\Apps\Godot\Godot-4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64_console.exe')
$ErrorActionPreference='Stop'
$repositoryPath=Split-Path $PSScriptRoot -Parent
$version='0.2.0-alpha.1'
$token=[guid]::NewGuid().ToString('N')
$checkRoot=Join-Path $repositoryPath ('output/pkg-'+$token.Substring(0,8))
New-Item -ItemType Directory -Path $checkRoot | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
function Expand-CheckedArchive([string]$archivePath,[string]$destination) {
    $resolved=[IO.Path]::GetFullPath($destination)
    if (-not $resolved.StartsWith(([IO.Path]::GetFullPath($checkRoot)+[IO.Path]::DirectorySeparatorChar),[StringComparison]::OrdinalIgnoreCase)) { throw 'Extraction target outside check folder' }
    $archive=[IO.Compression.ZipFile]::OpenRead($archivePath)
    try {
        foreach($entry in $archive.Entries) {
            $target=[IO.Path]::GetFullPath((Join-Path $resolved $entry.FullName))
            if (-not $target.StartsWith(($resolved+[IO.Path]::DirectorySeparatorChar),[StringComparison]::OrdinalIgnoreCase)) { throw 'Archive traversal rejected' }
        }
    } finally { $archive.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory($archivePath,$resolved)
}
function Invoke-Check([string]$executable,[string[]]$arguments,[string]$tag) {
    $stdout=Join-Path $checkRoot ($tag+'.log'); $stderr=Join-Path $checkRoot ($tag+'-errors.log')
    $process=Start-Process -FilePath $executable -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    if (-not $process.WaitForExit(300000)) { throw ('Package check timed out: '+$tag) }
    $process.Refresh()
    if ($process.ExitCode -ne 0 -or ((Get-Content $stdout,$stderr -Raw) -match 'SCRIPT ERROR|ERROR:')) { throw ('Package check failed: '+$tag+'; see '+$checkRoot) }
}
$sourceDestination=Join-Path $checkRoot 'source'
$appDestination=Join-Path $checkRoot 'windows'
Expand-CheckedArchive (Join-Path $repositoryPath ('dist/Open-Planet-Designer-Godot-'+$version+'-Source.zip')) $sourceDestination
Expand-CheckedArchive (Join-Path $repositoryPath ('dist/Open-Planet-Designer-Godot-'+$version+'-Windows.zip')) $appDestination
$sourceRoot=Join-Path $sourceDestination 'Open-Planet-Designer-Source'
$projectPath=Join-Path $sourceRoot 'godot'
$appPath=Join-Path $appDestination 'Open-Planet-Designer'
if ((Test-Path (Join-Path $projectPath '.godot')) -or (Test-Path (Join-Path $projectPath 'assets/generated')) -or (Test-Path (Join-Path $projectPath 'main.tscn'))) { throw 'Native source contains cache or frozen import' }
foreach($name in @('LICENSE','AI_DISCLOSURE.md','THIRD_PARTY_NOTICES.md','GODOT_NOTICES.txt','BUILD.json')) {
    if (-not (Test-Path (Join-Path $appPath $name)) -or -not (Test-Path (Join-Path $sourceRoot $name))) { throw ('Missing notice/metadata: '+$name) }
}
Invoke-Check $GodotPath @('--headless','--path',('"'+$projectPath+'"'),'--editor','--import','--quit') 'source-cold-import'
$coreReport=Join-Path $checkRoot 'source-core.json'
Invoke-Check $GodotPath @('--headless','--path',('"'+$projectPath+'"'),'--script','res://tests/native_core.gd','--',('"--report='+$coreReport+'"')) 'source-core'
$core=Get-Content $coreReport -Raw | ConvertFrom-Json
if (-not $core.passed -or $core.count -ne 27) { throw 'Extracted source core checks failed' }
$renderReport=Join-Path $checkRoot 'app-flight.json'
$imagePath=Join-Path $checkRoot 'app-flight.png'
Invoke-Check (Join-Path $appPath 'OpenPlanetDesigner.exe') @('--rendering-driver','vulkan','--audio-driver','Dummy','--resolution','1280x720','--','--benchmark','--seconds=12','--warmup=10','--route=forest',('--cache-namespace=package-'+$token),('"--report='+$renderReport+'"'),('"--screenshot='+$imagePath+'"')) 'app-flight'
$render=Get-Content $renderReport -Raw | ConvertFrom-Json
if (-not (Test-Path $imagePath) -or $render.flight_frame_count -le 0 -or $render.dropped_frames -ne 0) { throw 'Extracted app did not produce complete render evidence' }
$build=Get-Content (Join-Path $appPath 'BUILD.json') -Raw | ConvertFrom-Json
$pckHash=(Get-FileHash (Join-Path $appPath 'OpenPlanetDesigner.pck') -Algorithm SHA256).Hash.ToLowerInvariant()
if ($build.pck_sha256 -ne $pckHash) { throw 'Packaged app fingerprint mismatch' }
$packageReport=Get-Content (Join-Path $repositoryPath 'output/native-package.json') -Raw | ConvertFrom-Json
$packageReport | Add-Member -NotePropertyName extraction_checks -NotePropertyValue ([ordered]@{
    fresh_source_import=$true;extracted_source_core_checks=27;extracted_executable_vulkan_flight=$true
    runtime_framebuffer=$render.resolution;notices_present=$true;cache_and_frozen_import_excluded=$true
    pck_matches_build_fingerprint=$true;separate_clean_machine_qualified=$false
})
$packageReport | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $repositoryPath 'docs/verification/godot-native-package.json')
$packageReport.extraction_checks | ConvertTo-Json
