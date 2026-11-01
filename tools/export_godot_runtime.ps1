param([string]$GodotPath='E:\Apps\Godot\Godot-4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64_console.exe')
$ErrorActionPreference='Stop'
$repositoryPath=Split-Path $PSScriptRoot -Parent
$projectFolder=Join-Path $repositoryPath 'godot'
$destination=Join-Path $repositoryPath 'dist/godot-runtime'
New-Item -Path $destination -ItemType Directory -Force | Out-Null
$executable=Join-Path $destination 'OpenPlanetDesigner.exe'
$log=Join-Path $repositoryPath 'output/native-export.log'
& $GodotPath --headless --path $projectFolder --export-release 'Windows Native Alpha' $executable *> $log
if ($LASTEXITCODE -ne 0) { Get-Content -LiteralPath $log -Tail 25; throw 'Native Windows export failed' }
if ((Get-Content -LiteralPath $log -Raw) -match 'SCRIPT ERROR|ERROR:') { throw ('Export errors; see '+$log) }
& $GodotPath --headless --path $projectFolder --script res://tests/write_engine_notices.gd -- ('--output='+(Join-Path $destination 'GODOT_NOTICES.txt')) *> (Join-Path $repositoryPath 'output/native-engine-notices.log')
if ($LASTEXITCODE -ne 0) { throw 'Engine notice generation failed' }
foreach($name in @('LICENSE','AI_DISCLOSURE.md','THIRD_PARTY_NOTICES.md')) { Copy-Item -LiteralPath (Join-Path $repositoryPath $name) -Destination (Join-Path $destination $name) }
$credits=Join-Path $destination 'source-credits'
New-Item -Path $credits -ItemType Directory -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $projectFolder 'assets/catalog/catalog.json') -Destination (Join-Path $credits 'catalog.json')
Copy-Item -LiteralPath (Join-Path $projectFolder 'assets/native/regions.json') -Destination (Join-Path $credits 'regions.json')
Copy-Item -LiteralPath (Join-Path $repositoryPath 'open_planet_lab/assets/CREDITS.json') -Destination (Join-Path $credits 'models.json')
Copy-Item -LiteralPath (Join-Path $repositoryPath 'open_planet_lab/assets/ground/CREDITS.json') -Destination (Join-Path $credits 'ground.json')
$revision=git -C $repositoryPath rev-parse HEAD
[ordered]@{version='0.2.0-alpha.1';stage='native-streaming-alpha';source_revision=$revision;engine='Godot 4.7.2';ai_assisted=$true;hardware_qualified=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'BUILD.json')
@'
Open Planet Designer — native streaming alpha

Run OpenPlanetDesigner.exe. No Blender, Python or editor is required.
RMB + mouse look; WASD fly; Q/E down/up; Shift boost; wheel changes speed.
Home returns to the woodland; O goes to orbit; P replays a route; V toggles vegetation.
F8 saves a profiling report to Godot's user data folder; H toggles the interface.

Terrain and vegetation generate/stream as you move. This is an engineering alpha.
Photographic lighting, planetary atmosphere, clouds, animated water and additional
biome refinement remain in development. Consumer hardware is not qualified.

Source, license and AI disclosure:
https://github.com/katfacey/Open-Planet-Designer/tree/godot-import
'@ | Set-Content -LiteralPath (Join-Path $destination 'README.txt')
Get-ChildItem -LiteralPath $destination -File | Select-Object Name,Length
