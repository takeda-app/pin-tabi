"""build_graph.py の出力を、乗換駅のグループ化・路線色・速度付きの軽量な rail.json にまとめる。
使い方: python3 pack_data.py [間引き幅=10] [graph_raw.json] [出力 rail.json]
"""
import json,collections,math,hashlib,colorsys,sys,gzip
TOL=float(sys.argv[1]) if len(sys.argv)>1 else 10  # 線路形状の間引き幅（1単位≒1m）
g=json.load(open(sys.argv[2] if len(sys.argv)>2 else 'graph_raw.json'));st=g['st'];E=g['edges'];L=g['lines']
def dp(pts,tol):
    if len(pts)<3: return pts
    keep=[False]*len(pts);keep[0]=keep[-1]=True;stack=[(0,len(pts)-1)]
    while stack:
        i,j=stack.pop();ax,ay=pts[i];bx,by=pts[j];dx,dy=bx-ax,by-ay;l2=dx*dx+dy*dy;md=-1;mi=-1
        for k in range(i+1,j):
            px,py=pts[k]
            if l2==0: d=math.hypot(px-ax,py-ay)
            else:
                t=max(0,min(1,((px-ax)*dx+(py-ay)*dy)/l2));d=math.hypot(px-ax-t*dx,py-ay-t*dy)
            if d>md: md=d;mi=k
        if md>tol: keep[mi]=True;stack+=[(i,mi),(mi,j)]
    return [p for p,k in zip(pts,keep) if k]
# ---- groups ----
par=list(range(len(st)))
def f(x):
    while par[x]!=x: par[x]=par[par[x]];x=par[x]
    return x
def u(a,b): par[f(a)]=f(b)
byg=collections.defaultdict(list)
for i,s in enumerate(st): byg[s['g']].append(i)
for v in byg.values():
    for i in v[1:]: u(v[0],i)
byname=collections.defaultdict(list)
for i,s in enumerate(st): byname[s['name']].append(i)
def dd(a,b):
    lat=math.radians(a['y']/1e5);return math.hypot((b['x']-a['x'])/1e5*111320*math.cos(lat),(b['y']-a['y'])/1e5*110540)
for v in byname.values():
    for i in range(len(v)):
        for j in range(i+1,len(v)):
            if dd(st[v[i]],st[v[j]])<600: u(v[i],v[j])
roots={};groups=[]
for i,s in enumerate(st):
    r=f(i)
    if r not in roots: roots[r]=len(groups);groups.append({'m':[]})
    s['G']=roots[r];groups[roots[r]]['m'].append(i)
# name = most common name in group
for G in groups:
    names=collections.Counter(st[i]['name'] for i in G['m']);G['name']=names.most_common(1)[0][0]
    G['x']=round(sum(st[i]['x'] for i in G['m'])/len(G['m']));G['y']=round(sum(st[i]['y'] for i in G['m'])/len(G['m']))
    G['lines']=sorted(set(st[i]['li'] for i in G['m']))
# unique display key
cnt=collections.Counter(G['name'] for G in groups)
for G in groups:
    if cnt[G['name']]==1: G['key']=G['name']
    else:
        l=L[G['lines'][0]];G['key']=f"{G['name']}（{l[1] if l[0].endswith('旅客鉄道') else l[0]}）"
c2=collections.Counter(G['key'] for G in groups)
for G in groups:
    if c2[G['key']]>1: G['key']=G['key'][:-1]+'・'+L[G['lines'][0]][1]+'）' if not L[G['lines'][0]][0].endswith('旅客鉄道') else G['key']
c3=collections.Counter(G['key'] for G in groups);dup=[k for k,v in c3.items() if v>1]
seen=collections.Counter()
for G in groups:
    if G['key'] in dup: seen[G['key']]+=1; G['key']=G['key'][:-1]+str(seen[G['key']])+'）' if G['key'].endswith('）') else G['key']+str(seen[G['key']])
