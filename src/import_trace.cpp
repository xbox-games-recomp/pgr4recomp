// Import tracer: logs guest calls to selected XAM exports (args r3..r8 and the r3 result) when
// PGR4_TRACE_IMPORTS is set. Each wrapper is a strong definition of the `__imp__X` symbol the generated
// code calls, so the linker binds the game to it instead of the rexruntime.dll export; the original
// is fetched from the DLL by name. Each import logs its first 40 calls only.

#include <atomic>
#include <cstdlib>
#include <string>

#include <windows.h>

#include <rex/logging.h>
#include <rex/ppc/context.h>

namespace {

using GuestFn = void (*)(PPCContext&, uint8_t*);

bool TraceEnabled() {
  static const bool enabled = std::getenv("PGR4_TRACE_IMPORTS") != nullptr;
  return enabled;
}

GuestFn ResolveOriginal(const char* name) {
  HMODULE dll = GetModuleHandleA("rexruntime.dll");
  return dll ? reinterpret_cast<GuestFn>(GetProcAddress(dll, name)) : nullptr;
}

void CallTraced(const char* name, GuestFn original, std::atomic<int>& count, PPCContext& ctx,
                uint8_t* base) {
  const bool log = TraceEnabled() && count.fetch_add(1) < 40;
  const uint32_t a[6] = {ctx.r3.u32, ctx.r4.u32, ctx.r5.u32, ctx.r6.u32, ctx.r7.u32, ctx.r8.u32};
  const uint32_t lr = uint32_t(ctx.lr), sp = ctx.r1.u32;
  original(ctx, base);
  if (log) {
    // Guest return addresses: lr, then the saved lr (-8 from each back-chain frame).
    std::string stack = fmt::format("{:08X}", lr);
    uint32_t frame = sp;
    for (int i = 0; i < 8; ++i) {
      MEMORY_BASIC_INFORMATION mi;  // the top frame's back-chain can point at the unmapped stack end
      if (!VirtualQuery(base + frame, &mi, sizeof(mi)) || mi.State != MEM_COMMIT ||
          (mi.Protect & (PAGE_NOACCESS | PAGE_GUARD))) {
        break;
      }
      const uint32_t next = __builtin_bswap32(*reinterpret_cast<uint32_t*>(base + frame));
      if (next <= frame || next - frame > 0x4000) break;  // end of chain (top frame holds garbage)
      frame = next;
      stack += fmt::format(" {:08X}", __builtin_bswap32(*reinterpret_cast<uint32_t*>(base + frame - 8)));
    }
    REXKRNL_INFO("TRACE {}({:08X}, {:08X}, {:08X}, {:08X}, {:08X}, {:08X}) -> {:08X} [{}]", name + 7,
                 a[0], a[1], a[2], a[3], a[4], a[5], ctx.r3.u32, stack);
  }
}

}  // namespace

#define PGR4_TRACE_IMPORT(fn)                                                  \
  extern "C" void __imp__##fn(PPCContext& __restrict ctx, uint8_t* base) {    \
    static const GuestFn original = ResolveOriginal("__imp__" #fn);            \
    static std::atomic<int> count{0};                                          \
    CallTraced("__imp__" #fn, original, count, ctx, base);                     \
  }

PGR4_TRACE_IMPORT(XamShowSigninUI)
PGR4_TRACE_IMPORT(XamShowDeviceSelectorUI)
PGR4_TRACE_IMPORT(XamShowMessageBoxUIEx)
PGR4_TRACE_IMPORT(XamShowKeyboardUI)
PGR4_TRACE_IMPORT(XamShowDirtyDiscErrorUI)
PGR4_TRACE_IMPORT(XamUserGetSigninState)
PGR4_TRACE_IMPORT(XamUserGetSigninInfo)
PGR4_TRACE_IMPORT(XamUserGetXUID)
PGR4_TRACE_IMPORT(XamUserCheckPrivilege)
PGR4_TRACE_IMPORT(XamUserReadProfileSettings)
PGR4_TRACE_IMPORT(XamUserWriteProfileSettings)
PGR4_TRACE_IMPORT(XamContentCreateEx)
PGR4_TRACE_IMPORT(XamContentClose)
PGR4_TRACE_IMPORT(XamContentFlush)
PGR4_TRACE_IMPORT(XamContentDelete)
PGR4_TRACE_IMPORT(XamContentGetDeviceState)
PGR4_TRACE_IMPORT(XamContentGetDeviceData)
PGR4_TRACE_IMPORT(XamContentCreateEnumerator)
PGR4_TRACE_IMPORT(XamEnumerate)
PGR4_TRACE_IMPORT(XamNotifyCreateListener)
PGR4_TRACE_IMPORT(XNotifyGetNext)
PGR4_TRACE_IMPORT(XamUserCreateAchievementEnumerator)
PGR4_TRACE_IMPORT(XamUserCreateStatsEnumerator)
