#!/usr/bin/env python3
"""Genere oreillette_v1.kicad_pcb : placement, contour, plans, serigraphie et (option) routage.

A lancer avec l'interpreteur Python qui fournit le module pcbnew de KiCad 9 :
    python3 tools/gen_pcb.py <netlist exportee du schema> <sortie.kicad_pcb> [--route]
Coordonnees "locales" en mm : origine = coin haut-gauche de la carte, y vers le bas.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from pcbnew import VECTOR2I_MM as V, FromMM, ToMM
from sexpr import parse, find

NETLIST, OUT = sys.argv[1], sys.argv[2]
ROUTE = '--route' in sys.argv
FPDIR = os.environ.get('KICAD9_FOOTPRINT_DIR', '/usr/share/kicad/footprints')
OX, OY = 100.0, 60.0          # position de la carte sur la feuille
W, H = 30.0, 50.0             # dimensions de la carte

# ----------------------------------------------------------------- placement
# ref : (x, y, rotation)   -- voir VERIFICATION.md pour la justification
PLACE = {
    'U1': (15.0, 6.56, 0),      # antenne en debord du bord haut (6,2 mm hors carte)
    'J4': (27.1, 2.6, 0),       # barrette de programmation, bord droit
    'C6': (4.22, 2.1, 90), 'C5': (2.4, 2.1, 90),          # decouplage +3V3 colle aux broches 1/2 de U1
    'R7': (3.3, 4.9, 0), 'C7': (3.3, 6.5, 180),           # EN
    'C10': (3.3, 8.1, 180),                               # filtre ADC au ras de la broche IO35
    'TP1': (2.6, 11.5, 0),                                # pad tactile, bord gauche
    'TP7': (1.35, 16.3, 0), 'TP6': (3.95, 16.3, 0),
    'D3': (27.5, 17.95, 0), 'R10': (27.5, 19.55, 0),
    'SW2': (4.6, 23.4, 0), 'SW4': (15.0, 23.4, 0), 'SW3': (25.4, 23.4, 0),
    'R9': (9.8, 21.9, 270), 'C11': (9.8, 25.0, 270), 'R8': (20.25, 21.9, 270),
    'SW1': (2.2, 31.5, 270),
    'D1': (8.0, 29.5, 0), 'Q1': (8.0, 32.8, 0), 'R5': (11.6, 31.5, 0),
    'U4': (17.5, 30.5, 0), 'C3': (14.6, 30.5, 270), 'C4': (20.7, 29.9, 270),
    'D2': (11.6, 34.3, 0), 'R4': (14.7, 34.3, 180),
    'U3': (11.3, 37.0, 0), 'R3': (15.0, 36.0, 0), 'C2': (8.3, 37.0, 90), 'R6': (6.2, 37.9, 90),
    'C1': (11.3, 40.0, 180), 'R1': (14.2, 40.6, 90), 'R2': (15.8, 40.6, 90),
    'J2': (7.0, 42.0, 270), 'J1': (15.0, 46.6, 0), 'J3': (23.0, 46.3, 90),
    'U2': (25.0, 37.5, 270), 'C9': (21.3, 38.0, 180), 'C8': (21.2, 40.0, 180),
    'R13': (21.2, 34.57, 0), 'R14': (24.3, 34.57, 180),
    'TP4': (23.2, 28.9, 0), 'TP5': (25.9, 28.9, 0), 'TP8': (28.5, 28.9, 0),
    'TP2': (23.05, 31.6, 0), 'TP3': (25.65, 31.6, 0),
    'R11': (28.5, 31.75, 270), 'R12': (28.5, 34.85, 270),
}

# ------------------------------------------------------------------- netlist
nl = parse(open(NETLIST).read())
comps = {}
for c in find(find(nl, 'components')[0], 'comp'):
    g = lambda k: (find(c, k) or [[None, '']])[0][1]
    comps[g('ref')] = dict(value=g('value'), fp=g('footprint'), ts=g('tstamps'), desc=g('description'),
                           dnp=any(p[1][1] == 'dnp' for p in find(c, 'property') if isinstance(p[1], list)))
netof = {}
netnames = []
for n in find(find(nl, 'nets')[0], 'net'):
    name = find(n, 'name')[0][1]
    netnames.append(name)
    for x in find(n, 'node'):
        netof[(find(x, 'ref')[0][1], find(x, 'pin')[0][1])] = name
assert set(comps) == set(PLACE), set(comps) ^ set(PLACE)

# --------------------------------------------------------------------- carte
board = pcbnew.NewBoard(OUT)
board.SetCopperLayerCount(4)
ds = board.GetDesignSettings()
ds.SetBoardThickness(FromMM(1.6))
ds.m_HoleClearance = FromMM(0.25)
ds.m_CopperEdgeClearance = FromMM(0.3)
ds.m_MinClearance = FromMM(0.15)
ds.m_TrackMinWidth = FromMM(0.15)
ds.m_ViasMinSize = FromMM(0.5)
ds.m_MinThroughDrill = FromMM(0.2)
ds.m_HoleToHoleMin = FromMM(0.25)
tb = board.GetTitleBlock()
tb.SetTitle('Oreillette Bluetooth v1 - carte de validation')
tb.SetRevision('1.0')
tb.SetDate('2026-11-11')
tb.SetComment(0, '4 couches : F.Cu signal / In1.Cu GND / In2.Cu +3V3 / B.Cu signal')
nets = {}
for name in netnames:
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    nets[name] = ni

fps = {}
for ref, (x, y, rot) in PLACE.items():
    c = comps[ref]
    lib, name = c['fp'].split(':')
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + '.pretty'), name)
    assert fp is not None, c['fp']
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetReference(ref)
    fp.SetValue(c['value'])
    fp.SetPath(pcbnew.KIID_PATH('/' + c['ts']))
    fp.SetSheetname('/')
    fp.SetSheetfile('oreillette_v1.kicad_sch')
    fp.SetLibDescription(fp.GetLibDescription())
    fp.SetAttributes(fp.GetAttributes() & ~pcbnew.FP_EXCLUDE_FROM_BOM)   # coherent avec le schema
    if c['dnp']:
        fp.SetDNP(True)
    fp.SetPosition(V(OX + x, OY + y))
    fp.SetOrientationDegrees(rot)
    for pad in fp.Pads():
        n = netof.get((ref, pad.GetNumber()))
        if n:
            pad.SetNet(nets[n])
    board.Add(fp)
    fps[ref] = fp


def line(layer, pts, width=0.15, closed=False):
    if closed:
        pts = pts + [pts[0]]
    for a, b in zip(pts, pts[1:]):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(V(OX + a[0], OY + a[1]))
        s.SetEnd(V(OX + b[0], OY + b[1]))
        s.SetLayer(layer)
        s.SetWidth(FromMM(width))
        board.Add(s)


def text(s, x, y, size=0.8, layer=pcbnew.F_SilkS, rot=0, just=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(s)
    t.SetPosition(V(OX + x, OY + y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(FromMM(size), FromMM(size)))
    t.SetTextThickness(FromMM(max(0.1, size * 0.15)))
    if rot:
        t.SetTextAngleDegrees(rot)
    if just == 'left':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    if just == 'right':
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT)
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    board.Add(t)
    return t


# contour : rectangle 30 x 50 mm
line(pcbnew.Edge_Cuts, [(0, 0), (W, 0), (W, H), (0, H)], 0.1, closed=True)


def zone(layer, netname, name, pts=None):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(nets[netname])
    z.SetZoneName(name)
    o = z.Outline()
    o.NewOutline()
    for x, y in pts or [(0, 0), (W, 0), (W, H), (0, H)]:
        o.Append(FromMM(OX + x), FromMM(OY + y))
    z.SetMinThickness(FromMM(0.2))
    z.SetLocalClearance(FromMM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetThermalReliefGap(FromMM(0.25))
    z.SetThermalReliefSpokeWidth(FromMM(0.4))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    z.SetIsFilled(False)
    board.Add(z)
    return z


zone(pcbnew.In1_Cu, 'GND', 'Plan GND')
zone(pcbnew.In2_Cu, '+3V3', 'Plan +3V3')

# ---------------------------------------------------------------- references
# Les references sont reduites ; leur position est choisie plus bas (place_refs).
for fp in fps.values():
    r = fp.Reference()
    r.SetTextSize(pcbnew.VECTOR2I(FromMM(0.6), FromMM(0.6)))
    r.SetTextThickness(FromMM(0.1))
    r.SetKeepUpright(True)
    fp.Value().SetVisible(False) if fp.Value().GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) else None

if ROUTE:
    import route
    route.run(board, fps, nets, OX, OY, W, H)

import silk
silk.run(board, fps, text, line, OX, OY, W, H)

pcbnew.SaveBoard(OUT, board)
# rechargement avec les regles du projet (.kicad_pro) avant le remplissage des plans
board = pcbnew.LoadBoard(OUT)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
board.BuildConnectivity()
pcbnew.SaveBoard(OUT, board)
print('ecrit', OUT, len(board.GetFootprints()), 'empreintes', len(board.GetTracks()), 'pistes/vias')
