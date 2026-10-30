# Launch pgr4recomp windowed (the SDK's `fullscreen` cvar defaults to true) with a log file.
# Usage: & scripts\dev\run.ps1 [tag] [extra cvars...]   -> log in work\<tag>.log
param([string]$Tag = 'run', [Parameter(ValueFromRemainingArguments)] [string[]]$Extra)
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$exe = Join-Path $root 'out\build\win-amd64-release\pgr4recomp.exe'
$log = Join-Path $root "work\$Tag.log"
Remove-Item $log -ErrorAction SilentlyContinue
$Extra = @($Extra | Where-Object { $_ })
# Repeating a cvar makes the SDK exit at startup, so an explicit --log_level replaces the default.
$level = if ($Extra -match '^--log_level=') { @() } else { @('--log_level=info') }
$cvars = @("--game_data_root=`"$(Join-Path $root 'assets')`"", "--log_file=`"$log`"") + $level +
         @('--fullscreen=false', '--window_width=960', '--window_height=540') + $Extra
$p = Start-Process -FilePath $exe -ArgumentList $cvars -WorkingDirectory (Split-Path $exe) -PassThru
"pid=$($p.Id) log=$log"
