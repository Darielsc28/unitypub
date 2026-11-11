"""Mini lecteur/ecrivain de S-expressions KiCad."""
import re
class Sym(str):
    pass
_tok = re.compile(r'"(?:\\.|[^"\\])*"|\(|\)|[^\s()"]+')
def parse(text):
    stack=[[]]
    for m in _tok.finditer(text):
        t=m.group(0)
        if t=='(':
            l=[]; stack[-1].append(l); stack.append(l)
        elif t==')':
            stack.pop()
        elif t[0]=='"':
            stack[-1].append(t[1:-1].replace('\\"','"').replace('\\\\','\\').replace('\\n','\n'))
        else:
            stack[-1].append(Sym(t))
    return stack[0][0]
def q(s):
    return '"'+s.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n')+'"'
def dump(e,ind=0):
    if isinstance(e,Sym): return str(e)
    if isinstance(e,str): return q(e)
    if isinstance(e,(int,)): return str(e)
    if isinstance(e,float):
        s=('%.4f'%e).rstrip('0').rstrip('.')
        return s if s not in ('-0','') else '0'
    simple=all(not isinstance(x,list) for x in e)
    if simple or (len(e)<=4 and all(not isinstance(x,list) or all(not isinstance(y,list) for y in x) for x in e) and str(e[0]) in ('at','xy','pts','size','font','start','end','stroke','effects','number','name','mid','center','fill','offset','justify','length','color')):
        return '('+' '.join(dump(x) for x in e)+')'
    pad='\t'*(ind+1)
    out='('+dump(e[0])
    for x in e[1:]:
        if isinstance(x,list): out+='\n'+pad+dump(x,ind+1)
        else: out+=' '+dump(x)
    return out+'\n'+'\t'*ind+')'
def S(*a): return [Sym(a[0])]+list(a[1:])
def find(e,name):
    return [x for x in e if isinstance(x,list) and x and x[0]==name]
