"""Routeur sur grille (A*) pour la carte oreillette_v1.

Aucun autorouteur n'etant disponible hors ligne, les pistes sont calculees ici :
  - grille de 0,05 mm, deplacements a 0/45/90 deg sur F.Cu et B.Cu, vias traversants 0,6/0,3 mm ;
  - GND et +3V3 ne sont pas routes en pistes : chaque pastille CMS rejoint par un court troncon un via
    vers le plan interne correspondant (In1.Cu = GND, In2.Cu = +3V3) ;
  - les isolements sont garantis par construction (obstacles gonfles de demi-largeur + isolement), puis
    verifies par le DRC de KiCad.
"""
import heapq, math
import numpy as np
import pcbnew
from pcbnew import VECTOR2I_MM as V, FromMM, ToMM

P = 0.05                 # pas de grille (mm)
CLR = 0.2                # isolement cuivre vise (regle mini du projet : 0,15)
MARGIN = 0.03            # marge de discretisation
EDGE = 0.35              # cuivre / bord de carte (regle : 0,30)
VIA_D, VIA_DRILL = 0.6, 0.3
VR = VIA_D / 2
VIA_COST = 500           # en dixiemes de pas : equivaut a 2,5 mm de piste

PLANE = {'GND': pcbnew.In1_Cu, '+3V3': pcbnew.In2_Cu}
WIDTH = {'VBUS': 0.6, 'VBAT': 0.6, 'VSYS': 0.6, 'VSW': 0.6, '/BAT_IN': 0.6,
         '/SPK_P': 0.5, '/SPK_N': 0.5, 'GND': 0.3, '+3V3': 0.4}
DEFAULT_W = 0.2
# pastilles de simple mesure / commande raccordees a un net de puissance : piste fine admise
NARROW = {('R11', '1'), ('TP2', '1'), ('TP3', '1'), ('R5', '1'), ('Q1', '1'), ('R4', '1')}
NARROW_W = 0.25
# sorties fines pre-tracees (pastilles au pas de 0,5 mm du TQFN) : ref, broche, largeur, polyligne relative
PREROUTE = [
    ('U2', '9', 0.25, [(0, 0), (0, 0.9), (-0.6, 1.5)]),
    ('U2', '10', 0.25, [(0, 0), (0, 0.9), (0.6, 1.5)]),
    ('U2', '7', 0.25, [(0, 0), (-1.3, 0)]),
    ('U2', '8', 0.25, [(0, 0), (-1.3, 0)]),
]
FORCED_VIA = [('U2', '17')]      # via thermique au centre du pad expose
# liaisons directes de decouplage tracees avant la descente vers les plans
DIRECT = [('U1', '2', 'C6', '1'), ('C6', '1', 'C5', '1'), ('U1', '1', 'C6', '2'), ('C6', '2', 'C5', '2'),
          ('U4', '5', 'C4', '1'), ('U4', '2', 'C3', '2')]
