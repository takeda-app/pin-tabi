"""国土数値情報 鉄道データ(N02)のGeoJSONから、路線ごとの駅の並びと駅間の線路形状を作る。
使い方: python3 build_graph.py <N02のUTF-8フォルダ> [出力 graph_raw.json]
"""
import json,collections,math,heapq,sys
D=(sys.argv[1] if len(sys.argv)>1 else "N02-25_GML/UTF-8").rstrip("/")+"/"
R=json.load(open(D+'N02-25_RailroadSection.geojson'))['features']
S=json.load(open(D+'N02-25_Station.geojson'))['features']
Q=1e5
def k(c): return (round(c[0]*Q),round(c[1]*Q))
def dist(a,b):  # quantized -> meters
    lat=math.radians(a[1]/Q); dx=(b[0]-a[0])/Q*111320*math.cos(lat); dy=(b[1]-a[1])/Q*110540; return math.hypot(dx,dy)
EXCL={'13'}
lines={}  # (op,name) -> info
def lkey(p): return (p['N02_004'],p['N02_003'])
for f in R:
    p=f['properties']
    if p['N02_001'] in EXCL: continue
    L=lines.setdefault(lkey(p),{'cat':p['N02_001'],'typ':p['N02_002'],'polys':[],'st':{}})
    L['polys'].append([k(c) for c in f['geometry']['coordinates']])
for f in S:
    p=f['properties']
    if p['N02_001'] in EXCL: continue
    L=lines.get(lkey(p))
    if L is None: continue
    pts=[k(c) for c in f['geometry']['coordinates']]
    st=L['st'].setdefault(p['N02_005c'],{'name':p['N02_005'],'g':p['N02_005g'],'pts':[]})
    st['pts'].extend(pts); L['polys'].append(pts)
print('lines',len(lines),'stations',sum(len(L['st']) for L in lines.values()))
out_st=[]; out_edges=[]; stats=collections.Counter()
for li,(lk,L) in enumerate(lines.items()):
    adj=collections.defaultdict(dict)
    for poly in L['polys']:
        for a,b in zip(poly,poly[1:]):
            if a==b: continue
            d=dist(a,b); adj[a][b]=d; adj[b][a]=d
    nodes=list(adj)
    # connect gaps: endpoints (deg1) to nearest node in other component within 60m
    comp={}; 
    for n in nodes:
        if n in comp: continue
        stack=[n]; comp[n]=n
        while stack:
            u=stack.pop()
            for v in adj[u]:
                if v not in comp: comp[v]=n; stack.append(v)
    grid=collections.defaultdict(list); G=80  # ~80m cells in 1e-5 deg units (~0.8m)->use 100 units=~1m? 
    CELL=60  # 60 units ~ 60m*? 1 unit=1e-5deg ~1.1m ; 60 units ~ 66m
    for n in nodes: grid[(n[0]//CELL,n[1]//CELL)].append(n)
    def near(p,maxd,pred=lambda n:True):
        best=None;bd=maxd;cx,cy=int(p[0]//CELL),int(p[1]//CELL)
        r=int(maxd/60)+1
        for i in range(cx-r,cx+r+1):
            for j in range(cy-r,cy+r+1):
                for n in grid.get((i,j),()):
                    if pred(n):
                        d=dist(p,n)
                        if d<bd: bd=d;best=n
        return best,bd
    ncomp=len(set(comp.values()))
    if ncomp>1:
        for n in nodes:
            if len(adj[n])==1:
                m,d=near(n,70,lambda x:comp[x]!=comp[n])
                if m: adj[n][m]=d; adj[m][n]=d; stats['gapfix']+=1
    # station anchors
    sids=[]
    for code,st in L['st'].items():
        pts=st['pts']; mx=sum(p[0] for p in pts)/len(pts); my=sum(p[1] for p in pts)/len(pts)
        a,d=near((mx,my),300)
        if a is None: stats['noanchor']+=1; continue
        sid=len(out_st); out_st.append({'li':li,'name':st['name'],'g':st['g'],'code':code,'x':round(mx),'y':round(my),'node':a}); sids.append(sid)
    # multi-source dijkstra (Voronoi)
    distm={};owner={};prev={};pq=[]
    for sid in sids:
        a=out_st[sid]['node']
        if a in distm: stats['dupanchor']+=1; continue
        distm[a]=0;owner[a]=sid;prev[a]=None;heapq.heappush(pq,(0,a))
    while pq:
        d,u=heapq.heappop(pq)
        if d>distm[u]: continue
        for v,w in adj[u].items():
            nd=d+w
            if v not in distm or nd<distm[v]-1e-9:
                distm[v]=nd;owner[v]=owner[u];prev[v]=u;heapq.heappush(pq,(nd,v))
    best={}
    for u in adj:
        if u not in owner: continue
        for v,w in adj[u].items():
            if v not in owner or owner[u]==owner[v]: continue
            a,b=owner[u],owner[v]
            if a>b: continue
            tot=distm[u]+w+distm[v]
            if (a,b) not in best or tot<best[(a,b)][0]: best[(a,b)]=(tot,u,v)
    for (a,b),(tot,u,v) in best.items():
        pa=[];x=u
        while x is not None: pa.append(x);x=prev[x]
        pa.reverse()
        pb=[];x=v
        while x is not None: pb.append(x);x=prev[x]
        out_edges.append({'a':a,'b':b,'len':tot,'geom':pa+pb,'li':li})
print(stats,'edges',len(out_edges))
json.dump({'lines':[[op,nm,L['cat'],L['typ']] for (op,nm),L in lines.items()],'st':[{k2:v for k2,v in s.items() if k2!='node'} for s in out_st],'edges':out_edges},open(sys.argv[2] if len(sys.argv)>2 else 'graph_raw.json','w'),ensure_ascii=False)
