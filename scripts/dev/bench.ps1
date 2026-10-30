# Race benchmark (needs a save that reaches the St Petersburg arcade race): boot, menu through to the race,
# hold the throttle, snapshot, then report the race's logged fps and kill the game.
# Usage: & scripts\dev\bench.ps1 <tag> [extra cvars...]   -> work\<tag>.log, work\<tag>_r_<n>.png
param([string]$Tag = 'bench', [Parameter(ValueFromRemainingArguments)] [string[]]$Extra)
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Extra = @($Extra | Where-Object { $_ })
& (Join-Path $PSScriptRoot 'boot_steps.ps1') $Tag 'START,START,A,A,A,A,A,A,A,A,A' 5 @Extra | Out-Null
$raceStart = Get-Date
& (Join-Path $PSScriptRoot 'race_probe.ps1') "${Tag}_r" 20 5 | Out-Null
Stop-Process -Name pgr4recomp -Force -ErrorAction SilentlyContinue
$log = Join-Path $root "work\$Tag.log"
$fps = Select-String -Path $log -Pattern 'PGR4 fps ([\d.]+)' | Where-Object {
  [datetime]::ParseExact($_.Line.Substring(1, 23), 'yyyy-MM-dd HH:mm:ss.fff', $null) -gt $raceStart.AddSeconds(22)
} | ForEach-Object { [double]$_.Matches[0].Groups[1].Value }
"$Tag race fps: $($fps -join ' ')  (mean $([math]::Round(($fps | Measure-Object -Average).Average, 1)))"
