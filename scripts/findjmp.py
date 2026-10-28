import struct, sys
d = open(sys.argv[1], 'rb').read()
BASE, T0, TS = 0x82000000, 0x82270000, 0x75001C
words = struct.unpack_from(f'>{TS//4}I', d, T0 - BASE)
def kind(w):
    op, rs, ra = w >> 26, (w >> 21) & 31, (w >> 16) & 31
    if ra != 3: return None
    if op in (62, 36) and rs >= 13 and ((op == 36) or (w & 3) == 0): return 'S'   # std/stw rN,(r3)
    if op in (58, 32) and rs >= 13 and ((op == 32) or (w & 3) == 0): return 'L'   # ld/lwz rN,(r3)
    if op == 54 and rs >= 14: return 's'   # stfd
    if op == 50 and rs >= 14: return 'l'   # lfd
    return None
i = 0
while i < len(words):
    k = kind(words[i])
    if k in ('S', 'L'):
        j, n, nf = i, 0, 0
        while j < len(words) and j - i < 80:
            kk = kind(words[j])
            if kk == k: n += 1
            elif kk == k.lower(): nf += 1
            j += 1
        if n >= 15:
            # back up to function start: previous blr
            s = i
            while s > 0 and words[s - 1] != 0x4E800020 and i - s < 16: s -= 1
            print(f"{'setjmp' if k=='S' else 'longjmp'}? run at {T0+i*4:#x} (start~{T0+s*4:#x}) gpr={n} fpr={nf} first={words[s]:08x}")
            i = j; continue
    i += 1
