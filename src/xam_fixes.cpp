// XAM exports that the SDK stubs in a way PGR4 cannot survive. Each is a strong definition of the
// `__imp__X` symbol the generated code calls, so the linker binds the game to it instead of the
// rexruntime.dll export (see import_trace.cpp for the same mechanism).

#include <rex/hook.h>
#include <rex/logging.h>
#include <rex/system/kernel_state.h>
#include <rex/system/xenumerator.h>
#include <rex/system/xtypes.h>
#include <rex/types.h>

namespace {

using namespace rex;
using namespace rex::system;

// SDK v0.10 returns X_ERROR_INVALID_PARAMETER. PGR4's online worker (0x82774C00) builds
// XTitleServerCreateEnumerator on this (app 0xFC, messages 0x58039/0x5803A, 212 extra bytes),
// tests the result as an HRESULT (>= 0 = success), then enumerates and CloseHandle()s its
// INVALID_HANDLE_VALUE default -- the current-process pseudo-handle -- which intermittently
// crashes the thread. Return a real, empty enumerator as an offline console would: the game
// reads the extra area via XamGetPrivateEnumStructureFromHandle and XamEnumerate reports
// ERROR_NO_MORE_FILES ("no title servers").
u32 XamCreateEnumeratorHandle(u32 user_index, u32 app_id, u32 open_message, u32 close_message,
                              u32 extra_size, u32 item_count, u32 flags, mapped_u32 out_handle) {
  auto e = object_ref<XStaticUntypedEnumerator>(
      new XStaticUntypedEnumerator(REX_KERNEL_STATE(), item_count, 0));
  const X_STATUS result =
      e->Initialize(user_index, app_id, open_message, close_message, flags, extra_size, nullptr);
  REXKRNL_INFO("XamCreateEnumeratorHandle(user={:X}, app={:X}, open={:X}, extra={:X}, items={}) -> {:X}",
               uint32_t(user_index), uint32_t(app_id), uint32_t(open_message), uint32_t(extra_size),
               uint32_t(item_count), result);
  if (XFAILED(result)) {
    return result;
  }
  *out_handle = e->handle();
  return X_ERROR_SUCCESS;
}

}  // namespace

REX_HOOK(__imp__XamCreateEnumeratorHandle, XamCreateEnumeratorHandle)
