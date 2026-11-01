param([string]$GodotPath='E:\Apps\Godot\Godot-4.7.2\Godot_v4.7.2-stable_mono_win64\Godot_v4.7.2-stable_mono_win64_console.exe',[string]$Destination='dist/godot-visual')
$ErrorActionPreference='Stop'
$repositoryPath=Split-Path $PSScriptRoot -Parent
$projectFolder=Join-Path $repositoryPath 'godot'
$destination=Join-Path $repositoryPath $Destination
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
Copy-Item -LiteralPath (Join-Path $projectFolder 'assets/appearance/CREDITS.json') -Destination (Join-Path $credits 'appearance.json')
Copy-Item -LiteralPath (Join-Path $projectFolder 'assets/appearance/proxies.json') -Destination (Join-Path $credits 'proxies.json')
Copy-Item -LiteralPath (Join-Path $projectFolder 'assets/appearance/study.json') -Destination (Join-Path $credits 'study.json')
$revision=git -C $repositoryPath rev-parse HEAD
[ordered]@{version='0.2.0-alpha.2';stage='earth-woodland-visual-study';source_revision=$revision;engine='Godot 4.7.2';ai_assisted=$true;hardware_qualified=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'BUILD.json')
@'
Open Planet Designer — Earth woodland visual development

Run OpenPlanetDesigner.exe. No Blender, Python or editor is required.
RMB + mouse look; WASD fly; Q/E down/up; Shift boost; wheel changes speed.
Home resets the view. H toggles the interface. F2 switches to the native planet.
The default woodland study uses the original Blender layout and fixed source detail.
Use its lighting selector, exposure control and local bounced-light toggle to compare looks.

The separate native planet generates terrain/vegetation as you move. Its appearance
still differs from the fixed study. Photographic approval, distant canopy refinement,
atmosphere, clouds and animated water remain open. Consumer hardware is not qualified.

Source, license and AI disclosure:
https://github.com/katfacey/Open-Planet-Designer/tree/godot-import
'@ | Set-Content -LiteralPath (Join-Path $destination 'README.txt')
Get-ChildItem -LiteralPath $destination -File | Select-Object Name,Length
