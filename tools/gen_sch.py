#!/usr/bin/env python3
"""Genere oreillette_v1.kicad_sch (KiCad 9) a partir d'une description par blocs.

Toutes les coordonnees sont exprimees en pas de 1,27 mm (50 mil).
Usage : python3 tools/gen_sch.py <dossier symboles KiCad> <sortie.kicad_sch>
"""
import sys, os, copy, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, dump, S, Sym, find

SYMDIR = sys.argv[1]
OUT = sys.argv[2]
PROJECT = 'oreillette_v1'
NS = uuid.UUID('6f3a1c1e-0000-4000-8000-0000000000aa')
_n = [0]


def uid(tag=''):
    _n[0] += 1
    return str(uuid.uuid5(NS, '%s-%d' % (tag, _n[0])))


ROOT = str(uuid.uuid5(NS, 'root'))
G = 1.27


def mm(v):
    return round(v * G, 4)


# ----------------------------------------------------------------- libraries
_libs = {}
lib_symbols = {}
pin_db = {}


def load_lib(lib):
    if lib not in _libs:
        _libs[lib] = parse(open(os.path.join(SYMDIR, lib + '.kicad_sym')).read())
    return _libs[lib]


def get_symbol(lib_id):
    """Retourne le symbole de bibliotheque aplati (heritage 'extends' resolu)."""
    if lib_id in lib_symbols:
        return lib_symbols[lib_id]
    lib, name = lib_id.split(':')
    L = load_lib(lib)

    def raw(n):
        return [s for s in find(L, 'symbol') if s[1] == n][0]
    s = copy.deepcopy(raw(name))
    ext = find(s, 'extends')
    if ext:
        parent = copy.deepcopy(raw(ext[0][1]))
        pname = parent[1]
        out = [Sym('symbol'), name]
        for e in parent[2:]:
            if isinstance(e, list) and e[0] == 'property':
                continue
            if isinstance(e, list) and e[0] == 'symbol':
                e[1] = name + e[1][len(pname):]
            out.append(e)
        props = find(s, 'property')
        # proprietes de l'enfant inserees avant les sous-symboles
        idx = next(i for i, e in enumerate(out) if isinstance(e, list) and e[0] == 'symbol')
        out[idx:idx] = props
        s = out
    s[1] = lib_id
    pins = {}
    for u in find(s, 'symbol'):
        for p in find(u, 'pin'):
            at = find(p, 'at')[0]
            num = find(p, 'number')[0][1]
            pins[num] = (round(float(at[1]) / G), round(float(at[2]) / G))
    lib_symbols[lib_id] = s
    pin_db[lib_id] = pins
    return s


# ------------------------------------------------------------------ elements
OX = [0]  # decalage horizontal du bloc courant (en pas)
items = []
wires = []
pin_points = set()
pwr_count = [0]
flg_count = [0]


def xf(px, py, x, y, rot, mirror):
    if mirror == 'y':
        px = -px
    if rot == 0:
        return (x + px, y - py)
    if rot == 90:
        return (x - py, y - px)
    if rot == 180:
        return (x - px, y + py)
    if rot == 270:
        return (x + py, y + px)
    raise ValueError(rot)


def prop(name, val, x, y, ang=0, hide=False, just=None):
    eff = S('effects', S('font', S('size', 1.27, 1.27)))
    if just:
        eff.append(S('justify', *[Sym(j) for j in just.split()]))
    if hide:
        eff.append(S('hide', Sym('yes')))
    return S('property', name, val, S('at', mm(x), mm(y), ang), eff)


