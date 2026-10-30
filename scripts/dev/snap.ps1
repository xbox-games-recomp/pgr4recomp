# Capture the pgr4recomp window's own contents via PrintWindow(PW_RENDERFULLCONTENT), so it works while the
# window is covered by other windows and never changes focus. Usage: & scripts\dev\snap.ps1 [out.png]
param([string]$Out = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'work\snap.png'))
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class W { [StructLayout(LayoutKind.Sequential)] public struct R { public int L, T, Ri, B; }
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out R r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }
'@
[W]::SetProcessDPIAware() | Out-Null
$p = Get-Process pgr4recomp -ErrorAction Stop | Select-Object -First 1
$r = New-Object W+R; [W]::GetClientRect($p.MainWindowHandle, [ref]$r) | Out-Null
$bmp = New-Object System.Drawing.Bitmap ([Math]::Max(1, $r.Ri)), ([Math]::Max(1, $r.B))
$g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
$ok = [W]::PrintWindow($p.MainWindowHandle, $hdc, 3)   # PW_CLIENTONLY | PW_RENDERFULLCONTENT
$g.ReleaseHdc($hdc); $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
"saved $Out ($($r.Ri) x $($r.B)) printwindow=$ok"
