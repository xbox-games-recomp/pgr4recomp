# Gets the ReXGlue SDK ready for pgr4recomp: clones v0.10.0 into ..\_ext\rexglue-sdk (next to this repository),
# replaces the git symlinks that a Windows checkout leaves as text files, applies patches\rexglue-*.patch and
# builds + installs it (scripts\build_sdk.bat). Prints SDK_READY at the end.
#
# Safe to re-run: a step that is already done is skipped. The launcher's Setup page runs it; README "Building"
# describes the same steps by hand.
# Not "Stop": Windows PowerShell treats any git stderr (progress, the probe below) as fatal then.
$ErrorActionPreference = "Continue"
$repo = Split-Path $PSScriptRoot
$sdk = Join-Path (Split-Path $repo) "_ext\rexglue-sdk"
$install = Join-Path $sdk "out\install\win-amd64\bin"
$stamp = Join-Path $sdk "out\pgr4recomp-patches.txt"
# README order; each patch is a git diff of the SDK tree on top of the previous ones.
$patches = "rexglue-draw-debug", "rexglue-gpu-frame-stats", "rexglue-texture-heap-pool",
           "rexglue-vpkd3d-float16-range", "rexglue-x360-half-vertex-kill" |
           ForEach-Object { Join-Path $repo "patches\$_.patch" }

# 1. Source
if (-not (Test-Path (Join-Path $sdk "CMakeLists.txt"))) {
    "Cloning the ReXGlue SDK v0.10.0 into $sdk"
    git clone --recursive --branch v0.10.0 https://github.com/rexglue/rexglue-sdk.git $sdk 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "git clone failed" }
} else {
    "SDK source: $sdk"
}

# 2. Symlinks (libmspack cabextract/mspack/*, o1heap): git without symlink support writes each one as a
# text file holding the link target. Replace those with a copy of the target.
$dirs = @($sdk) + @(git -C $sdk submodule foreach --quiet --recursive 'echo $displaypath' |
                    ForEach-Object { Join-Path $sdk $_ })
$fixed = 0
foreach ($d in $dirs) {
    foreach ($line in (git -C $d ls-files -s 2>$null | Where-Object { $_ -like "120000 *" })) {
        $link = Join-Path $d ($line -split "`t", 2)[1]
        if (-not (Test-Path $link -PathType Leaf) -or (Get-Item $link).Length -gt 512) { continue }
        $target = Join-Path (Split-Path $link) ((Get-Content $link -Raw).Trim())
        if (-not (Test-Path $target)) { continue }  # already a real file
        Remove-Item $link -Force
        Copy-Item $target $link -Recurse -Force
        $fixed++
    }
}
"Symlinks replaced: $fixed"

# 3. Patches. The stamp records the patch set this tree was built with.
$want = ($patches | ForEach-Object { (Get-FileHash $_ -Algorithm SHA1).Hash }) -join "`n"
$have = if (Test-Path $stamp) { (Get-Content $stamp -Raw).Trim() } else { $null }
$rebuild = -not (Test-Path (Join-Path $install "rexglue.exe"))
if ($have -eq $want) {
    "Patches already applied"
} elseif (-not $have -and (git -C $sdk status --porcelain --untracked-files=no --ignore-submodules=all)) {
    # A tree patched by hand before this script existed.
    "The SDK tree already has local changes; assuming the patches are in (delete $sdk to start clean)"
    New-Item -ItemType Directory -Force (Split-Path $stamp) | Out-Null
    Set-Content $stamp $want
} else {
    if ($have) { throw "The patches changed since the SDK was built. Revert the SDK tree (git -C `"$sdk`" checkout .) and run again." }
    foreach ($p in $patches) {
        git -C $sdk apply $p
        if ($LASTEXITCODE -ne 0) {
            throw "$(Split-Path $p -Leaf) does not apply to $sdk. Is it a clean v0.10.0 tree? (git -C `"$sdk`" checkout .)"
        }
        "Applied $(Split-Path $p -Leaf)"
    }
    New-Item -ItemType Directory -Force (Split-Path $stamp) | Out-Null
    Set-Content $stamp $want
    $rebuild = $true
}

# 4. Build + install
if ($rebuild) {
    & cmd /c "`"$PSScriptRoot\build_sdk.bat`" `"$sdk`"" 2>&1 | ForEach-Object { "$_" }
    if ($LASTEXITCODE -ne 0) { throw "SDK build failed" }
    # The game build copies the SDK DLLs only when it is configured; refresh an existing build directory.
    $game = Join-Path $repo "out\build\win-amd64-release"
    if (Test-Path $game) {
        Copy-Item (Join-Path $install "rexruntime.dll"), (Join-Path $install "rexgpu-xenos.dll") $game -Force
    }
} else {
    "SDK already built: $install"
}
"SDK_READY"
