// Frame stats at the guest present: window title fps / draws / triangles, a once-a-second summary
// and hitch logging. See frame_stats.h.

#include "frame_stats.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <mutex>

#include <intrin.h>
#include <windows.h>

#include <rex/cvar.h>
#include <rex/graphics/gpu_frame_stats.h>
#include <rex/logging.h>
#include <rex/ppc/context.h>

REXCVAR_DEFINE_INT32(pgr4_hitch_ms, 25, "PGR4",
                     "Log frames (guest present to present) longer than this many ms with a GPU / "
                     "guest breakdown; 0 = off");
REXCVAR_DEFINE_BOOL(pgr4_title_stats, true, "PGR4",
                    "Show fps, draws and triangles per frame in the window title");

namespace pgr4 {
namespace {

using rex::graphics::GpuFrameStats;

// Plain copy of the GPU counters at one instant.
struct GpuSnapshot {
  uint64_t swaps, draws, triangles, copies, pipelines, shaders, texture_loads, upload_bytes;
  uint64_t ns_idle, ns_draw, ns_pipeline, ns_textures, ns_shared_memory, ns_copy, ns_fence_wait,
      ns_swap;
  uint64_t texture_creates, ns_texture_create, ns_texture_load, wait_reg_mem_sleeps,
      ns_wait_reg_mem, invalidations, ns_invalidation;
};

const GpuFrameStats* GpuStats() {
  static const GpuFrameStats* stats = [] () -> const GpuFrameStats* {
    HMODULE dll = GetModuleHandleA("rexgpu-xenos.dll");
    auto fn = dll ? reinterpret_cast<rex::graphics::GpuFrameStatsFn>(
                        GetProcAddress(dll, "rex_gpu_frame_stats"))
                  : nullptr;
    const GpuFrameStats* s = fn ? fn() : nullptr;
    if (!s || s->size != sizeof(GpuFrameStats)) {
      REXKRNL_WARN("PGR4 frame stats: rex_gpu_frame_stats unavailable or mismatched; "
                   "draw / GPU counters off (rebuild the SDK with patches/rexglue-gpu-frame-stats.patch)");
      return nullptr;
    }
    return s;
  }();
  return stats;
}

GpuSnapshot Snapshot() {
  GpuSnapshot s{};
  if (const GpuFrameStats* g = GpuStats()) {
    auto r = [](const std::atomic<uint64_t>& v) { return v.load(std::memory_order_relaxed); };
    s = {r(g->swaps),   r(g->draws),         r(g->triangles),   r(g->copies),
         r(g->pipelines), r(g->shaders),     r(g->texture_loads), r(g->upload_bytes),
         r(g->ns_idle), r(g->ns_draw),       r(g->ns_pipeline), r(g->ns_textures),
         r(g->ns_shared_memory), r(g->ns_copy), r(g->ns_fence_wait), r(g->ns_swap),
         r(g->texture_creates), r(g->ns_texture_create), r(g->ns_texture_load),
         r(g->wait_reg_mem_sleeps), r(g->ns_wait_reg_mem), r(g->invalidations),
         r(g->ns_invalidation)};
  }
  return s;
}

GpuSnapshot Delta(const GpuSnapshot& a, const GpuSnapshot& b) {
  GpuSnapshot d;
  const uint64_t* pa = &a.swaps;
  const uint64_t* pb = &b.swaps;
  uint64_t* pd = &d.swaps;
  for (size_t i = 0; i < sizeof(GpuSnapshot) / sizeof(uint64_t); ++i) pd[i] = pa[i] - pb[i];
  return d;
}

double Ms(uint64_t ns) { return ns / 1e6; }

std::mutex sink_mutex;
std::function<void(const std::string&)> title_sink;
std::atomic<uint64_t> guest_fence_wait_ns{0};

// State of the presenting thread (VdSwap is only called from the guest render thread).
struct SwapState {
  uint64_t swaps = 0;
  uint64_t last_begin = 0;
  uint64_t last_guest_fence_wait = 0;
  uint64_t last_cycles = 0;  // QueryThreadCycleTime of the presenting thread
  uint64_t first_tsc = 0, first_ns = 0;
  GpuSnapshot last_gpu{};
  // Current one-second window.
  uint64_t window_start = 0, window_frames = 0, window_max_ns = 0, window_over = 0;
  uint64_t window_guest_cpu_ns = 0, window_guest_wait_ns = 0;
  GpuSnapshot window_gpu{};
} state;

}  // namespace

uint64_t NowNs() {
  return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
                      std::chrono::steady_clock::now().time_since_epoch())
                      .count());
}

void SetTitleSink(std::function<void(const std::string&)> sink) {
  std::lock_guard<std::mutex> lock(sink_mutex);
  title_sink = std::move(sink);
}

void AddGuestFenceWait(uint64_t ns) { guest_fence_wait_ns.fetch_add(ns, std::memory_order_relaxed); }

