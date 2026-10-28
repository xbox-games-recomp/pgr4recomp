import struct, sys, re
d = open(sys.argv[1], 'rb').read()
pe = struct.unpack_from('<I', d, 0x3C)[0]
assert d[pe:pe+4] == b'PE\0\0'
mach, nsec = struct.unpack_from('<HH', d, pe+4)
optsz = struct.unpack_from('<H', d, pe+20)[0]
print(f'machine={mach:#x} sections={nsec}')
s = pe + 24 + optsz
for i in range(nsec):
    name = d[s:s+8].split(b'\0')[0].decode()
    vsz, va, rsz, rptr = struct.unpack_from('<4I', d, s+8)
    ch = struct.unpack_from('<I', d, s+36)[0]
    print(f'  {name:9s} va={0x82000000+va:#010x} vsize={vsz:#9x} flags={ch:#010x}{"  CODE" if ch & 0x20000000 else ""}')
    s += 40
for pat in [rb'Bizarre[ -~]{0,40}', rb'PGR[ -~]{0,30}', rb'[Bb]uild[ -~]{4,40}20\d\d', rb'XNA[ -~]{0,20}', rb'Havok[ -~]{0,30}', rb'Bink[ -~]{0,30}', rb'Lua[ -~]{0,20}']:
    seen = sorted({m.group().decode() for m in re.finditer(pat, d)})[:6]
    if seen: print(pat.decode(), '->', seen)