def place(ref, lib_id, x, y, rot=0, value='', fp='', desc='', mirror=None,
          refpos=None, valpos=None, dnp=False, ds='~', power=False, just='left'):
    get_symbol(lib_id)
    local = {n: xf(px, py, x, y, rot, mirror) for n, (px, py) in pin_db[lib_id].items()}
    x += OX[0]
    pins = {n: (p[0] + OX[0], p[1]) for n, p in local.items()}
    fa = 0 if rot in (0, 180) else 90
    if refpos is None:
        refpos = (x + 2 - OX[0], y - 1) if rot in (0, 180) else (x - OX[0], y - 2)
    if valpos is None:
        valpos = (x + 2 - OX[0], y + 1) if rot in (0, 180) else (x - OX[0], y + 2)
    j = just if rot in (0, 180) else None
    # un symbole tourne de 180 deg inverse la justification affichee
    if rot == 180 and j:
        j = {'left': 'right', 'right': 'left'}[j]
    e = S('symbol', S('lib_id', lib_id), S('at', mm(x), mm(y), rot))
    if mirror:
        e.append(S('mirror', Sym(mirror)))
    e += [S('unit', 1), S('exclude_from_sim', Sym('no')), S('in_bom', Sym('no' if power else 'yes')),
          S('on_board', Sym('yes')), S('dnp', Sym('yes' if dnp else 'no')), S('uuid', uid(ref)),
          prop('Reference', ref, refpos[0] + OX[0], refpos[1], fa, hide=power, just=j),
          prop('Value', value, valpos[0] + OX[0], valpos[1], fa, just=j if not power else None),
          prop('Footprint', fp, x, y, 0, hide=True),
          prop('Datasheet', ds, x, y, 0, hide=True),
          prop('Description', desc, x, y, 0, hide=True)]
    for n in pins:
        e.append(S('pin', n, S('uuid', uid(ref + n))))
    e.append(S('instances', S('project', PROJECT, S('path', '/' + ROOT, S('reference', ref), S('unit', 1)))))
    items.append(e)
    for p in pins.values():
        pin_points.add(p)
    return local


def wire(*pts):
    for a, b in zip(pts, pts[1:]):
        assert a[0] == b[0] or a[1] == b[1], (a, b)
        if a != b:
            wires.append(((a[0] + OX[0], a[1]), (b[0] + OX[0], b[1])))


def power(name, pt, rot=0):
    pwr_count[0] += 1
    ref = '#PWR%03d' % pwr_count[0]
    dy = {0: (2.8 if name == 'GND' else -2.8), 180: (-2.8 if name == 'GND' else 2.8)}.get(rot, 0)
    place(ref, 'power:' + name, pt[0], pt[1], rot, value=name, power=True,
          valpos=(pt[0], pt[1] + dy), just=None, desc='Symbole d\'alimentation')


def gnd(pt):
    power('GND', pt)


def flag(pt, rot=0):
    flg_count[0] += 1
    ref = '#FLG%03d' % flg_count[0]
    place(ref, 'power:PWR_FLAG', pt[0], pt[1], rot, value='PWR_FLAG', power=True,
          valpos=(pt[0], pt[1] - 3.2 if rot == 0 else pt[1] + 3.2), just=None, desc='Drapeau d\'alimentation')


_DIR = {'R': (0, 'left'), 'L': (180, 'right'), 'U': (90, 'left'), 'D': (270, 'right')}


def glabel(name, pt, d='R'):
    ang, j = _DIR[d]
    items.append(S('global_label', name, S('shape', Sym('passive')), S('at', mm(pt[0] + OX[0]), mm(pt[1]), ang),
                   S('effects', S('font', S('size', 1.27, 1.27)), S('justify', Sym(j))), S('uuid', uid('gl' + name)),
                   S('property', 'Intersheetrefs', '${INTERSHEET_REFS}', S('at', mm(pt[0] + OX[0]), mm(pt[1]), 0),
                     S('effects', S('font', S('size', 1.27, 1.27)), S('hide', Sym('yes'))))))


def label(name, pt, d='R'):
    ang, j = _DIR[d]
    items.append(S('label', name, S('at', mm(pt[0] + OX[0]), mm(pt[1]), ang),
                   S('effects', S('font', S('size', 1.27, 1.27)), S('justify', Sym(j), Sym('bottom'))),
                   S('uuid', uid('l' + name))))


def nc(pt):
    items.append(S('no_connect', S('at', mm(pt[0] + OX[0]), mm(pt[1])), S('uuid', uid('nc'))))


def text(s, pt, size=1.27, bold=False):
    f = S('font', S('size', size, size))
    if bold:
        f.append(S('bold', Sym('yes')))
    items.append(S('text', s, S('exclude_from_sim', Sym('no')), S('at', mm(pt[0] + OX[0]), mm(pt[1]), 0),
                   S('effects', f, S('justify', Sym('left'), Sym('bottom'))), S('uuid', uid('t'))))


