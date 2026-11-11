#!/usr/bin/env python3
"""Compare la netlist d'origine avec celle exportee du schema KiCad (refs, valeurs, empreintes, noeuds)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, find
def load(p):
    t = parse(open(p).read())
    comps = {}
    for c in find(find(t, 'components')[0], 'comp'):
        g = lambda k: (find(c, k) or [[None, '']])[0][1]
        comps[g('ref')] = (g('value'), g('footprint'))
    nets = {}
    for n in find(find(t, 'nets')[0], 'net'):
        name = find(n, 'name')[0][1].lstrip('/')
        nets[name] = frozenset((find(x, 'ref')[0][1], find(x, 'pin')[0][1]) for x in find(n, 'node'))
    return comps, nets
ca, na = load(sys.argv[1]); cb, nb = load(sys.argv[2])
ok = True
for r in sorted(set(ca) | set(cb)):
    if ca.get(r) != cb.get(r):
        print('COMPOSANT', r, ca.get(r), '->', cb.get(r)); ok = ok and r in ca and r in cb
for n in sorted(set(na) | set(nb)):
    if n.startswith('unconnected-'):
        continue  # broches volontairement non connectees (drapeaux NC)
    a, b = na.get(n, frozenset()), nb.get(n, frozenset())
    if a != b:
        ok = False
        print('NET', n, 'origine seulement:', sorted(a - b), 'schema seulement:', sorted(b - a))
print('%d composants / %d nets (origine) ; %d composants / %d nets (schema)' % (len(ca), len(na), len(cb), len(nb)))
print('CONNECTIVITE IDENTIQUE' if ok else 'DIFFERENCES')
sys.exit(0 if ok else 1)