void OnSwapBegin() {
  SwapState& s = state;
  const uint64_t now = NowNs();
  const GpuSnapshot gpu = Snapshot();
  const uint64_t fence_wait = guest_fence_wait_ns.load(std::memory_order_relaxed);
  ULONG64 cycles = 0;
  QueryThreadCycleTime(GetCurrentThread(), &cycles);
  const uint64_t tsc = __rdtsc();
  if (!s.swaps++) {
    s.last_begin = s.window_start = s.first_ns = now;
    s.first_tsc = tsc;
    s.last_gpu = s.window_gpu = gpu;
    s.last_guest_fence_wait = fence_wait;
    s.last_cycles = cycles;
    return;
  }
  const uint64_t frame_ns = now - s.last_begin;
  const GpuSnapshot d = Delta(gpu, s.last_gpu);
  // Guest render thread: on-CPU time (thread cycles at the TSC rate) minus the fence spin-wait,
  // which spins on the CPU, is the guest's own work; the rest of the frame it was off the CPU
  // (kernel waits on other guest threads, preemption).
  const double tsc_per_ns = now > s.first_ns ? double(tsc - s.first_tsc) / (now - s.first_ns) : 3.0;
  const uint64_t frame_fence_wait = fence_wait - s.last_guest_fence_wait;
  const uint64_t on_cpu_ns = uint64_t((cycles - s.last_cycles) / std::max(tsc_per_ns, 0.1));
  const uint64_t guest_work_ns = on_cpu_ns > frame_fence_wait ? on_cpu_ns - frame_fence_wait : 0;
  const uint64_t guest_off_cpu_ns = frame_ns > on_cpu_ns ? frame_ns - on_cpu_ns : 0;
  s.last_cycles = cycles;
  s.window_guest_cpu_ns += guest_work_ns;
  s.window_guest_wait_ns += frame_fence_wait;
  const int32_t hitch_ms = REXCVAR_GET(pgr4_hitch_ms);
  if (hitch_ms > 0 && frame_ns > uint64_t(hitch_ms) * 1000000) {
    // GPU thread time since the last guest present; it runs behind the guest, so a GPU-side cause
    // can show in the frame after the long one too.
    REXKRNL_INFO(
        "PGR4 hitch swap #{}: {:.1f} ms (guest: work {:.1f}, fence wait {:.1f}, off CPU {:.1f}, "
        "{} invalidations {:.1f}) | GPU: {} swaps, "
        "idle {:.1f}, wait_reg_mem {:.1f} ({} sleeps), draw {:.1f} [pipeline {:.1f}, textures {:.1f} "
        "(create {:.1f}, load {:.1f}), copy {:.1f}], uploads {:.1f}, fence wait {:.1f}, swap {:.1f} "
        "ms; {} draws, {} copies, {} pipelines, {} shaders, {} textures created, {} loaded, "
        "{:.2f} MB uploaded",
        s.swaps - 1, Ms(frame_ns), Ms(guest_work_ns), Ms(frame_fence_wait), Ms(guest_off_cpu_ns),
        d.invalidations, Ms(d.ns_invalidation), d.swaps, Ms(d.ns_idle), Ms(d.ns_wait_reg_mem),
        d.wait_reg_mem_sleeps, Ms(d.ns_draw), Ms(d.ns_pipeline), Ms(d.ns_textures),
        Ms(d.ns_texture_create), Ms(d.ns_texture_load), Ms(d.ns_copy), Ms(d.ns_shared_memory),
        Ms(d.ns_fence_wait), Ms(d.ns_swap), d.draws, d.copies, d.pipelines, d.shaders,
        d.texture_creates, d.texture_loads, d.upload_bytes / 1048576.0);
  }
  s.window_frames++;
  s.window_max_ns = std::max(s.window_max_ns, frame_ns);
  if (hitch_ms > 0 && frame_ns > uint64_t(hitch_ms) * 1000000) s.window_over++;
  s.last_begin = now;
  s.last_gpu = gpu;
  s.last_guest_fence_wait = fence_wait;

  const uint64_t window_ns = now - s.window_start;
  if (window_ns >= 1000000000) {
    const GpuSnapshot w = Delta(gpu, s.window_gpu);
    const double fps = s.window_frames * 1e9 / window_ns;
    const uint64_t frames = std::max<uint64_t>(s.window_frames, 1);
    if (REXCVAR_GET(pgr4_title_stats)) {
      std::string title = fmt::format("{:.0f} fps, {} draws, {}k tris", fps, w.draws / frames,
                                      (w.triangles / frames + 500) / 1000);
      std::lock_guard<std::mutex> lock(sink_mutex);
      if (title_sink) title_sink(title);
    }
    if (hitch_ms > 0) {
      REXKRNL_INFO(
          "PGR4 frames: {:.1f} fps, max {:.1f} ms, {} over {} ms | per frame: {} draws, {}k tris, "
          "guest work {:.1f}, guest fence wait {:.1f}, {} invalidations {:.2f}, "
          "GPU idle {:.1f}, wait_reg_mem {:.1f}, draw {:.1f}, fence wait {:.1f} ms; this second: "
          "{} pipelines, {} textures created, {} loaded, {:.2f} MB uploaded",
          fps, Ms(s.window_max_ns), s.window_over, hitch_ms, w.draws / frames,
          (w.triangles / frames + 500) / 1000, Ms(s.window_guest_cpu_ns / frames),
          Ms(s.window_guest_wait_ns / frames), w.invalidations / frames,
          Ms(w.ns_invalidation / frames), Ms(w.ns_idle / frames),
          Ms(w.ns_wait_reg_mem / frames), Ms(w.ns_draw / frames), Ms(w.ns_fence_wait / frames),
          w.pipelines, w.texture_creates, w.texture_loads, w.upload_bytes / 1048576.0);
    }
    s.window_start = now;
    s.window_frames = s.window_max_ns = s.window_over = 0;
    s.window_guest_cpu_ns = s.window_guest_wait_ns = 0;
    s.window_gpu = gpu;
  }
}

}  // namespace pgr4

// The D3D layer's GPU fence spin-wait (db16cyc loop on the fence value); timed to separate guest
// waiting from guest work in long frames.
extern "C" void __imp__sub_82697970(PPCContext& __restrict ctx, uint8_t* base);
extern "C" void sub_82697970(PPCContext& __restrict ctx, uint8_t* base) {
  const uint64_t start = pgr4::NowNs();
  __imp__sub_82697970(ctx, base);
  pgr4::AddGuestFenceWait(pgr4::NowNs() - start);
}