def block(title, x0, y0, x1, y1):
    items.append(S('rectangle', S('start', mm(x0 + OX[0]), mm(y0)), S('end', mm(x1 + OX[0]), mm(y1)),
                   S('stroke', S('width', 0.2), S('type', Sym('dash'))), S('fill', S('type', Sym('none'))),
                   S('uuid', uid('rect'))))
    text(title, (x0 + 1, y0 + 3), size=2.0, bold=True)


FP = {
    'R': 'Resistor_SMD:R_0603_1608Metric', 'C': 'Capacitor_SMD:C_0603_1608Metric',
    'C0805': 'Capacitor_SMD:C_0805_2012Metric', 'LED': 'LED_SMD:LED_0603_1608Metric',
    'TP': 'TestPoint:TestPoint_Pad_D1.5mm', 'SW': 'Button_Switch_SMD:SW_SPST_TL3342',
    'JST': 'Connector_JST:JST_PH_S2B-PH-K_1x02_P2.00mm_Horizontal',
}


def R(ref, x, y, val, desc, rot=0, **k):
    return place(ref, 'Device:R', x, y, rot, val, FP['R'], desc, **k)


def C(ref, x, y, val, desc, fp='C', **k):
    return place(ref, 'Device:C', x, y, 0, val, FP[fp], desc, **k)


# ====================================================== bloc 1 : USB-C + charge
block('1 - Entree USB-C et charge Li-ion (MCP73831, 500 mA)', 12, 28, 138, 72)
j1 = place('J1', 'Connector:USB_C_Receptacle_PowerOnly_6P', 32, 48, 0, 'USB4125-GF-A',
           'Connector_USB:USB_C_Receptacle_GCT_USB4125-xx-x_6P_TopMnt_Horizontal', 'USB-C alimentation seule',
           refpos=(24, 35), valpos=(24, 37), ds='https://gct.co/files/drawings/usb4125.pdf')
wire(j1['A9'], (90, 42))
flag((49, 42))
C('C1', 60, 45, '4.7uF', 'Entree chargeur')
gnd((60, 48))
power('VBUS', (70, 42))
wire(j1['A5'], (50, 52))
label('CC1', (45, 52))
R('R1', 50, 55, '5.1k', 'CC1 USB-C')
gnd((50, 58))
wire(j1['B5'], (58, 54))
label('CC2', (45, 54))
R('R2', 58, 57, '5.1k', 'CC2 USB-C')
gnd((58, 60))
wire(j1['A12'], (32, 64))
wire(j1['S1'], (26, 64), (32, 64))
gnd((32, 64))
wire((32, 64), (40, 64), (40, 62))
flag((40, 62))
u3 = place('U3', 'Battery_Management:MCP73831-2-OT', 90, 50, 0, 'MCP73831T-2ACI/OT', 'Package_TO_SOT_SMD:SOT-23-5',
           'Chargeur Li-ion 4,2 V', refpos=(92, 43), valpos=(92, 57.5),
           ds='https://ww1.microchip.com/downloads/en/DeviceDoc/MCP73831-Family-Data-Sheet-DS20001984H.pdf')
wire(u3['4'], (90, 42))
wire(u3['2'], (90, 58))
gnd((90, 58))
wire(u3['5'], (72, 52))
label('CHG_PROG', (72.5, 52))
R('R3', 72, 55, '2k', 'Courant de charge 500 mA', refpos=(74, 55.5), valpos=(74, 57.5))
gnd((72, 58))
wire(u3['1'], (108, 52), (108, 60), (109, 60))
label('CHG_STAT', (98.5, 52))
place('D2', 'Device:LED', 112, 60, 0, 'LED rouge', FP['LED'], 'LED charge', refpos=(112, 63), valpos=(112, 65), just=None)
wire((115, 60), (126, 60))
label('CHG_LED_A', (115.5, 60))
R('R4', 129, 60, '1k', 'LED charge', rot=270, refpos=(129, 62.5), valpos=(129, 64.5))
wire((132, 60), (134, 60), (134, 58))
power('VBUS', (134, 58))
wire(u3['3'], (124, 48))
C('C2', 116, 51, '4.7uF', 'Sortie chargeur')
gnd((116, 54))
glabel('VBAT', (124, 48), 'R')
text('Icharge = 1000 V / R3 = 500 mA\nSTAT : bas pendant la charge (LED allumee)', (62, 70))

