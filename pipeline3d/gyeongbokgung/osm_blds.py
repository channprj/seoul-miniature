import json, numpy as np
ORG=[197940.46660081236,552912.2911692131]
def tm5186(lon,lat):
    a,f=6378137.0,1/298.257222101; e2=f*(2-f); ep2=e2/(1-e2); lat0,lon0=np.radians(38.0),np.radians(127.0)
    def M(p): return a*((1-e2/4-3*e2**2/64-5*e2**3/256)*p-(3*e2/8+3*e2**2/32+45*e2**3/1024)*np.sin(2*p)+(15*e2**2/256+45*e2**3/1024)*np.sin(4*p)-(35*e2**3/3072)*np.sin(6*p))
    p,l=np.radians(lat),np.radians(lon); N_=a/np.sqrt(1-e2*np.sin(p)**2); T=np.tan(p)**2; C=ep2*np.cos(p)**2; A=(l-lon0)*np.cos(p)
    x=N_*(A+(1-T+C)*A**3/6+(5-18*T+T**2+72*C-58*ep2)*A**5/120)+200000.0
    y=(M(p)-M(lat0)+N_*np.tan(p)*(A**2/2+(5-T+9*C+4*C**2)*A**4/24+(61-58*T+T**2+600*C-330*ep2)*A**6/720))+600000.0
    return x-ORG[0],y-ORG[1]
def load(path='work/redraw/osm_raw.json'):
    osm=json.load(open(path)); out=[]
    for e in osm['elements']:
        t=e.get('tags',{})
        if 'building' not in t and 'building:part' not in t: continue
        rings=[]
        if e['type']=='relation':
            for mem in e.get('members',[]):
                if mem.get('role','outer') in ('outer','') and mem.get('geometry'): rings.append(mem['geometry'])
        elif e.get('geometry'): rings.append(e['geometry'])
        for g in rings:
            if len(g)>=4 and g[0]==g[-1] or len(g)>=3:
                out.append((np.array([tm5186(q['lon'],q['lat']) for q in g]),t))
    return out