assert len(set(G['key'] for G in groups))==len(groups)
# rank
shin=set(i for i,l in enumerate(L) if l[3]=='1')
for G in groups:
    G['rank']=len(G['lines'])+(6 if any(l in shin for l in G['lines']) else 0)
# ---- line colors ----
OFFICIAL={
 '東海道新幹線':'#2453a8','山陽新幹線':'#3d8ee0','九州新幹線':'#d6262f','西九州新幹線':'#ea7a1e','東北新幹線':'#1d9a4e','北海道新幹線':'#69b836','上越新幹線':'#e6a10d','北陸新幹線':'#b06a2c',
 '山手線':'#80c241','3号線銀座線':'#ff9500','4号線丸ノ内線':'#f62e36','2号線日比谷線':'#9cae b7'.replace(' ',''),'5号線東西線':'#009bbf','9号線千代田線':'#00bb85','8号線有楽町線':'#c1a470','11号線半蔵門線':'#8f76d6','7号線南北線':'#00ac9b','13号線副都心線':'#9c5e31',
 '1号線浅草線':'#e85298','6号線三田線':'#0079c2','10号線新宿線':'#6cbb5a','12号線大江戸線':'#b6007a',
 '1号線(御堂筋線)':'#e5171f','中央線':'#f15a22','京浜東北線':'#00b2e5','総武線':'#ffd400','京葉線':'#c9242f','埼京線':'#00ac9a','武蔵野線':'#f15a22','南武線':'#ffd400','横浜線':'#80c241','常磐線':'#00b261','東海道線':'#f68b1e','東北線':'#f68b1e','大阪環状線':'#e8336d','根岸線':'#00b2e5'}
def color(op,nm,typ):
    if nm in OFFICIAL and (typ in '12' or op in('東京地下鉄','東京都','大阪市高速電気軌道')): return OFFICIAL[nm]
    h=int(hashlib.md5((op+nm).encode()).hexdigest()[:8],16)
    hue=(h%360)/360; s=0.55+((h>>9)%25)/100; v=0.62+((h>>15)%20)/100
    r,g_,b=colorsys.hsv_to_rgb(hue,s,v);return '#%02x%02x%02x'%(int(r*255),int(g_*255),int(b*255))
# speed km/h and dwell min
def speed(l):
    op,nm,cat,typ=l
    if typ=='1': return 215
    if nm in('田沢湖線',) : return 85
    if typ=='2': return 62
    if cat=='12': return 45
    if cat=='21': return 22
    return 32
lines_out=[]
for l in L:
    op,nm,cat,typ=l
    kind='s' if typ=='1' else 'j' if typ=='2' else 't' if cat=='21' else 'm' if cat in('14','15','16','22','23','24','25') else 'p'
    lines_out.append([nm,op,kind,color(op,nm,typ),speed(l)])
# ---- edges ----
pts_total=0;edges_out=[]
for e in E:
    geom=dp(e['geom'],TOL);pts_total+=len(geom)
    flat=[geom[0][0],geom[0][1]]
    for a,b in zip(geom,geom[1:]): flat+= [b[0]-a[0],b[1]-a[1]]
    edges_out.append([e['a'],e['b'],round(e['len']),flat])
st_out=[[s['li'],s['G']] for s in st]
gr_out=[[G['key'],G['name'],G['x'],G['y'],G['rank']] for G in groups]
data={'lines':lines_out,'st':st_out,'groups':gr_out,'edges':edges_out}
js=json.dumps(data,ensure_ascii=False,separators=(',',':'))
open(sys.argv[3] if len(sys.argv)>3 else 'rail.json','w').write(js)
print('groups',len(groups),'pts',pts_total,'size',len(js.encode())/1e6,'MB gz',len(gzip.compress(js.encode()))/1e6)
print([G['key'] for G in groups if G['name']=='府中'],[G['key'] for G in groups if G['name'] in('東京','新宿')])
print(sorted(groups,key=lambda G:-G['rank'])[:15] and [ (G['name'],G['rank']) for G in sorted(groups,key=lambda G:-G['rank'])[:15]])