OX[0] = 14
# ========================================== bloc 2 : partage de charge + inter
block('2 - Batterie, partage de charge et interrupteur', 130, 28, 226, 72)
j2 = place('J2', 'Connector_Generic:Conn_01x02', 138, 48, 0, 'S2B-PH-K-S', FP['JST'], 'Connecteur batterie LiPo',
           mirror='y', refpos=(136, 44.5), valpos=(136, 54), just=None)
wire(j2['2'], (144, 50), (144, 52))
gnd((144, 52))
wire(j2['1'], (148, 48))
label('BAT_IN', (142.5, 48))
R('R6', 151, 48, '0R', 'Shunt mesure courant batterie', rot=90, refpos=(151, 46), valpos=(151, 50))
text('1 = BAT+   2 = GND', (132, 58))
q1 = place('Q1', 'Transistor_FET:DMG2301L', 182, 50, 90, 'DMG2305UX', 'Package_TO_SOT_SMD:SOT-23',
           'MOSFET P partage de charge', refpos=(186.5, 51.5), valpos=(188.5, 53.5), just='left',
           ds='https://www.diodes.com/assets/Datasheets/DMG2305UX.pdf')
wire((154, 48), q1['3'])
wire((158, 48), (158, 44))
glabel('VBAT', (158, 44), 'U')
R('R11', 164, 51, '1M', 'Pont diviseur VBAT haut')
R('R12', 164, 57, '1M', 'Pont diviseur VBAT bas')
gnd((164, 60))
wire((160, 54), (170, 54))
C('C10', 170, 57, '100nF', 'Filtre mesure VBAT')
gnd((170, 60))
glabel('ADC_VBAT', (160, 54), 'L')
wire(q1['2'], (204, 48))
power('VBUS', (176, 40))
wire((176, 40), (185, 40))
place('D1', 'Device:D_Schottky', 188, 40, 180, 'B5819W', 'Diode_SMD:D_SOD-123', 'Schottky 1 A 40 V',
      refpos=(188, 37.5), valpos=(188, 42.5), just=None, ds='https://www.diodes.com/assets/Datasheets/ds30217.pdf')
wire((191, 40), (194, 40), (194, 48))
wire((176, 40), (176, 56), (182, 56))
wire(q1['1'], (182, 58))
R('R5', 182, 61, '100k', 'Rappel grille Q1')
gnd((182, 64))
wire((199, 48), (199, 44))
glabel('VSYS', (199, 44), 'U')
sw1 = place('SW1', 'Switch:SW_SPDT', 208, 48, 0, 'PCM12SMTR', 'Button_Switch_SMD:SW_SPDT_PCM12',
            'Interrupteur marche/arret', refpos=(208, 43), valpos=(208, 53.5), just=None)
nc(sw1['3'])
wire(sw1['1'], (216, 46))
glabel('VSW', (216, 46), 'R')
text('USB present : grille Q1 = VBUS -> Q1 bloque, charge alimentee par D1\n'
     'USB absent : grille a 0 V par R5 -> Q1 passant, charge sur batterie', (146, 70.5))

# ===================================================== bloc 3 : regulation 3V3
OX[0] = 12
block('3 - Regulation 3,3 V (AP2112K, 600 mA)', 232, 28, 308, 72)
glabel('VSW', (238, 48), 'L')
u4 = place('U4', 'Regulator_Linear:AP2112K-3.3', 264, 50, 0, 'AP2112K-3.3TRG1', 'Package_TO_SOT_SMD:SOT-23-5',
           'LDO 3,3 V 600 mA', refpos=(260, 43), valpos=(266, 56.5),
           ds='https://www.diodes.com/assets/Datasheets/AP2112.pdf')
wire((238, 48), u4['1'])
flag((243, 48))
C('C3', 248, 51, '1uF', 'Entree LDO')
gnd((248, 54))
wire(u4['3'], (254, 50), (254, 48))
wire(u4['2'], (264, 58))
gnd((264, 58))
wire(u4['5'], (290, 48))
C('C4', 284, 51, '22uF', 'Sortie LDO', fp='C0805')
gnd((284, 54))
wire((290, 48), (290, 46))
power('+3V3', (290, 46))

