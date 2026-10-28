import struct, sys, bisect
d = open(sys.argv[1], 'rb').read(); BASE = 0x82000000
f = []
for o in range(0x82241000 - BASE, 0x82241000 - BASE + 0x28F50, 8):
    s, i = struct.unpack_from('>II', d, o)
    if s: f.append((s, ((i >> 8) & 0x3FFFFF) * 4))
f.sort(); starts = [s for s, _ in f]
for q in sys.argv[2:]:
    a = int(q, 16); k = bisect.bisect_right(starts, a) - 1
    prev = f[k] if k >= 0 else None; nxt = f[k + 1] if k + 1 < len(f) else None
    inside = prev and prev[0] <= a < prev[0] + prev[1]
    print(f'{a:#x}: prev pdata {prev[0]:#x}+{prev[1]:#x} {"(INSIDE)" if inside else "(gap)"}  next {nxt[0]:#x}')
# biggest gaps in .text not covered by pdata
gaps = []
for (s, z), (n, _) in zip(f, f[1:]):
    if n - (s + z) > 0x1000: gaps.append((n - (s + z), s + z, n))
for g in sorted(gaps, reverse=True)[:8]: print(f'gap {g[0]:#x} bytes at {g[1]:#x}..{g[2]:#x}')
