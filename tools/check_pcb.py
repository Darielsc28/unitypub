#!/usr/bin/env python3
"""Mesures de controle sur le PCB route (largeurs mini par net, vias, distances cles)."""
import sys, math, collections
import pcbnew
from pcbnew import ToMM
b = pcbnew.LoadBoard(sys.argv[1])
OX, OY = 100.0, 60.0
w = collections.defaultdict(list); L = collections.Counter(); nv = collections.Counter(); lay = collections.defaultdict(set)
ymin = 1e9
for t in b.GetTracks():
    n = t.GetNetname()
    if t.Type() == pcbnew.PCB_VIA_T:
        nv[n] += 1; ymin = min(ymin, ToMM(t.GetPosition().y) - OY - 0.3)
    else:
        w[n].append(ToMM(t.GetWidth())); L[n] += ToMM(t.GetLength()); lay[n].add(b.GetLayerName(t.GetLayer()))
        ymin = min(ymin, ToMM(min(t.GetStart().y, t.GetEnd().y)) - OY)
print('net;largeur mini (mm);largeur maxi (mm);longueur (mm);vias;couches')
for n in sorted(set(w) | set(nv)):
    ws = w.get(n, [0])
    print('%s;%.2f;%.2f;%.1f;%d;%s' % (n, min(ws), max(ws), L[n], nv[n], '+'.join(sorted(lay[n]))))
print('pistes: %d, vias: %d' % (sum(len(v) for v in w.values()), sum(nv.values())))
print('cuivre route le plus haut : y = %.2f mm sous le bord haut de la carte' % ymin)
def pad(ref, num):
    p = b.FindFootprintByReference(ref).FindPadByNumber(num).GetPosition()
    return ToMM(p.x) - OX, ToMM(p.y) - OY
def d(a, c): return math.hypot(a[0] - c[0], a[1] - c[1])
for a, c, txt in [(('C6','1'),('U1','2'),'C6 -> U1.2 (3V3)'), (('C5','1'),('U1','2'),'C5 -> U1.2 (3V3)'), (('C9','1'),('U2','7'),'C9 -> U2.7 (VDD)'),
                  (('C8','1'),('U2','7'),'C8 -> U2.7 (VDD)'), (('C3','1'),('U4','1'),'C3 -> U4.1 (VIN)'), (('C4','1'),('U4','5'),'C4 -> U4.5 (VOUT)'),
                  (('C1','1'),('U3','4'),'C1 -> U3.4 (VDD)'), (('C2','1'),('U3','3'),'C2 -> U3.3 (VBAT)'), (('C7','1'),('U1','3'),'C7 -> U1.3 (EN)'),
                  (('C10','1'),('U1','7'),'C10 -> U1.7 (IO35)')]:
    print('distance entre centres de pastilles %s : %.2f mm' % (txt, d(pad(*a), pad(*c))))
u2 = b.FindFootprintByReference('U2').GetPosition(); j3 = b.FindFootprintByReference('J3').GetPosition()
print('U2 -> limite antenne (bord haut) : %.1f mm ; J3 -> bord haut : %.1f mm' % (ToMM(u2.y) - OY, ToMM(j3.y) - OY))
for z in b.Zones():
    print('zone', z.GetZoneName(), b.GetLayerName(z.GetLayer()), z.GetNetname(), 'aire remplie %.0f mm2' % (z.GetFilledArea() / 1e12))
