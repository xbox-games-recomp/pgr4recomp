# Boot into the St Petersburg race, leave the car on the start line (static camera) and snapshot the sky
# repeatedly, then count artifact frames with sky_probe.py.
# Usage: & scripts\sky_bench.ps1 <tag> [shots] [extra cvars...]   -> work\<tag>_<n>.png
param([string]$Tag = 'sky', [int]$Shots = 40, [Parameter(ValueFromRemainingArguments)] [string[]]$Extra)
$root = Split-Path $PSScriptRoot -Parent
$Extra = @($Extra | Where-Object { $_ })
& (Join-Path $PSScriptRoot 'boot_steps.ps1') $Tag 'START,START,A,A,A,A,A,A,A,A,A' 5 @Extra | Out-Null
Start-Sleep -Seconds 25   # race load + countdown
for ($n = 0; $n -lt $Shots; $n++) {
  if (-not (Get-Process pgr4recomp -ErrorAction SilentlyContinue)) { "EXITED at shot $n"; break }
  & (Join-Path $PSScriptRoot 'snap.ps1') (Join-Path $root "work\${Tag}_s_$n.png") | Out-Null
  Start-Sleep -Milliseconds 700
}
Stop-Process -Name pgr4recomp -Force -ErrorAction SilentlyContinue
python (Join-Path $PSScriptRoot 'sky_probe.py') (Join-Path $root "work\${Tag}_s_*.png") | Select-Object -Last 1
