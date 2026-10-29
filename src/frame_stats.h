// Per-frame stats taken at each guest present (VdSwap): the window title's fps / draws / triangles
// and hitch logging (frames over pgr4_hitch_ms, with what the GPU command processor and the guest
// did in them). GPU counters come from rexgpu-xenos.dll's rex_gpu_frame_stats() export.

#pragma once

#include <functional>
#include <string>

namespace pgr4 {

// Called once a second from the presenting guest thread with the title suffix, e.g.
// "60 fps, 1850 draws, 412k tris" (per-frame averages over that second).
void SetTitleSink(std::function<void(const std::string&)> sink);

// Called before the original VdSwap on the presenting guest thread.
void OnSwapBegin();

// Guest time spent busy-waiting on D3D fences (sub_82697970), added by its override.
void AddGuestFenceWait(uint64_t ns);

uint64_t NowNs();

}  // namespace pgr4