ORDER_FIRST = ['/SPK_N', '/SPK_P', 'VBUS', 'VSW', 'VSYS', 'VBAT', '/BAT_IN']
DIRS = [(0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (-1, 1)]   # (dj, di)


class Router:
    def __init__(self, board, fps, nets, ox, oy, w, h):
        self.board, self.fps, self.nets = board, fps, nets
        self.ox, self.oy, self.w, self.h = ox, oy, w, h
        self.NX, self.NY = int(round(w / P)) + 1, int(round(h / P)) + 1
        self.items = []          # (couches, net, forme, type, ref)
        self.holes = []          # (x, y, rayon)
        self.pads = {}           # (ref, broche) -> liste de dict
        self.log = []
        self.fail = []
        yy, xx = np.mgrid[0:self.NY, 0:self.NX]
        self.edge = (xx * P < 0) | (yy * P < 0)
        self._xx, self._yy = xx, yy
        for ref, fp in fps.items():
            for pad in fp.Pads():
                b = pad.GetBoundingBox()
                x0, y0, x1, y1 = (ToMM(b.GetLeft()) - ox, ToMM(b.GetTop()) - oy, ToMM(b.GetRight()) - ox, ToMM(b.GetBottom()) - oy)
                c = pad.GetPosition()
                cx, cy = ToMM(c.x) - ox, ToMM(c.y) - oy
                layers = ''.join(l for l, k in (('F', pcbnew.F_Cu), ('B', pcbnew.B_Cu)) if pad.IsOnLayer(k))
                net = pad.GetNetname() or None
                npth = pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
                tht = pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH
                drill = ToMM(max(pad.GetDrillSize().x, pad.GetDrillSize().y))
                if pad.GetShape(pcbnew.F_Cu) == pcbnew.PAD_SHAPE_CIRCLE:
                    shape = ('circ', cx, cy, (x1 - x0) / 2)
                else:
                    shape = ('rect', x0, y0, x1, y1)
                if npth:
                    self.items.append(('FB', None, ('circ', cx, cy, drill / 2), 'npth', ref))
                    self.holes.append((cx, cy, drill / 2))
                    continue
                if not layers:
                    continue          # pastille de pate seule
                self.items.append((layers, net, shape, 'tht' if tht else 'smd', ref))
                if tht:
                    self.holes.append((cx, cy, drill / 2))
                if net and pad.GetNumber():
                    self.pads.setdefault((ref, pad.GetNumber()), []).append(
                        dict(ref=ref, num=pad.GetNumber(), net=net, shape=shape, layers=layers, c=(cx, cy), tht=tht))

    # ---------------------------------------------------------- rasterisation
    def raster(self, m, shape, infl):
        NX, NY = self.NX, self.NY
        if shape[0] == 'rect':
            _, x0, y0, x1, y1 = shape
            i0, i1 = math.ceil((x0 - infl) / P - 1e-9), math.floor((x1 + infl) / P + 1e-9)
            j0, j1 = math.ceil((y0 - infl) / P - 1e-9), math.floor((y1 + infl) / P + 1e-9)
            if i1 < i0 or j1 < j0:
                return
            m[max(j0, 0):min(j1, NY - 1) + 1, max(i0, 0):min(i1, NX - 1) + 1] = True
            return
        if shape[0] == 'circ':
            _, cx, cy, r = shape
            ax, ay, bx, by = cx, cy, cx, cy
        else:
            _, ax, ay, bx, by, r = shape
        R = r + infl
        if R <= 0:
            return
        i0, i1 = max(math.floor((min(ax, bx) - R) / P), 0), min(math.ceil((max(ax, bx) + R) / P), NX - 1)
        j0, j1 = max(math.floor((min(ay, by) - R) / P), 0), min(math.ceil((max(ay, by) + R) / P), NY - 1)
        if i1 < i0 or j1 < j0:
            return
        X = self._xx[j0:j1 + 1, i0:i1 + 1] * P
        Y = self._yy[j0:j1 + 1, i0:i1 + 1] * P
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        if L2 == 0:
            d2 = (X - ax) ** 2 + (Y - ay) ** 2
        else:
            t = np.clip(((X - ax) * dx + (Y - ay) * dy) / L2, 0, 1)
            d2 = (X - ax - t * dx) ** 2 + (Y - ay - t * dy) ** 2
        m[j0:j1 + 1, i0:i1 + 1] |= d2 <= R * R + 1e-9

    def edge_mask(self, d):
        m = np.zeros((self.NY, self.NX), bool)
        k = int(math.ceil(d / P - 1e-9))
        m[:k, :] = True
        m[-k:, :] = True
        m[:, :k] = True
        m[:, -k:] = True
        return m

    def blocked(self, net, layer, hw):
        m = self.edge_mask(EDGE + hw)
        infl = hw + CLR + MARGIN
        for layers, n, shape, kind, ref in self.items:
            if layer in layers and n != net:
                self.raster(m, shape, infl)
        return m

    def via_blocked(self, net, in_pad_ok=None):
        m = self.edge_mask(EDGE + VR)
        for layers, n, shape, kind, ref in self.items:
            if n != net:
                self.raster(m, shape, VR + CLR + MARGIN)
            elif kind == 'smd' and shape is not in_pad_ok:
                self.raster(m, shape, VR + 0.02)          # pas de via dans une pastille CMS
        for x, y, r in self.holes:
            self.raster(m, ('circ', x, y, r), VIA_DRILL / 2 + 0.25 + MARGIN)
        return m

    def region(self, pad, layer):
        m = np.zeros((self.NY, self.NX), bool)
        if layer in pad['layers']:
            self.raster(m, pad['shape'], -0.05)
            if not m.any():
                j, i = int(round(pad['c'][1] / P)), int(round(pad['c'][0] / P))
                m[j, i] = True
        return m

    # ------------------------------------------------------------------- A*
    def search(self, sources, blocked, goal, viaok, hint=None, maxcost=None):
        """sources : liste (couche, j, i). Retourne la liste des noeuds (couche, j, i) ou None."""
        NX, NY = self.NX, self.NY
        g, parent = {}, {}
        heap = []

        def h(j, i):
            if hint is None:
                return 0
            a, b = abs(j - hint[0]), abs(i - hint[1])
            return 10 * max(a, b) + 4 * min(a, b)
        for s in sources:
            st = (s[0], s[1], s[2], -1)
            g[st] = 0
            heapq.heappush(heap, (h(s[1], s[2]), 0, st))
        while heap:
            f, c, st = heapq.heappop(heap)
            if c > g.get(st, 1 << 60):
                continue
            L, j, i, d = st
            if goal[L][j, i] and d != -1:
                path = [st]
                while st in parent:
                    st = parent[st]
                    path.append(st)
                return [(a, b, cc) for a, b, cc, _ in reversed(path)]
            if maxcost is not None and c > maxcost:
                return None
            bl = blocked[L]
            for nd, (dj, di) in enumerate(DIRS):
                nj, ni = j + dj, i + di
                if nj < 0 or ni < 0 or nj >= NY or ni >= NX or bl[nj, ni]:
                    continue
                if dj and di and (bl[j, ni] or bl[nj, i]):
                    continue
                nc = c + (14 if dj and di else 10)
                if d >= 0 and nd != d:
                    t = abs(nd - d)
                    t = min(t, 8 - t)
                    nc += 4 if t == 1 else 30      # penalise les coudes, surtout a 90 deg et plus
                ns = (L, nj, ni, nd)
                if nc < g.get(ns, 1 << 60):
                    g[ns] = nc
                    parent[ns] = st
                    heapq.heappush(heap, (nc + h(nj, ni), nc, ns))
            if viaok is not None and viaok[j, i]:
                L2 = 'B' if L == 'F' else 'F'
                if not blocked[L2][j, i]:
                    nc = c + VIA_COST
                    ns = (L2, j, i, 8)
                    if nc < g.get(ns, 1 << 60):
                        g[ns] = nc
                        parent[ns] = st
                        heapq.heappush(heap, (nc + h(j, i), nc, ns))
        return None

    # ---------------------------------------------------------------- sortie
    def add_track(self, net, layer, a, b, w):
        if a == b:
            return
        t = pcbnew.PCB_TRACK(self.board)
        t.SetStart(V(self.ox + a[0], self.oy + a[1]))
        t.SetEnd(V(self.ox + b[0], self.oy + b[1]))
        t.SetWidth(FromMM(w))
        t.SetLayer(pcbnew.F_Cu if layer == 'F' else pcbnew.B_Cu)
        t.SetNet(self.nets[net])
        self.board.Add(t)
        self.items.append((layer, net, ('seg', a[0], a[1], b[0], b[1], w / 2), 'track', None))

    def add_via(self, net, x, y):
        v = pcbnew.PCB_VIA(self.board)
        v.SetPosition(V(self.ox + x, self.oy + y))
        v.SetViaType(pcbnew.VIATYPE_THROUGH)
        v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetWidth(pcbnew.F_Cu, FromMM(VIA_D))
        v.SetDrill(FromMM(VIA_DRILL))
        v.SetNet(self.nets[net])
        self.board.Add(v)
        self.items.append(('FB', net, ('circ', x, y, VR), 'via', None))
        self.holes.append((x, y, VIA_DRILL / 2))

    def emit(self, net, path, w, tree):
        """Convertit un chemin de noeuds en pistes + vias et met a jour l'arbre du net."""
        k = 0
        n = len(path)
        while k < n - 1:
            L, j, i = path[k]
            L2, j2, i2 = path[k + 1]
            if L2 != L:
                self.add_via(net, round(i * P, 4), round(j * P, 4))
                tree['F'][j, i] = tree['B'][j, i] = True
                k += 1
                continue
            dj, di = j2 - j, i2 - i
            e = k + 1
            while e + 1 < n and path[e + 1][0] == L and (path[e + 1][1] - path[e][1], path[e + 1][2] - path[e][2]) == (dj, di):
                e += 1
            self.add_track(net, L, (round(i * P, 4), round(j * P, 4)), (round(path[e][2] * P, 4), round(path[e][1] * P, 4)), w)
            for q in range(k, e + 1):
                tree[L][path[q][1], path[q][2]] = True
            k = e

    def connect(self, net, pad, tree, w, plane=False, label=''):
        """Relie une pastille a l'arbre du net (ou, pour un net de plan, a un via vers le plan)."""
        widths = [x for x in dict.fromkeys([w, 0.4, 0.3, 0.25, 0.2]) if x <= w]
        for ww in widths:
            hw = ww / 2
            bl = {'F': self.blocked(net, 'F', hw), 'B': self.blocked(net, 'B', hw)}
            src = []
            for L in pad['layers']:
                reg = pad['region'][L] & ~bl[L]
                src += [(L, int(j), int(i)) for j, i in np.argwhere(reg)]
            if not src:
                continue
            vb = self.via_blocked(net)
            viaok = ~vb & ~bl['F'] & ~bl['B']
            if plane:
                # but : cellule deja reliee au plan, ou emplacement de via libre
                goal = {'F': tree['F'] | viaok, 'B': tree['B'] | viaok}
                path = self.search(src, bl, goal, None, None, maxcost=10 * int(8 / P))
            else:
                goal = tree
                pts = np.argwhere(tree['F'] | tree['B'])
                c = (pad['c'][1] / P, pad['c'][0] / P)
                hint = tuple(int(v) for v in pts[np.argmin((pts[:, 0] - c[0]) ** 2 + (pts[:, 1] - c[1]) ** 2)])
                path = self.search(src, bl, goal, viaok, hint)
            if path is None:
                continue
            self.emit(net, path, ww, tree)
            if plane:
                L, j, i = path[-1]
                if not tree[L][j, i] or len(path) == 1:
                    pass
                if viaok[j, i] and not self._has_via(i * P, j * P):
                    self.add_via(net, round(i * P, 4), round(j * P, 4))
                    tree['F'][j, i] = tree['B'][j, i] = True
            if ww != w:
                self.log.append('%s %s.%s : largeur reduite a %.2f mm (au lieu de %.2f)' % (net, pad['ref'], pad['num'], ww, w))
            for L in pad['layers']:
                tree[L] |= pad['region'][L]
            return True
        self.fail.append('%s : %s.%s non route %s' % (net, pad['ref'], pad['num'], label))
        return False

    def _has_via(self, x, y):
        return any(k == 'via' and abs(s[1] - x) < 1e-6 and abs(s[2] - y) < 1e-6 for _, _, s, k, _ in self.items)

    # ------------------------------------------------------------------- run
    def run(self):
        netpads = {}
        for key, lst in self.pads.items():
            for p in lst:
                p['region'] = {L: self.region(p, L) for L in 'FB'}
                netpads.setdefault(p['net'], []).append(p)
        empty = lambda: {'F': np.zeros((self.NY, self.NX), bool), 'B': np.zeros((self.NY, self.NX), bool)}
        trees = {n: empty() for n in netpads}
        extra = {}                       # cuivre pre-trace rattache a une pastille

        # 0) via thermique force
        for ref, num in FORCED_VIA:
            p = self.pads[(ref, num)][0]
            self.add_via(p['net'], p['c'][0], p['c'][1])
            for L in 'FB':
                trees[p['net']][L] |= p['region'][L]
        # 1) sorties fines pre-tracees
        for ref, num, w, rel in PREROUTE:
            p = self.pads[(ref, num)][0]
            pts = [(round(p['c'][0] + dx, 4), round(p['c'][1] + dy, 4)) for dx, dy in rel]
            for a, b in zip(pts, pts[1:]):
                self.add_track(p['net'], 'F', a, b, w)
                m = np.zeros((self.NY, self.NX), bool)
                self.raster(m, ('seg', a[0], a[1], b[0], b[1], 0.0), 0.03)
                p['region']['F'] |= m
        # 2) liaisons directes de decouplage
        for r1, n1, r2, n2 in DIRECT:
            a, b = self.pads[(r1, n1)][0], self.pads[(r2, n2)][0]
            t = empty()
            t['F'] |= b['region']['F']
            self.connect(a['net'], a, t, WIDTH.get(a['net'], DEFAULT_W), label='(liaison directe %s.%s)' % (r2, n2))
        # 3) nets
        sig = [n for n in netpads if n not in PLANE and len(netpads[n]) > 1 and not n.startswith('unconnected-')]

        def hpwl(n):
            xs = [p['c'][0] for p in netpads[n]]
            ys = [p['c'][1] for p in netpads[n]]
            return max(xs) - min(xs) + max(ys) - min(ys)
        rest = sorted([n for n in sig if n not in ORDER_FIRST], key=hpwl)
        local = [n for n in rest if hpwl(n) < 5.0]       # petits nets locaux (LED, PROG, CC...) avant la puissance
        rest = [n for n in rest if n not in local]
        for net in local + [n for n in ORDER_FIRST if n in sig]:
            self.route_net(net, netpads[net], trees[net])
        for net in PLANE:
            self.route_plane(net, netpads[net], trees[net])
        for net in rest:
            self.route_net(net, netpads[net], trees[net])

    def route_net(self, net, pads, tree):
        w = WIDTH.get(net, DEFAULT_W)
        # une entree par pastille physique (les pastilles homonymes d'une meme broche sont a relier aussi)
        todo = list(pads)
        wide = [p for p in todo if (p['ref'], p['num']) not in NARROW]
        first = wide[0] if wide else todo[0]
        todo.remove(first)
        done = [first]
        for L in first['layers']:
            tree[L] |= first['region'][L]
        while todo:
            cand = [p for p in todo if (p['ref'], p['num']) not in NARROW] or todo
            nxt = min(cand, key=lambda p: min(math.hypot(p['c'][0] - q['c'][0], p['c'][1] - q['c'][1]) for q in done))
            todo.remove(nxt)
            ww = NARROW_W if (nxt['ref'], nxt['num']) in NARROW and w > NARROW_W else w
            # deja relie (pastilles qui se touchent ou pre-trace aboutissant dans l'arbre) ?
            if not any((nxt['region'][L] & tree[L]).any() for L in nxt['layers']):
                self.connect(net, nxt, tree, ww)
            else:
                for L in nxt['layers']:
                    tree[L] |= nxt['region'][L]
            done.append(nxt)

    def route_plane(self, net, pads, tree):
        w = WIDTH[net]
        for p in pads:
            if p['tht']:
                for L in 'FB':
                    tree[L] |= p['region'][L]      # traversant : relie directement au plan interne
        # pastilles CMS : les plus grosses d'abord (decouplage), puis les autres
        smd = [p for p in pads if not p['tht']]
        for p in smd:
            if any((p['region'][L] & tree[L]).any() for L in p['layers']):
                continue
            self.connect(net, p, tree, w, plane=True)


def run(board, fps, nets, ox, oy, w, h):
    r = Router(board, fps, nets, ox, oy, w, h)
    r.run()
    for l in r.log:
        print('  note :', l)
    for l in r.fail:
        print('  ECHEC :', l)
    print('routage : %d echec(s)' % len(r.fail))
    return r
