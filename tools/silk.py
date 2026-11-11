"""Serigraphie : references placees automatiquement + reperes fonctionnels."""
import pcbnew
from pcbnew import VECTOR2I_MM as V, FromMM, ToMM


def bbox(b):
    return (ToMM(b.GetLeft()), ToMM(b.GetTop()), ToMM(b.GetRight()), ToMM(b.GetBottom()))


def hit(a, b, m=0.0):
    return a[0] < b[2] + m and b[0] < a[2] + m and a[1] < b[3] + m and b[1] < a[3] + m


# reperes fonctionnels : (texte, x, y, taille, rotation)
LABELS = [
    ('RESET', 4.6, 27.0, 0.7), ('USER', 15.0, 27.0, 0.7), ('BOOT', 20.25, 25.0, 0.7, 90),
    ('TOUCH', 2.6, 14.5, 0.6),
    ('LRCK', 1.35, 18.1, 0.6), ('BCLK', 3.95, 18.1, 0.6),
    ('3V3', 23.2, 27.02, 0.6), ('GND', 25.9, 27.02, 0.6), ('DIN', 28.5, 27.02, 0.6),
    ('VBAT', 23.05, 33.35, 0.6), ('VSYS', 25.65, 33.35, 0.6),
    ('BAT', 4.5, 47.3, 0.8), ('+', 8.3, 39.02, 0.7), ('-', 8.2, 47.2, 0.9),
    ('HP', 25.5, 41.3, 0.8),
    ('ON', 5.4, 27.9, 0.6), ('OFF', 5.4, 35.4, 0.6),
    ('CHG', 11.6, 33.05, 0.6),
]
# barrette J4 : nom de chaque broche, a gauche des pastilles
J4_NAMES = ['3V3', 'GND', 'TX', 'RX', 'EN', 'IO0']


def run(board, fps, text, line, OX, OY, W, H):
    obstacles = []      # (bbox, proprietaire)
    for ref, fp in fps.items():
        for pad in fp.Pads():
            obstacles.append((bbox(pad.GetBoundingBox()), ref))
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        if ref == 'U1':
            # la cour de U1 inclut la zone d'exclusion d'antenne : on ne garde que le corps du module
            p = fp.GetPosition()
            obstacles.append(((ToMM(p.x) - 9.2, ToMM(p.y) - 12.9, ToMM(p.x) + 9.2, ToMM(p.y) + 13.6), ref))
        else:
            obstacles.append((bbox(c.BBox()), ref))
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS:
                obstacles.append((bbox(g.GetBoundingBox()), ref + '#silk'))
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_VIA_T:
            p = t.GetPosition()
            r = 0.35
            obstacles.append(((ToMM(p.x) - r, ToMM(p.y) - r, ToMM(p.x) + r, ToMM(p.y) + r), None))
    board_box = (OX + 0.2, OY + 0.2, OX + W - 0.2, OY + H - 0.2)
    placed = []
    V = pcbnew.VECTOR2I_MM

    def free(b, owner=None):
        if b[0] < board_box[0] or b[1] < board_box[1] or b[2] > board_box[2] or b[3] > board_box[3]:
            return False
        for ob, o in obstacles:
            if o != owner and hit(b, ob, 0.02):
                return False
        return not any(hit(b, p, 0.1) for p in placed)

    # 1) reperes fonctionnels (prioritaires)
    def put(s, x, y, size, just=None, rot=0):
        # cherche la position libre la plus proche du point demande
        t = text(s, x, y, size, just=just, rot=rot)
        hw, hh = 0.43 * size * len(s) + 0.05, 0.62 * size
        if rot:
            hw, hh = hh, hw
        b0 = (OX + x - hw, OY + y - hh, OX + x + hw, OY + y + hh)
        best = None
        for r in [k * 0.25 for k in range(0, 17)]:
            for dx, dy in ([(0, 0)] if r == 0 else [(r * cx, r * cy) for cx, cy in
                           ((0, -1), (0, 1), (-1, 0), (1, 0), (-.7, -.7), (.7, -.7), (-.7, .7), (.7, .7))]):
                b = (b0[0] + dx, b0[1] + dy, b0[2] + dx, b0[3] + dy)
                if free(b):
                    best = (dx, dy, b)
                    break
            if best:
                break
        if best:
            t.SetPosition(V(OX + x + best[0], OY + y + best[1]))
            placed.append(best[2])
        else:
            print('repere', s, ': pas de position libre, laisse en place', [round(v - o, 2) for v, o in zip(b0, (OX, OY, OX, OY))], [(o, [round(v, 2) for v in ob]) for ob, o in obstacles if hit(b0, ob, 0.05)][:3])
            placed.append(b0)
        return t

    for s, x, y, size, *r in LABELS:
        put(s, x, y, size, rot=r[0] if r else 0)
    p1 = fps['J4'].FindPadByNumber('1').GetPosition()
    for i, name in enumerate(J4_NAMES):
        put(name, ToMM(p1.x) - OX + 2.25, ToMM(p1.y) - OY + 2.54 * i, 0.6, rot=90)
    put('1', ToMM(p1.x) - OX - 2.2, ToMM(p1.y) - OY, 0.7)

    # 2) references : premiere position libre autour de la cour, sinon reportee sur F.Fab
    hidden = []
    for ref, fp in fps.items():
        r = fp.Reference()
        c = bbox(fp.GetCourtyard(pcbnew.F_CrtYd).BBox())
        if ref.startswith('TP'):
            r.SetLayer(pcbnew.F_Fab)      # les points de test portent le nom de leur signal
            continue
        if ref == 'U1':
            p = fp.GetPosition()
            r.SetPosition(V(ToMM(p.x), ToMM(p.y) + 9.0))
            r.SetTextAngleDegrees(0)
            r.SetTextSize(pcbnew.VECTOR2I(FromMM(0.8), FromMM(0.8)))
            continue
        cx, cy = (c[0] + c[2]) / 2, (c[1] + c[3]) / 2
        wl = 0.52 * len(ref) + 0.2
        hl = 0.8
        ok = False
        for ang in (0, 90):
            w, h = (wl, hl) if ang == 0 else (hl, wl)
            cands = []
            for d in (0.0, 0.35, 0.7, 1.1):
                for s in (0.0, -0.5, 0.5, -1.0, 1.0, -1.6, 1.6):
                    cands += [(cx + s, c[1] - h / 2 - d), (cx + s, c[3] + h / 2 + d),
                              (c[0] - w / 2 - d, cy + s), (c[2] + w / 2 + d, cy + s)]
            for x, y in cands:
                b = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
                if free(b, ref):
                    r.SetPosition(V(x, y))
                    r.SetTextAngleDegrees(ang)
                    placed.append(b)
                    ok = True
                    break
            if ok:
                break
        if not ok:
            r.SetLayer(pcbnew.F_Fab)
            r.SetPosition(V(cx, cy))
            hidden.append(ref)
    # titre et aide-memoire au dos
    text('OREILLETTE BT v1', 15.0, 30.0, 1.5, layer=pcbnew.B_SilkS)
    text('ESP32-WROOM-32E + MAX98357A', 15.0, 33.0, 0.8, layer=pcbnew.B_SilkS)
    text('J4: 1=3V3 2=GND 3=TX 4=RX 5=EN 6=IO0', 15.0, 35.5, 0.8, layer=pcbnew.B_SilkS)
    text('J2: 1=BAT+ 2=GND', 15.0, 37.5, 0.8, layer=pcbnew.B_SilkS)
    if hidden:
        print('references reportees sur F.Fab (pas de place en serigraphie) :', ' '.join(sorted(hidden)))
