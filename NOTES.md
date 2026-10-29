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

## 7. Scripted pad + first race (2026-10-28)

- `src/scripted_input.h`: synthetic pad driver added to the SDK's default input system when `PGR4_PAD` is set
  (synthetic devices route to guest user 0 and merge with a real pad). Syntax in the header, e.g.
  `$env:PGR4_PAD='~4@15:START,~4@17:A'; & scripts\run.ps1 menu1`. Presses are logged (`PGR4_PAD: t=..`).
- Run menu1 (START/A mashing): Dolby logo -> loading -> **first-run race** (Street Race, St Petersburg, Ford
  Sierra Cosworth RS500) with countdown, world, HUD and pause menu all rendering. A new profile starts in this
  race, not the front-end, so the menus come after it. No fatal errors in 2 min.
- Log noise, all optional/dev files: VehiclePvsData/*.dat, damagescripts/*.dms, dontship/textures, ai/*.ain,
  areas/frontend_mad.bpr, `SAVE:\buffer.save` (first run), `\Device\Image`, `IoDismountVolumeByFileHandle` stub,
  `XMPPlayTitlePlaylist: System playback is enabled!` (x17).

## 8. Live pad, autopilot, main menu reached (2026-10-28)

- Pad additions (`src/scripted_input.h`): `PGR4_PAD_FILE` live command file (re-read on mtime change, times
  relative to the change), analog channels `RT=0.6`, `LX=-0.4` etc., expired one-shot entries pruned.
- `scripts/goto_race.ps1 <tag>`: boot + START/A through the input-only black screens until the race car loads.
  Boot path for a fresh profile: intro -> **black screens that still take input** (START, A, A; likely title /
  profile / storage prompts that don't render -- open rendering bug) -> event card "Catch Me If You Can"
  (choose difficulty) -> St Petersburg street race (4 laps, Ford Sierra Cosworth).
- `scripts/autopilot.py`: drives by the HUD minimap. Traces the route line from the arrow tip (BFS, 2 px gap
  bridging; opponent dots sit on the line), steers at the point ~30 px along it, reads MPH digits with templates
  (`scripts/speed_digits.json` from `build_speed_templates.py`; no samples of 7/9 yet), speed target 75->25 mph by
  bend angle, three-point turn when <= 3 mph. `--debug` dumps the minimap mask. Reaches 60+ mph and gets round
  most of the lap; still gets pinned on the tight hairpins, so the race ended in TIMEOUT / DNF.
- After the race: Results (DNF) -> End of Race (Retry / Watch Replay / Go Back to Main Menu) -> **Main Menu**
  (Single Player / Multiplayer / PGR Shop). Everything on the way rendered correctly except the boot black screens.
- Gotcha: the autopilot's stop condition (speed HUD gone 5 s) misses the TIMEOUT screen, which keeps the speedo.

## Toolchain on this machine

clang 23.1.3 (`C:\Program Files\LLVM\bin`), CMake (`C:\Program Files\CMake\bin`, not on PATH), Python 3.10.
Xenia builds 2019-2023 under `G:\Emulators\Xbox 360 Emulator` (reference/ground truth).

## 9. Saves, title-server crash, front-end black screen (2026-10-28, later)

- **Saving works.** The SDK's user data root is `<Documents>\pgr4recomp` (here `D:\Documents\pgr4recomp`):
  `B13EBABEBABEBABE\4D5307F9\00000001\pgr4.save\{savegame,buffer.save}` + `Headers\...`, written after a race.
  The `SAVE:\buffer.save` miss in the log is the first-run probe only. Delete that folder to test a fresh profile.
- With a save present, boots crashed on most runs (`Unhandled guest access violation ... 0x70510008`) right after
  the front end. Cause: `XamCreateEnumeratorHandle` is an SDK stub returning ERROR_INVALID_PARAMETER; the online
  worker 0x82774C00 (XTitleServerCreateEnumerator wrapper 0x828FE270, app 0xFC, msg 0x58039, 212 extra bytes)
  treats the result as an HRESULT, enumerates INVALID_HANDLE_VALUE and `CloseHandle(-1)`s. Fixed in
  `src/xam_fixes.cpp` with a real empty enumerator (strong `__imp__` override in the exe, no SDK fork); 3/3 boots OK.
- `src/import_trace.cpp` (`$env:PGR4_TRACE_IMPORTS=1`): logs selected XAM calls with args, result and guest return
  addresses (lr + back-chain), plus every 30th `VdSwap` with the frontbuffer fetch constant.
- `scripts/boot_steps.ps1 <tag> 'START,A,WAIT,...' <delay> [cvars]`: one press per step, snapshot after each.
- **The boot "black screens" are not system UI.** No XamShow* call happens on them (the only one, a headless
  XamShowDeviceSelectorUI, comes later). Sequence with a save: intro -> (START) white fade -> title "PRESS START
  TO CONTINUE" (renders) -> (A) front end loads `frontend_mad.bpr` + Ferrari Enzo showroom car -> **black**, 30 s+,
  still takes input -> (A) race loads. VdSwap keeps running at 30 fps with the same frontbuffer, so the game is
  presenting frames that come out black (not a stall). `--readback_resolve=some` does not change it. The SDK has
  no cvar to pick the Vulkan backend (`any` = D3D12 first). Next: Xenia ground truth for this screen (needs a pad
  or a focused window for keyboard input), then GPU-side inspection of what the front end draws.

## 10. Black front end fixed: ROV render target path (2026-10-28)

- Exact sequence with a save: intro -> (START) title "PRESS START TO CONTINUE" -> (START) the title scene loads
  `frontend_mad.bpr` (missing, harmless) + Enzo, still showing the title -> (A) headless XamShowDeviceSelectorUI,
  profile content mount -> **Gamer Profiles "Your profile has been loaded"** dialog -> (A) Main Menu -> Single
  Player -> Arcade Mode -> "Catch Me If You Can" difficulty card -> St Petersburg race. Before the fix everything
  from the Gamer Profiles dialog on was black (pixel mean exactly 0) on the D3D12 default host render target path
  (`render_target_path_d3d12` "" -> RTV); that is also the fresh-profile "black input-only screens" of section 8.
- `--render_target_path_d3d12=rov` (EDRAM emulated in pixel shaders with rasterizer-ordered views) renders all of
  it, and runs at 30 fps in the menus and in the race (dips only while loading). `--gamma_render_target_as_unorm16=false`
  does not help, so it is not the 8_8_8_8_GAMMA emulation.
- Fix: `Pgr4recompApp::OnPreSetup` loads the GPU plugin itself (so the plugin's cvars are registered) and sets
  `render_target_path_d3d12=rov` unless the command line / config set it. `--render_target_path_d3d12=rtv`
  brings the bug back for comparison.
- RTV root cause not pinned down. `--log_level=debug` logs render target creation: no new RT is created when the
  dialog appears; the front end uses 2_10_10_10_FLOAT (fmt 3) RTs at 1x/2x/4x MSAA, 8_8_8_8 and a 80x8192
  16_16_16_16_FLOAT (fmt 7) + 32_FLOAT (fmt 14) pair at EDRAM base 0 (looks like a luminance/exposure chain).
  Hypothesis: RTV stores 2_10_10_10_FLOAT as R16G16B16A16_FLOAT, which keeps negatives/Inf/NaN that the real
  7e3 format clamps, so an exposure value goes NaN/0 and the whole tonemapped frame comes out black. Worth
  knowing for the native renderer: clamp HDR targets like the 7e3 format does.
- Gotcha: passing the same cvar twice makes the exe exit at startup with no log; `run.ps1` now drops its
  default `--log_level=info` when an explicit `--log_level=` is passed.

## 11. 60 fps, race performance, sky wedges, AA settings (2026-10-28)

- **60 fps.** `0x826957EC lwz r10,0x350C(r31)` in the D3D swap path loads the device PresentationInterval
  (PGR4: 2 = 30 fps) and maps it to the VdSwap interval. Same site as the Xenia Canary game-patches "60 FPS"
  patch (author illusion; its "Disable Motion Blur"/"Disable HDR" sites 0x829A9A9F/0x829A89EF are the `li r11,1`
  immediates and match this exe too). Byte patches do not reach recompiled code, so it is a codegen
  `[[midasm_hook]]` (`config/default.toml`, after_instruction) -> `Pgr4PresentIntervalHook` in
  `src/game_patches.cpp`, cvar `pgr4_60fps` (default true). Rerun `rexglue codegen` after editing hooks.
  Gameplay timing is real-time (race clock matches the 30 fps run); the patch notes say some videos may
  play at double speed.
- **Race perf.** With 60 fps unlocked, races ran 36-40 fps. Thread sampling (`scripts/tsample.py`): the guest
  render thread was 98% busy, ~45% of it spinning in the D3D fence poll `sub_82697970`; the GPU command
  processor thread was mostly idle-spinning. Culprit: the SDK cvar `clear_memory_page_state` (default true,
  ReXGlue addition, not upstream Xenia) drops every CPU-uploaded shared-memory page at each frame end, so all
  geometry/textures are re-uploaded each frame. Off -> locked ~60 fps, no visible difference (write watches
  still catch CPU writes). Now defaulted off in `OnPreSetup`. Benchmarks (`scripts/bench.ps1`, 960x540, RTX
  4080 SUPER): default 38/39, readback_memexport off 38, submit_on_primary_buffer_end off 38, vsync off 39,
  RTV 51/37, mrt clamp off 38, **clear_memory_page_state off 59-60**.
- **Sky wedges** (grey in St Petersburg day, black/orange at night): intermittent huge triangles; in the
  St Petersburg start-line view always fanning from the top of the Alexander Column toward the top-right
  screen edge. **Still open.** `scripts/sky_bench.ps1` (car parked on the start line, static camera, N
  snapshots; `sky_probe.py` counts frames whose sky deviates from the median) measures a ~3-6% frame rate:
  default 1/40, 3/60, 4/40; readback_memexport off 8/60; RTV 0/60; occlusion_query_enable=false 0/60 then
  6/120 (so not occlusion queries; the 0/60 runs were luck at this base rate, RTV is unproven too). Not
  clear_memory_page_state either (4/40 with it off). Vertex kill (OR mode -> position.w = NaN only) was not
  actually tested: the diagnostic DLL never reached the game folder (see gotcha below). Next: an SDK debug
  cvar to skip draws by VS/PS hash and bisect with sky_bench, or log draws whose CPU-executed VS output has
  w <= 0 / NaN (DrawExtentEstimator already runs VS on the CPU).
- **Graphics settings file.** The SDK loads `<exe dir>/pgr4recomp.toml` (flat `cvar = value`). The build
  copies `config/pgr4recomp.toml` there once (not overwritten): pgr4_60fps, resolution_scale (SSAA; the game's
  own EDRAM 2x/4x MSAA stays on), swap_post_effect (fxaa / fxaa_extreme), present_effect (bilinear/cas/fsr),
  anisotropic_override (5 = 16x).
- Gotchas: the game build only copies the SDK DLLs at configure time, so an SDK rebuild does not reach
  `out\build\...` by itself (a vertex-kill diagnostic silently never ran). `scripts/*.py` that use PIL must run
  without `-I` (PIL is in user site-packages); the PowerShell `python` lacks PIL entirely.
- One bench with `--resolution_scale=2` stopped presenting right after the front-end car loaded; a rerun was
  fine (title 52 fps, race 30-35 fps before the page-state fix; after it 55-59 fps at 2x). Watch for it.
