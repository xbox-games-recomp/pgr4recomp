# Project Gotham Racing 4 — Static Recompilation

![Racing in Macau](docs/macau_race.png)

A native Windows (x64) port of the Xbox 360 *Project Gotham Racing 4* (Bizarre Creations / Microsoft, 2007).
Every PowerPC function in the retail `default.xex` is translated to C++, compiled with Clang and linked against
a replacement Xbox 360 runtime; the Xenos command stream is rendered with Direct3D 12. No emulator CPU core,
interpreter or JIT.

Built on the [ReXGlue SDK](https://github.com/rexglue/rexglue-sdk) v0.10.0 (BSD-3-Clause, Xenia-derived) with
five local patches in `patches/`.

> **No game content is in this repository.** You need your own copy of the game. Everything derived from it
> (generated C++, builds, logs, snapshots) is git-ignored.

**Status:** intro movie, menus, saving and full races at a steady 60 fps with audio and a gamepad. Crowd
rendering has a workaround, not a fix (see [Open issues](#open-issues)).

## Quick start

1. Download `pgr4recomp-<version>-windows.zip` from this repository's releases and unzip it to a short path
   such as `C:\Games`.
2. Run `pgr4_launcher.exe`, choose your disc image or extracted game partition, press **Run setup**, then
   **Play**.

Setup installs the build tools with winget if needed (Visual Studio 2022 Community, LLVM, CMake, Git, in their
default folders), builds the SDK into `..\_ext\rexglue-sdk` **next to** the game folder (reused by later
installs), then generates and builds the game. Needs ~7 GB plus the SDK and build trees. The launcher's
[player guide](https://github.com/xbox-games-recomp/xbox-recomp-launcher#readme) covers each step and
troubleshooting.

## Game version

`config/default.toml` names guest addresses, so only this executable works:

| | |
|---|---|
| Title ID / Media ID | `4D5307F9` / `0x5A381A4E` (v1, disc 1/1, region-free, XDK 2.0.6132) |
| `default.xex` SHA-1 | `1a7e3b9ee84ef5f3ea1db66e6b1e3eb4f96b0cdd` (12,431,360 bytes) |

Extract the game partition of an XGD2 dump (1033 files) and link it as `assets`:

```bat
python -I scripts\xiso_extract.py "Project Gotham Racing 4.iso" ..\pgr4_files 0xFD90000
mklink /J assets ..\pgr4_files
```

## Building from source

Needs Windows 10/11, LLVM Clang 18+ and CMake 3.25+ in their default folders, Visual Studio 2022 Community
(C++ workload, for `vcvars64.bat`, the Windows SDK and Ninja), Git, and a Direct3D 12 GPU with
rasterizer-ordered views. `scripts\build.bat` and `scripts\build_sdk.bat` hard-code those folders.

```bat
powershell -ExecutionPolicy Bypass -File scripts\setup_sdk.ps1
..\_ext\rexglue-sdk\out\install\win-amd64\bin\rexglue.exe codegen pgr4recomp_manifest.toml
scripts\build.bat
```

1. `setup_sdk.ps1` clones the SDK at v0.10.0 into `..\_ext\rexglue-sdk`, replaces git symlinks that arrive as
   text files, applies the patches and runs `scripts\build_sdk.bat` (prints `SDK_BUILD_OK`).
2. Codegen (~16 s) writes `generated\default\`. Rerun it after editing `config/*.toml`.
3. `build.bat` (~50 s, prints `BUILD_OK`) produces `out\build\win-amd64-release\pgr4recomp.exe`. After
   rebuilding the SDK, copy `rexgpu-xenos.dll` and `rexruntime.dll` into that folder by hand.

## Running

`pgr4_launcher.exe` sets window size, fullscreen, 60 fps, resolution scale, AA, anisotropic filtering and log
level, passes them as cvars and logs to `work\play.log`; `--play` skips the window. Other cvars go in *Extra
arguments*. Starting the exe yourself, pass `--fullscreen=false` and never give a cvar twice (the exe exits
silently).

Saves go to `<Documents>\pgr4recomp`. The window title shows fps, draws and triangles.

Settings in `pgr4recomp.toml` next to the exe (copied from `config/` once; command-line flags win):

| Setting | Default | Effect |
|---|---|---|
| `pgr4_60fps` / `pgr4_adaptive_vsync` | `true` | 60 fps instead of the 30 fps lock; present at once and pace on the host |
| `resolution_scale` | `1` | Supersampling factor (2 holds 55–60 fps on an RTX 4080 SUPER) |
| `swap_post_effect` | `"fxaa"` | `"none"`, `"fxaa"`, `"fxaa_extreme"` |
| `present_effect` | `"bilinear"` | `"bilinear"`, `"cas"`, `"fsr"` |
| `anisotropic_override` | `5` | -1 game default, 0 off, 1..5 = 1×..16× |
| `pgr4_hitch_ms` | `25` | Log a breakdown of every frame slower than this; 0 = off |
| `pgr4_crowd_cull` | on | Hide crowd draws with scattered bones (sky-wedge workaround) |

The port also defaults `render_target_path_d3d12=rov`, `clear_memory_page_state=false` and
`x360_half_vertex_kill=true`.

**Controls:** the first XInput pad maps 1:1 to the Xbox 360 pad. `PGR4_PAD` / `PGR4_PAD_FILE` add a scripted
pad for test runs (syntax in `src/scripted_input.h`).

## How it works

```
default.xex ─► rexglue codegen ─► generated/default/*.cpp ─► Clang ─► pgr4recomp.exe
               (.pdata bounds + config/*.toml overrides)       + src/   loads rexruntime.dll, rexgpu-xenos.dll
```

- **`config/ptr_funcs.toml`** lists 2,912 entry points reached only through data pointers;
  **`config/default.toml`** holds hand-checked fixes and the 60 fps present hook (byte patches don't reach
  recompiled code).
- **`src/`** sets the PGR4 defaults, adds the 60 fps hook and adaptive vsync, fixes
  `XamCreateEnumeratorHandle` (crash at boot with a save), and collects frame stats.
- **`patches/`** add draw debugging, GPU frame stats, pooled texture heaps and two half-float fixes to the SDK.
  Regenerate one with `git -C ..\_ext\rexglue-sdk diff -- <files>`.

`NOTES.md` is the engineering log (every bug, cause and fix). `scripts\dev\` (`run.ps1`, `snap.ps1`, `boot_steps.ps1`, ...),
`autopilot.py` and `hitch_stats.py` drive and measure test runs.

## Open issues

1. **Sky wedges / crowd skeletons:** crowd bones come out scattered, most likely a recompiled-CPU bug in the
   crowd animation. `pgr4_crowd_cull` hides it.
2. ~1.3 µs GPU command-processor cost per draw leaves little headroom in dense views.
3. One 70–100 ms frame at race start while ~570 textures are created.
4. The default RTV render-target path renders the front end black, so ROV is used.
5. Lua error paths, Xbox Live / System Link and *Geometry Wars: Waves* are untested.

## Legal

An independent, non-commercial preservation project, not affiliated with Microsoft, Xbox Game Studios,
Bizarre Creations or any car manufacturer. *Project Gotham Racing* is the property of its owners. Do not open
issues or pull requests containing game files or generated code. The ReXGlue SDK is BSD-3-Clause; the patches
modify it under that license.
