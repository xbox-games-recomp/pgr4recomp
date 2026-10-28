# PGR4 (Project Gotham Racing 4) static recompilation notes

Xbox 360 title: PowerPC (Xenon) + Xenos GPU. The original-Xbox toolkit used for mm3recomp/rsc2recomp
(xboxrecomp, x86 XBE) does not apply; candidate toolchains are XenonRecomp/XenosRecomp (code only, no runtime)
or the ReXGlue SDK (recompiler + Xenia-derived runtime, D3D12/Vulkan, Clang 18+).

## 1. Source dump

- ISO: `G:\Emulators\Xbox 360 Emulator\Games\Project Gotham Racing 4 [RF].iso` (7,835,492,352 bytes, XGD2).
- Game partition (XDVDFS) at 0xFD90000: `python -I scripts\xiso_extract.py <iso> ..\pgr4_files 0xFD90000`
  -> 1033 files, 6,190,859,772 bytes in `D:\Documents\Xbox Recompilation\pgr4_files` (junction `game_files`).
- Top level: `default.xex`, `gw.xex` (Geometry Wars: Waves, built as "Gw3pgr Release_NearlyFinal.exe"),
  `ai.pak`, `cultures.txt`, dirs `Camera Game Movies UI gw loc $SystemUpdate`.

## 2. default.xex fingerprint (`scripts\xexinfo.py`)

- Title ID 4D5307F9, media ID 0x5A381A4E, version 1, disc 1/1, region-free (0xFFFFFFFF).
- Image base 0x82000000, image size 0xD70000, entry 0x8267CA00, default stack 0x40000, TLS slots 0x40.
- File format: AES (retail key) + **basic** compression (no LZX). gw.xex uses LZX (window 0x8000).
- XDK 2.0.6132 static libs: XFFB XAPILIB D3D9 D3DX9 XBOXKRNL LIBCPMT XGRAPHC XONLINE XMP XAUD XHV.
- Imports: xam.xex (236 records), xboxkrnl.exe (339 records), min version 2.0.5766.

## 3. PE image (`scripts\xexdec.py` -> `work\default.pe`, `scripts\pesect.py`)

Decrypt: session key = AES-128-ECB-decrypt(retail key, security_info+0x150); payload AES-128-CBC IV 0; then
basic blocks (data_size, zero_size) from the 0x3FF header. Uses Git's `openssl.exe` (no Python AES installed).

| section | VA | size | |
|---|---|---|---|
| .rdata | 0x82000400 | 0x240BE8 | |
| .pdata | 0x82241000 | 0x28F50 | ~20.9k function entries |
| BINKBSS | 0x8226A000 | 0x4908 | |
| .text | 0x82270000 | 0x75001C | code |
| BINK | 0x829C0200 | 0x1043C | code (Bink video) |
| .data | 0x829E0000 | 0x20601C | |
| .XBMOVIE / BINKDATA / .XEXID / .idata / .XBLD / .reloc | 0x82BE6200.. | | |

Strings: "Bizarre Creations Limited", Lua 5.1 embedded, Bink movies.

## 4. ReXGlue SDK (chosen 2026-10-28)

- Source: `..\_ext\rexglue-sdk` = github.com/rexglue/rexglue-sdk `main` c94f5eb (== tag v0.10.0).
  The prebuilt `rexglue-sdk-0.10.0-win-amd64.zip` was blocked by Defender (`Trojan:Win32/Suschil!rfn`, heuristic),
  so the SDK is built from source: `scripts\build_sdk.bat` -> installs to `_ext\rexglue-sdk\out\install\win-amd64`
  (`bin\rexglue.exe`, `rexruntime.dll`, `rexgpu-xenos.dll`). The local build was not flagged.
- Windows checkout gotcha: git symlinks in submodules (libmspack `cabextract/mspack/*.c`, o1heap) arrive as
  one-line text files; replace each mode-120000 entry with a copy of its target before building.
- The wiki documents an older CLI. v0.10: `rexglue init --project-name N --xex-path assets/default.xex
  --game-root assets --project-root .` (xex must exist relative to cwd) -> `pgr4recomp_manifest.toml`
  (`[project]`, `[entrypoint]` with `includes`), not `*_config.toml`. Config keys (see `src/codegen/config.cpp`)
  are the same as the wiki's, but the exception-handler bool is `generate_exception_handlers`.
- Layout: `assets` = junction to `..\pgr4_files` (runtime default game root), overrides in `config/default.toml`,
  generated C++ in `generated/default` (ignored, ~138 MB, 269 files), build with `scripts\build.bat [release]`.
- Codegen: `rexglue codegen pgr4recomp_manifest.toml` from the repo root, ~16 s.

## 5. Codegen results

First pass (`--force`): 5 UnresolvedCall + 3 more at write time; all fixed in `config/default.toml`:
- 5 tail-call targets are leaf functions without .pdata (in gaps between .pdata ranges).
- 3 are an MSVC C++ EH layout: parent function, then catch funclets (`addi r31,r12,-N` prologue), then the
  parent's epilogue; the last funclet's .pdata length (0x80) covers the epilogue. Fix: funclet `end` = epilogue,
  epilogue = chunk with `parent`. Expect more of these if `generate_exception_handlers` is turned on.
Second pass: 0 analysis errors without `--force`. Only warning: 0x8256E8C0 (a real 0x16540-byte function per
.pdata) generates >1 MB of C++ (max_file_size_bytes).
Open: setjmp/longjmp not located (no CRT-shaped register-save leaf found by `findjmp` scans); check whether the
game's Lua 5.1 uses setjmp or C++ throw before relying on Lua error paths.

## 6. First boots (2026-10-28)

- Build: `scripts\build.bat` (~50 s full, generated code compiles fast with clang 23). Run: `& scripts\run.ps1 <tag>`
  -> windowed 960x540 (`--fullscreen=false`; SDK default is fullscreen), log in `work\<tag>.log`.
  Snapshot without focusing the window: `& scripts\snap.ps1 out.png` (PrintWindow PW_RENDERFULLCONTENT; a plain
  screen copy grabs whatever covers the window).
- `--game_data_root` is required (no positional path). The SDK's `gpu_plugin` cvar defaults to "" = no GPU;
  `Pgr4recompApp::OnPreSetup` now defaults it to `xenos` (D3D12, loads `rexgpu-xenos.dll`).
- Run 3 died: `[FATAL] Call to invalid or unregistered function at guest address 0x828FD7C0` = vtable forwarding
  stubs (`lwz r11,N(r11); mtctr; bctr`) with no .pdata, merged into one gap-fill function.
  Fix: `scripts\find_ptr_funcs.py` registers every .rdata/.data pointer into code not covered by .pdata
  (2912 entries) -> `config/ptr_funcs.toml` (generated; rerun it if the scan logic changes).
- Run 4: boots, D3D12 + audio up, plays the intro Bink movie for 2+ minutes (verified via snapshots), stays
  responsive. Not yet tried: skipping the intro / reaching the menus (needs pad input), races.
- Benign log noise: `GAME:\Game\Replay` access denied (write to read-only game dir; may matter for replays),
  missing `loc\*\lang.ini`, `debug_frontend.xml`, `d:\DebugOptions.ini`, `Vince\TestCreate.tmp` (dev probes).

## Toolchain on this machine

clang 23.1.3 (`C:\Program Files\LLVM\bin`), CMake (`C:\Program Files\CMake\bin`, not on PATH), Python 3.10.
Xenia builds 2019-2023 under `G:\Emulators\Xbox 360 Emulator` (reference/ground truth).
