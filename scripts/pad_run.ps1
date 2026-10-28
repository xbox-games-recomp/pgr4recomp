# Run pgr4recomp windowed with a scripted pad and periodic snapshots, then stop it and build a contact sheet.
# Usage: & scripts\pad_run.ps1 <tag> <PGR4_PAD spec> [seconds=120] [snap_every=10] [snap_from=0]
param([Parameter(Mandatory)] [string]$Tag, [Parameter(Mandatory)] [string]$Pad,
      [int]$Seconds = 120, [int]$Every = 10, [int]$From = 0)
$root = Split-Path $PSScriptRoot -Parent
$dir = Join-Path $root "work\$Tag"
New-Item -ItemType Directory -Force $dir | Out-Null
Get-ChildItem $dir -Filter *.png -ErrorAction SilentlyContinue | Remove-Item
$env:PGR4_PAD = $Pad
& (Join-Path $PSScriptRoot 'run.ps1') $Tag
Remove-Item Env:PGR4_PAD
$t0 = Get-Date
$shots = @()
while (((Get-Date) - $t0).TotalSeconds -lt $Seconds) {
  Start-Sleep -Milliseconds 250
  $t = [int]((Get-Date) - $t0).TotalSeconds
  if (-not (Get-Process pgr4recomp -ErrorAction SilentlyContinue)) { "EXITED at ~${t}s"; break }
  if ($t -ge $From -and ($t % $Every) -eq 0 -and -not ($shots -contains $t)) {
    & (Join-Path $PSScriptRoot 'snap.ps1') (Join-Path $dir ("t{0:D3}.png" -f $t)) | Out-Null
    $shots += $t
  }
}
Stop-Process -Name pgr4recomp -Force -ErrorAction SilentlyContinue

# Contact sheet: 4 columns of 320x180 thumbnails, labelled with the capture time.
Add-Type -AssemblyName System.Drawing
$files = Get-ChildItem $dir -Filter 't*.png' | Sort-Object Name
if ($files) {
  $cols = 4; $tw = 320; $th = 180; $rows = [Math]::Ceiling($files.Count / $cols)
  $sheet = New-Object System.Drawing.Bitmap ($cols * $tw), ($rows * $th)
  $g = [System.Drawing.Graphics]::FromImage($sheet)
  $font = New-Object System.Drawing.Font 'Arial', 11
  for ($i = 0; $i -lt $files.Count; $i++) {
    $im = [System.Drawing.Image]::FromFile($files[$i].FullName)
    $x = ($i % $cols) * $tw; $y = [Math]::Floor($i / $cols) * $th
    $g.DrawImage($im, $x, $y, $tw, $th)
    $g.DrawString($files[$i].BaseName, $font, [System.Drawing.Brushes]::Yellow, $x + 3, $y + 3)
    $im.Dispose()
  }
  $sheet.Save((Join-Path $dir 'sheet.png')); $g.Dispose(); $sheet.Dispose()
}
"shots=$($shots.Count) sheet=$(Join-Path $dir 'sheet.png') log=$(Join-Path $root "work\$Tag.log")"
