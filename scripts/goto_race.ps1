# Launch pgr4recomp with the live pad file and drive it into the first-run St Petersburg race.
# Boot -> intro -> title -> profile dialog / menus (mashing START,A) -> event card -> race.
# Usage: & scripts\goto_race.ps1 [tag] [extra cvars...]   (command file: work\pad_cmd.txt)
param([string]$Tag = 'race', [Parameter(ValueFromRemainingArguments)] [string[]]$Extra)
$root = Split-Path $PSScriptRoot -Parent
$cmd = Join-Path $root 'work\pad_cmd.txt'
$log = Join-Path $root "work\$Tag.log"
Remove-Item $cmd -ErrorAction SilentlyContinue
$env:PGR4_PAD_FILE = $cmd
& (Join-Path $PSScriptRoot 'run.ps1') $Tag @Extra
Remove-Item Env:PGR4_PAD_FILE

function Send([string]$s) { Set-Content $cmd $s }
function LogHas([string]$pat) { (Test-Path $log) -and (Select-String -Path $log -Pattern $pat -SimpleMatch -Quiet) }

$t0 = Get-Date
while (-not (LogHas 'Ford_SierraCosworthRS500')) {
  if (((Get-Date) - $t0).TotalSeconds -gt 240) { 'TIMEOUT waiting for the race car to load'; return }
  if (-not (Get-Process pgr4recomp -ErrorAction SilentlyContinue)) { 'EXITED'; return }
  Send '0:START,2:A'
  Start-Sleep -Seconds 4
}
Start-Sleep -Seconds 4
Send '0:A'   # confirm the difficulty on the event card
"race loading after $([int]((Get-Date) - $t0).TotalSeconds)s; log=$log"
