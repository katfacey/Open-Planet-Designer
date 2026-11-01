# Launch the imported project with the user's existing Godot installation.
param([string]$GodotPath='', [switch]$Editor, [switch]$Review)
$ErrorActionPreference='Stop'
if (-not $GodotPath) {
    $command=Get-Command godot,godot4 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command) { $GodotPath=$command.Source }
}
if (-not $GodotPath) {
    $reader=New-Object -ComObject WScript.Shell
    $menus=@([Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('CommonPrograms'))
    foreach ($menu in $menus) {
        $links=Get-ChildItem -LiteralPath $menu -Filter '*Godot*.lnk' -Recurse -ErrorAction SilentlyContinue | Sort-Object Name -Descending
        foreach ($link in $links) {
            $target=$reader.CreateShortcut($link.FullName).TargetPath
            if (Test-Path -LiteralPath $target) { $GodotPath=$target; break }
        }
        if ($GodotPath) { break }
    }
}
if (-not $GodotPath -or -not (Test-Path -LiteralPath $GodotPath)) { throw 'Pass the installed Godot executable with -GodotPath.' }
$arguments=@('--path',('"'+$PSScriptRoot+'"'))
if ($Editor) { $arguments+=@('--editor',$(if ($Review) {'res://scenes/forest.tscn'} else {'res://runtime.tscn'})) }
elseif ($Review) { $arguments+='res://main.tscn' }
# This is an interactive editor/viewer window for the user.
Start-Process -FilePath $GodotPath -ArgumentList $arguments -WindowStyle Normal
