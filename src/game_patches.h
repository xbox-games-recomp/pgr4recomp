// Game code patches (see game_patches.cpp).

#pragma once

namespace pgr4 {

// Called before each guest VdSwap: with pgr4_adaptive_vsync, waits for the next 60 Hz slot.
void PaceGuestPresent();

}  // namespace pgr4
