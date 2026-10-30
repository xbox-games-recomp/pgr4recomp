# Boot with the live pad file and snapshot each screen between single presses.
# Usage: & scripts\dev\boot_steps.ps1 <tag> [presses] [delaySeconds]
#   presses: comma list sent one at a time, e.g. 'START,A,A,A' -> work\<tag>_<n>.png after each step;
#   WAIT = no press, just another snapshot.
param([string]$Tag = 'steps', [string]$Presses = 'START,A,A,A,A', [int]$Delay = 5,
      [Parameter(ValueFromRemainingArguments)] [string[]]$Extra)
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$cmd = Join-Path $root 'work\pad_cmd.txt'
Remove-Item $cmd -ErrorAction SilentlyContinue
$env:PGR4_PAD_FILE = $cmd
& (Join-Path $PSScriptRoot 'run.ps1') $Tag @Extra
Remove-Item Env:PGR4_PAD_FILE

Start-Sleep -Seconds 12
$n = 0
& (Join-Path $PSScriptRoot 'snap.ps1') (Join-Path $root "work\${Tag}_$n.png") | Out-Null
foreach ($b in $Presses.Split(',')) {
  $n++
  if ($b -ne 'WAIT') { Set-Content $cmd "0:$b" }
  Start-Sleep -Seconds $Delay
  if (-not (Get-Process pgr4recomp -ErrorAction SilentlyContinue)) { "EXITED at step $n"; return }
  & (Join-Path $PSScriptRoot 'snap.ps1') (Join-Path $root "work\${Tag}_$n.png") | Out-Null
  "step $n ($b) -> work\${Tag}_$n.png"
}