# =========================================================== bloc 4 : ESP32
OX[0] = 0
block('4 - ESP32-WROOM-32E (Bluetooth Classic A2DP + BLE)', 12, 78, 112, 176)
u1 = place('U1', 'RF_Module:ESP32-WROOM-32E', 60, 132, 0, 'ESP32-WROOM-32E-N4', 'RF_Module:ESP32-WROOM-32E',
           'Module Bluetooth Classic + BLE', refpos=(49, 102), valpos=(63, 161.5),
           ds='https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32e_esp32-wroom-32ue_datasheet_en.pdf')
used = {'25': 'IO0', '35': 'TXD0', '34': 'RXD0', '31': 'LED', '33': 'AMP_SD', '36': 'I2S_DIN', '10': 'I2S_LRCLK',
        '11': 'I2S_BCLK', '8': 'TOUCH', '9': 'BTN_USER', '7': 'ADC_VBAT'}
for n in ['25', '35', '24', '34', '26', '29', '14', '16', '13', '23', '27', '28', '30', '31', '33', '36', '37',
          '10', '11', '12', '8', '9', '6', '7', '4', '5']:
    p = u1[n]
    if n in used:
        wire(p, (p[0] + 6, p[1]))
        glabel(used[n], (p[0] + 6, p[1]), 'R')
    else:
        nc(p)
wire(u1['3'], (30, u1['3'][1]))
ey = u1['3'][1]
glabel('EN', (30, ey), 'L')
R('R7', 42, ey - 3, '10k', 'Pull-up EN', refpos=(36.5, ey - 4), valpos=(36.5, ey - 2))
power('+3V3', (42, ey - 6))
C('C7', 34, ey + 3, '1uF', 'Temporisation EN', refpos=(28, ey + 2.5), valpos=(28, ey + 4.5))
gnd((34, ey + 6))
vy = u1['2'][1]
wire(u1['2'], (60, vy - 10))
power('+3V3', (60, vy - 10))
wire((60, vy - 8), (78, vy - 8))
C('C5', 70, vy - 5, '10uF', 'Decouplage ESP32', fp='C0805')
gnd((70, vy - 2))
C('C6', 78, vy - 5, '100nF', 'Decouplage ESP32')
gnd((78, vy - 2))
wire(u1['1'], (60, u1['1'][1] + 2))
gnd((60, u1['1'][1] + 2))
text('Broches de demarrage IO2, IO5, IO12, IO15 :\nlaissees libres. IO0 : bouton BOOT + J4 seulement.', (14, 173))

# =========================================================== bloc 5 : ampli
block('5 - Ampli classe D I2S MAX98357A + haut-parleur', 118, 78, 212, 134)
u2 = place('U2', 'Audio:MAX98357A', 164, 108, 0, 'MAX98357AETE+T',
           'Package_DFN_QFN:TQFN-16-1EP_3x3mm_P0.5mm_EP1.23x1.23mm', 'Ampli classe D I2S mono',
           refpos=(166, 97), valpos=(167, 119),
           ds='https://www.analog.com/media/en/technical-documentation/data-sheets/MAX98357A-MAX98357B.pdf')
for n, name in [('1', 'I2S_DIN'), ('16', 'I2S_BCLK'), ('14', 'I2S_LRCLK'), ('4', 'AMP_SD')]:
    p = u2[n]
    wire(p, (134, p[1]))
    glabel(name, (134, p[1]), 'L')
sd = u2['4']
R('R13', 140, sd[1] + 3, '100k', 'Rappel SD_MODE (ampli coupe au boot)', refpos=(133.5, sd[1] + 3), valpos=(133.5, sd[1] + 5))
gnd((140, sd[1] + 6))
ga = u2['2']
wire(ga, (146, ga[1]), (146, ga[1] + 6))
label('AMP_GAIN', (146, ga[1] + 3.5), 'R')
R('R14', 146, ga[1] + 9, '100k', 'Option gain 15 dB (non monte)', dnp=True, refpos=(148, ga[1] + 8), valpos=(148, ga[1] + 10))
gnd((146, ga[1] + 12))
vd = u2['7']
wire(vd, (164, 90))
wire((152, 90), (182, 90))
glabel('VSW', (152, 90), 'L')
C('C8', 174, 93, '10uF', 'Decouplage ampli', fp='C0805')
gnd((174, 96))
C('C9', 182, 93, '100nF', 'Decouplage ampli')
gnd((182, 96))
g2 = u2['3']
pd = u2['17']
wire(g2, (g2[0], g2[1] + 2))
wire(pd, (pd[0], pd[1] + 2), (g2[0], g2[1] + 2))
gnd((g2[0], g2[1] + 2))
j3 = place('J3', 'Connector_Generic:Conn_01x02', 196, u2['9'][1], 0, 'S2B-PH-K-S', FP['JST'], 'Connecteur haut-parleur',
           refpos=(196, u2['9'][1] - 3), valpos=(196, u2['9'][1] + 5.5), just=None)
