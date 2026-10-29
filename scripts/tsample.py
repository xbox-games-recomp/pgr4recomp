"""Sample one thread's instruction pointer (and a few return addresses) of a running process.

Usage: python -I scripts/tsample.py <pid> <tid> [seconds] [--exports]
Prints the share of samples per module and the hottest addresses as module+offset (or the nearest
export name with --exports). Windows x64 only; uses SuspendThread/GetThreadContext.
"""
import collections
import ctypes
import ctypes.wintypes as wt
import struct
import sys
import time

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)

THREAD_ALL = 0x001F03FF
PROCESS_ALL = 0x001F0FFF
CONTEXT_CONTROL = 0x00100001


class CONTEXT(ctypes.Structure):
    _pack_ = 16
    _fields_ = [('P1Home', ctypes.c_uint64 * 6), ('ContextFlags', wt.DWORD), ('MxCsr', wt.DWORD),
                ('Seg', wt.WORD * 6), ('EFlags', wt.DWORD), ('Dr', ctypes.c_uint64 * 6),
                ('Rax', ctypes.c_uint64), ('Rcx', ctypes.c_uint64), ('Rdx', ctypes.c_uint64),
                ('Rbx', ctypes.c_uint64), ('Rsp', ctypes.c_uint64), ('Rbp', ctypes.c_uint64),
                ('Rsi', ctypes.c_uint64), ('Rdi', ctypes.c_uint64), ('R8_15', ctypes.c_uint64 * 8),
                ('Rip', ctypes.c_uint64), ('rest', ctypes.c_byte * 976)]


def modules(hp):
    arr = (ctypes.c_void_p * 1024)()
    need = wt.DWORD()
    psapi.EnumProcessModulesEx(hp, arr, ctypes.sizeof(arr), ctypes.byref(need), 3)
    out = []
    for i in range(need.value // 8):
        base = arr[i]
        name = ctypes.create_unicode_buffer(260)
        psapi.GetModuleBaseNameW(hp, ctypes.c_void_p(base), name, 260)

        class MI(ctypes.Structure):
            _fields_ = [('base', ctypes.c_void_p), ('size', wt.DWORD), ('entry', ctypes.c_void_p)]
        mi = MI()
        psapi.GetModuleInformation(hp, ctypes.c_void_p(base), ctypes.byref(mi), ctypes.sizeof(mi))
        out.append((base, base + mi.size, name.value))
    return out


def read(hp, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not k32.ReadProcessMemory(hp, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return None
    return buf.raw[:got.value]


def exports(hp, base):
    """Sorted (rva, name) list from the module's export table, read from process memory."""
    hdr = read(hp, base, 0x1000)
    pe = struct.unpack_from('<I', hdr, 0x3C)[0]
    rva, size = struct.unpack_from('<II', hdr, pe + 24 + 112)
    if not rva:
        return []
    d = read(hp, base + rva, 40)
    nfun, nnames, afun, anames, aord = struct.unpack_from('<IIIII', d, 20)
    funcs = struct.unpack(f'<{nfun}I', read(hp, base + afun, 4 * nfun))
    names = struct.unpack(f'<{nnames}I', read(hp, base + anames, 4 * nnames))
    ords = struct.unpack(f'<{nnames}H', read(hp, base + aord, 2 * nnames))
    out = []
    for nrva, o in zip(names, ords):
        s = read(hp, base + nrva, 128).split(b'\0')[0].decode(errors='replace')
        out.append((funcs[o], s))
    return sorted(out)


def main():
    pid, tid = int(sys.argv[1]), int(sys.argv[2])
    secs = float(sys.argv[3]) if len(sys.argv) > 3 and not sys.argv[3].startswith('-') else 3.0
    hp = k32.OpenProcess(PROCESS_ALL, False, pid)
    ht = k32.OpenThread(THREAD_ALL, False, tid)
    mods = modules(hp)

    def where(a):
        for b, e, n in mods:
            if b <= a < e:
                return n, a - b
        return '?', a

    ctx = CONTEXT()
    ctx.ContextFlags = CONTEXT_CONTROL
    hits = collections.Counter()
    mod_hits = collections.Counter()
    end = time.time() + secs
    n = 0
    while time.time() < end:
        k32.SuspendThread(ht)
        ok = k32.GetThreadContext(ht, ctypes.byref(ctx))
        rip = ctx.Rip
        k32.ResumeThread(ht)
        if ok:
            m, off = where(rip)
            mod_hits[m] += 1
            hits[(m, off)] += 1
            n += 1
        time.sleep(0.0005)
    print(f'{n} samples')
    for m, c in mod_hits.most_common(12):
        print(f'{100 * c / n:5.1f}%  {m}')
    exp = {}
    if '--exports' in sys.argv:
        for b, e, name in mods:
            try:
                exp[name] = exports(hp, b)
            except Exception:
                exp[name] = []
    # Aggregate hot offsets into 256-byte buckets (or nearest export).
    agg = collections.Counter()
    for (m, off), c in hits.items():
        key = None
        if exp.get(m):
            import bisect
            i = bisect.bisect_right(exp[m], (off, '￿')) - 1
            if i >= 0:
                key = (m, exp[m][i][1])
        agg[key or (m, hex(off & ~0xFF))] += c
    for (m, k), c in agg.most_common(40):
        print(f'{100 * c / n:5.1f}%  {m} {k}')


main()
