// Game code patches applied through codegen mid-asm hooks (config/default.toml [[midasm_hook]]).
// Byte patches to guest memory do not reach recompiled code, so each patch is a hook on the
// instruction it replaces, switched by a cvar.

#include "game_patches.h"

#include <windows.h>

#include <rex/cvar.h>
#include <rex/ppc/context.h>

#include "frame_stats.h"

REXCVAR_DEFINE_BOOL(pgr4_60fps, true, "PGR4",
                    "Present every vblank (60 fps) instead of the game's PresentationInterval 2 (30 fps)");
REXCVAR_DEFINE_BOOL(pgr4_adaptive_vsync, true, "PGR4",
                    "With pgr4_60fps: present immediately and pace to 60 fps on the host, so a frame "
                    "that misses the 16.7 ms vblank by a little shows at ~17 ms instead of waiting "
                    "for the next vblank (33 ms); false = wait for the guest vblank");

namespace {
constexpr uint32_t kPresentIntervalImmediate = 0x80000000;  // D3DPRESENT_INTERVAL_IMMEDIATE
bool adaptive_active = false;  // set by the hook, read by PaceGuestPresent (same guest thread)
}  // namespace

// After `lwz r10,0x350C(r31)` in the D3D swap path (0x826957EC): the device's PresentationInterval,
// which the following code maps to the VdSwap interval (IMMEDIATE -> 0, no vblank wait). Same site
// as the Xenia Canary "60 FPS" patch.
void Pgr4PresentIntervalHook(PPCRegister& r10) {
  adaptive_active = false;
  if (REXCVAR_GET(pgr4_60fps) && r10.u32 == 2) {
    adaptive_active = REXCVAR_GET(pgr4_adaptive_vsync);
    r10.u64 = adaptive_active ? kPresentIntervalImmediate : 1;
  }
}

namespace pgr4 {

// Holds presents to a 60 Hz schedule when the swap no longer waits for vblank. A late present goes
// out at once; the schedule then resyncs, at most one period of debt is carried so the average
// stays at 60 fps without bursts.
void PaceGuestPresent() {
  if (!adaptive_active) return;
  constexpr uint64_t kPeriodNs = 1000000000 / 60;
  static uint64_t target = 0;
  static HANDLE timer =
      CreateWaitableTimerExW(nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
  uint64_t now = NowNs();
  target += kPeriodNs;
  if (now >= target) {
    if (now - target > kPeriodNs) target = now;
    return;
  }
  // Sleep to ~1 ms before the target on the high-resolution timer, then spin the rest.
  if (timer && target - now > 1500000) {
    LARGE_INTEGER due;
    due.QuadPart = -int64_t((target - now - 1000000) / 100);
    if (SetWaitableTimer(timer, &due, 0, nullptr, nullptr, FALSE)) {
      WaitForSingleObject(timer, INFINITE);
    }
  }
  while (NowNs() < target) YieldProcessor();
}

}  // namespace pgr4