wire(u2['9'], j3['1'])
wire(u2['10'], j3['2'])
label('SPK_P', (180, u2['9'][1]))
label('SPK_N', (180, u2['10'][1]))
text('GAIN_SLOT libre = 9 dB ; R14 (100k vers GND) = 15 dB\n'
     'SD_MODE : 0 V = arret (R13) ; 3,3 V = canal gauche', (172, 131))

# ======================================================= bloc 6 : interface
block('6 - Interface : boutons, LED, pad tactile', 118, 140, 212, 196)


def button(ref, x, y, desc):
    s = place(ref, 'Switch:SW_Push', x, y, 0, 'TL3342', FP['SW'], desc, refpos=(x, y - 4.5), valpos=(x, y + 2.5), just=None)
    wire(s['2'], (x + 6, y), (x + 6, y + 2))
    gnd((x + 6, y + 2))
    return s


glabel('EN', (126, 152), 'L')
s = button('SW2', 138, 152, 'Bouton RESET')
wire((126, 152), s['1'])
text('RESET', (135, 146.5))
glabel('IO0', (126, 166), 'L')
s = button('SW3', 142, 166, 'Bouton BOOT')
wire((126, 166), s['1'])
R('R8', 130, 163, '10k', 'Pull-up IO0', refpos=(124, 161.5), valpos=(124, 163.5))
power('+3V3', (130, 160))
text('BOOT', (139, 160.5))
glabel('BTN_USER', (126, 182), 'L')
s = button('SW4', 148, 182, 'Bouton utilisateur')
wire((126, 182), s['1'])
R('R9', 130, 179, '10k', 'Pull-up bouton', refpos=(124, 177.5), valpos=(124, 179.5))
power('+3V3', (130, 176))
C('C11', 136, 185, '100nF', 'Anti-rebond bouton', refpos=(130, 185), valpos=(130, 187))
gnd((136, 188))
text('UTILISATEUR', (143, 176.5))
glabel('LED', (172, 152), 'L')
wire((172, 152), (176, 152))
R('R10', 179, 152, '1k', 'LED etat', rot=90, refpos=(179, 150), valpos=(179, 154))
place('D3', 'Device:LED', 193, 152, 180, 'LED bleue', FP['LED'], 'LED etat', refpos=(193, 149), valpos=(193, 155), just=None)
wire((182, 152), (190, 152))
label('LED_A', (182.5, 152))
wire((196, 152), (202, 152), (202, 154))
gnd((202, 154))
glabel('TOUCH', (172, 170), 'L')
wire((172, 170), (184, 170))
place('TP1', 'Connector:TestPoint', 184, 170, 0, 'Pad tactile', 'TestPoint:TestPoint_Pad_D4.0mm', 'Electrode tactile',
      refpos=(186, 167), valpos=(186, 169))

# =================================================== bloc 7 : programmation
block('7 - Programmation UART (J4)', 218, 78, 262, 134)
j4 = place('J4', 'Connector_Generic:Conn_01x06', 248, 104, 0, 'Barrette 1x6',
           'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical', 'Programmation UART',
           refpos=(248, 97), valpos=(248, 114.5), just=None)
wire(j4['1'], (240, j4['1'][1]), (240, j4['1'][1] - 4))
power('+3V3', (240, j4['1'][1] - 4))
wire(j4['2'], (224, j4['2'][1]), (224, j4['2'][1] + 12))
gnd((224, j4['2'][1] + 12))
for n, name in [('3', 'TXD0'), ('4', 'RXD0'), ('5', 'EN'), ('6', 'IO0')]:
    p = j4[n]
    wire(p, (236, p[1]))
    glabel(name, (236, p[1]), 'L')
