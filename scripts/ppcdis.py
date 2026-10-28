import struct, sys
d = open(sys.argv[1], 'rb').read(); BASE = 0x82000000
a0, a1 = int(sys.argv[2], 16), int(sys.argv[3], 16)
def dis(a, w):
    op = w >> 26; rs = (w >> 21) & 31; ra = (w >> 16) & 31; si = struct.unpack('>h', struct.pack('>H', w & 0xFFFF))[0]
    ds = struct.unpack('>h', struct.pack('>H', w & 0xFFFC))[0]
    if w == 0x4E800020: return 'blr'
    if w == 0x4E800420: return 'bctr'
    if (w & 0xFC1FFFFF) == 0x7C0802A6: return f'mflr r{rs}'
    if (w & 0xFC1FFFFF) == 0x7C0803A6: return f'mtlr r{rs}'
    if (w & 0xFC1FFFFF) == 0x7C000026: return f'mfcr r{rs}'
    if (w & 0xFC100FFF) == 0x7C000120: return f'mtcrf {(w>>12)&0xFF:#x},r{rs}'
    if op == 62 and w & 3 == 0: return f'std r{rs},{ds}(r{ra})'
    if op == 58 and w & 3 == 0: return f'ld r{rs},{ds}(r{ra})'
    if op == 36: return f'stw r{rs},{si}(r{ra})'
    if op == 32: return f'lwz r{rs},{si}(r{ra})'
    if op == 54: return f'stfd f{rs},{si}(r{ra})'
    if op == 50: return f'lfd f{rs},{si}(r{ra})'
    if op == 14: return f'addi r{rs},r{ra},{si}' if ra else f'li r{rs},{si}'
    if op == 18:
        li = w & 0x03FFFFFC; li = li - 0x04000000 if li & 0x02000000 else li
        return f'b{"l" if w & 1 else ""} {a + li:#x}'
    if op == 16: return f'bc {(w>>21)&31},{(w>>16)&31},{a + struct.unpack(">h", struct.pack(">H", w & 0xFFFC))[0]:#x}'
    if op == 31 and ((w >> 1) & 0x3FF) == 444: return f'or r{ra},r{rs},r{(w>>11)&31}'
    if op == 4: return 'vmx128/vmx'
    return f'.word {w:08x} (op {op})'
for a in range(a0, a1, 4):
    w = struct.unpack_from('>I', d, a - BASE)[0]
    print(f'{a:#x}: {w:08x}  {dis(a, w)}')
