// Game code patches applied through codegen mid-asm hooks (config/default.toml [[midasm_hook]]).
// Byte patches to guest memory do not reach recompiled code, so each patch is a hook on the
// instruction it replaces, switched by a cvar.

#include <rex/cvar.h>
#include <rex/ppc/context.h>

REXCVAR_DEFINE_BOOL(pgr4_60fps, true, "PGR4",
                    "Present every vblank (60 fps) instead of the game's PresentationInterval 2 (30 fps)");

// After `lwz r10,0x350C(r31)` in the D3D swap path (0x826957EC): the device's PresentationInterval,
// which the following code maps to the VdSwap interval. Same site as the Xenia Canary "60 FPS" patch.
void Pgr4PresentIntervalHook(PPCRegister& r10) {
  if (REXCVAR_GET(pgr4_60fps) && r10.u32 == 2) r10.u64 = 1;
}