text('1 +3V3\n2 GND\n3 TXD0 (sortie ESP32)\n4 RXD0 (entree ESP32)\n5 EN\n6 IO0', (222, 131))

# ==================================================== bloc 8 : points de test
block('8 - Points de test', 268, 78, 318, 134)
tps = [('TP2', 'TP VBAT', 'VBAT'), ('TP3', 'TP VSYS', 'VSYS'), ('TP4', 'TP +3V3', '+3V3'), ('TP5', 'TP GND', 'GND'),
       ('TP6', 'TP I2S_BCLK', 'I2S_BCLK'), ('TP7', 'TP I2S_LRCLK', 'I2S_LRCLK'), ('TP8', 'TP I2S_DIN', 'I2S_DIN')]
for i, (ref, val, net) in enumerate(tps):
    x = 274 + 7 * i
    place(ref, 'Connector:TestPoint', x, 96, 0, val, FP['TP'], 'Point de test', refpos=(x - 2, 91), valpos=(x, 86), just=None)
    items[-1][[k for k, e in enumerate(items[-1]) if isinstance(e, list) and e[0] == 'property' and e[1] == 'Value'][0]][4].append(S('hide', Sym('yes')))
    wire((x, 96), (x, 100))
    if net == 'GND':
        gnd((x, 100))
    elif net == '+3V3':
        power('+3V3', (x, 100), rot=180)
    else:
        glabel(net, (x, 100), 'D')

text('Oreillette Bluetooth v1 - carte de validation fonctionnelle\n'
     'Chaine audio : A2DP -> ESP32 -> I2S -> MAX98357A -> HP ; retour BLE vers l\'application.\n'
     'Voir VERIFICATION.md pour les brochages controles et les ecarts avec la netlist d\'origine.', (218, 150), size=1.5)

# ------------------------------------------------------------- jonctions auto
ends = {}
for a, b in wires:
    for p in (a, b):
        ends[p] = ends.get(p, 0) + 1


def interior(p):
    for a, b in wires:
        if a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1]):
            return True
        if a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0]):
            return True
    return False


for p in sorted(set(ends) | pin_points):
    n = ends.get(p, 0) + (1 if p in pin_points else 0)
    if (interior(p) and n >= 1) or n >= 3:
        items.append(S('junction', S('at', mm(p[0]), mm(p[1])), S('diameter', 0), S('color', 0, 0, 0, 0), S('uuid', uid('j'))))
# KiCad ne connecte un fil qu'a ses extremites : on coupe chaque fil aux broches / extremites qu'il traverse
split = []
for a, b in wires:
    cuts = [p for p in set(ends) | pin_points
            if (a[0] == b[0] == p[0] and min(a[1], b[1]) < p[1] < max(a[1], b[1]))
            or (a[1] == b[1] == p[1] and min(a[0], b[0]) < p[0] < max(a[0], b[0]))]
    pts = sorted([a, b] + cuts)
    split += list(zip(pts, pts[1:]))
for a, b in split:
    items.append(S('wire', S('pts', S('xy', mm(a[0]), mm(a[1])), S('xy', mm(b[0]), mm(b[1]))),
                   S('stroke', S('width', 0), S('type', Sym('default'))), S('uuid', uid('w'))))

order = {'junction': 0, 'no_connect': 1, 'wire': 2, 'rectangle': 3, 'text': 4, 'label': 5, 'global_label': 6, 'symbol': 7}
items.sort(key=lambda e: order[str(e[0])])
root = S('kicad_sch', S('version', 20250114), S('generator', 'eeschema'), S('generator_version', '9.0'),
         S('uuid', ROOT), S('paper', 'A3'),
         S('title_block', S('title', 'Oreillette Bluetooth v1 - carte de validation'), S('date', '2026-11-11'),
           S('rev', '1.0'), S('comment', 1, 'ESP32-WROOM-32E + MAX98357A + chargeur Li-ion'),
           S('comment', 2, 'Schema genere par tools/gen_sch.py puis verifie par ERC (kicad-cli)')),
         [Sym('lib_symbols')] + [lib_symbols[k] for k in sorted(lib_symbols)])
root += items
root.append(S('sheet_instances', S('path', '/', S('page', '1'))))
root.append(S('embedded_fonts', Sym('no')))
open(OUT, 'w').write(dump(root) + '\n')
print('ecrit', OUT, len(items), 'elements')
