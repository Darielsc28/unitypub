import sys; sys.path.insert(0,'/home/user/unitypub/tools')
from sexpr import *
SYM='/opt/kroot/usr/share/kicad/symbols/'
import re
def lib(n): return parse(open(SYM+n+'.kicad_sym').read())
dev=lib('Device'); print([s[1] for s in find(dev,'symbol') if 'MOS' in s[1]][:20])
pw=lib('power'); print([s[1] for s in find(pw,'symbol') if s[1] in('GND','+3V3','VBUS','PWR_FLAG','+BATT')])
def pins(l,n):
    s=[x for x in find(l,'symbol') if x[1]==n][0]
    ext=find(s,'extends')
    if ext: 
        print(n,'extends',ext[0][1]); return pins(l,ext[0][1])
    for u in find(s,'symbol'):
        for p in find(u,'pin'):
            at=find(p,'at')[0]; print('  ',n,find(p,'number')[0][1],find(p,'name')[0][1],p[1],at[1:],find(p,'length')[0][1])
for ln,n in [('RF_Module','ESP32-WROOM-32E'),('Audio','MAX98357A'),('Battery_Management','MCP73831-2-OT'),('Regulator_Linear','AP2112K-3.3'),('Transistor_FET','DMG2301L'),('Connector','USB_C_Receptacle_PowerOnly_6P'),('Switch','SW_SPDT'),('Switch','SW_Push'),('Device','D_Schottky'),('Device','LED'),('Device','R'),('Device','C'),('Connector_Generic','Conn_01x06'),('Connector_Generic','Conn_01x02'),('Connector','TestPoint'),('power','GND'),('power','+3V3'),('power','VBUS'),('power','PWR_FLAG')]:
    pins(lib(ln),n)
