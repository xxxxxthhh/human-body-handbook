# -*- coding: utf-8 -*-
import os as _os
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"..",".."))  # 存档件：相对路径从仓库根解析，可在任意目录调用
"""跨章『近似句』探测：逐字匹配看不见的刻意呼应对。只读。"""
import re,os,glob,difflib
from collections import defaultdict
BOILER=[r'<title>.*?</title>',r'<nav class="crumbs">.*?</nav>',r'<div class="series">.*?</div>',
        r'<div class="meta">.*?</div>',r'<span class="tag">.*?</span>',r'<div class="stamp">.*?</div>',
        r'<div class="eyebrow">.*?</div>',r'<div class="spec-head">.*?</div>',r'<div class="label">.*?</div>']
def sents(p):
    h=open(p,encoding='utf-8').read()
    b=re.sub(r'<script.*?</script>','',re.search(r'<body.*?</body>',h,re.S).group(0),flags=re.S)
    b=re.sub(r'<svg.*?</svg>','',b,flags=re.S)
    for pat in BOILER: b=re.sub(pat,' ',b,flags=re.S)
    t=re.sub(r'<[^>]+>','\n',b)
    out=[]
    for line in t.split('\n'):
        for s in re.split(r'(?<=[。！？])',re.sub(r'\s+','',line)):
            s=s.strip()
            if len(re.findall(r'[一-鿿]',s))>=12: out.append(s)
    return out
docs={os.path.basename(f):sents(f) for f in sorted(glob.glob('chapters/ch*.html'))}
items=[(c,s) for c,ss in docs.items() for s in ss]
idx=defaultdict(list)
for i,(c,s) in enumerate(items):
    for g in {s[j:j+4] for j in range(len(s)-3)}: idx[g].append(i)
cand=defaultdict(int)
for g,lst in idx.items():
    if len(lst)>40: continue
    for a in range(len(lst)):
        for b in range(a+1,len(lst)):
            i,j=lst[a],lst[b]
            if items[i][0]!=items[j][0]: cand[(i,j)]+=1
res=[]
for (i,j),n in cand.items():
    if n<4: continue
    a,b=items[i][1],items[j][1]
    r=difflib.SequenceMatcher(None,a,b,autojunk=False).ratio()  # 中文按字比对必须关闭 autojunk（见 archive/coupling_scan.py 存档复核）
    if r>=0.70 and a!=b: res.append((r,items[i][0],a,items[j][0],b))
res.sort(reverse=True)
print('跨章近似句（相似度 ≥0.70，非逐字相同）：\n')
for r,c1,a,c2,b in res:
    print('  %.2f  %s ⇄ %s'%(r,c1.replace('.html',''),c2.replace('.html','')))
    print('        A「%s」'%a[:70]); print('        B「%s」'%b[:70]); print()
print('合计 %d 对'%len(res))
