# After goto_race.ps1: wait for the race to start, hold the throttle and snapshot a few frames.
# Usage: & scripts\race_probe.ps1 <tag> [startDelaySeconds] [snapshots]   -> work\<tag>_<n>.png
param([string]$Tag = 'probe', [int]$StartDelay = 25, [int]$Shots = 4)
$root = Split-Path $PSScriptRoot -Parent
$cmd = Join-Path $root 'work\pad_cmd.txt'
Start-Sleep -Seconds $StartDelay
Set-Content $cmd "0:RT=0.7:$(($Shots * 3 + 2) * 1000)"
for ($n = 0; $n -lt $Shots; $n++) {
  Start-Sleep -Seconds 3
  if (-not (Get-Process pgr4recomp -ErrorAction SilentlyContinue)) { "EXITED at shot $n"; return }
  & (Join-Path $PSScriptRoot 'snap.ps1') (Join-Path $root "work\${Tag}_$n.png") | Out-Null
  "shot $n -> work\${Tag}_$n.png"
}
