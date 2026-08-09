# -*- coding: utf-8 -*-
import os as _os
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"..",".."))  # 存档件：相对路径从仓库根解析，可在任意目录调用
"""跨章逐字引用探测（剔除模板样板串）。只读。"""
import re,os,glob
from collections import defaultdict
N=18
BOILER=[r'<title>.*?</title>',r'<nav class="crumbs">.*?</nav>',r'<div class="series">.*?</div>',
        r'<div class="meta">.*?</div>',r'<span class="tag">.*?</span>',r'<div class="stamp">.*?</div>',
        r'<div class="eyebrow">.*?</div>',r'<div class="spec-head">.*?</div>',r'<div class="label">.*?</div>']
def visible(p):
    h=open(p,encoding='utf-8').read()
    b=re.search(r'<body.*?</body>',h,re.S).group(0)
    b=re.sub(r'<script.*?</script>','',b,flags=re.S)
    b=re.sub(r'<svg.*?</svg>','',b,flags=re.S)
    for pat in BOILER: b=re.sub(pat,'\n□\n',b,flags=re.S)
    t=re.sub(r'<[^>]+>','\n',b)
    return [re.sub(r'\s+','',seg) for seg in t.split('□')]
files=sorted(glob.glob('chapters/*.html'))
texts={os.path.basename(f):visible(f) for f in files}
grams=defaultdict(set)
pos={}
for name,segs in texts.items():
    for t in segs:
        for i in range(len(t)-N+1):
            g=t[i:i+N]
            grams[g].add(name)
shared={g:frozenset(s) for g,s in grams.items() if len(s)>1}
spans=set()
for name,segs in texts.items():
    for t in segs:
        i=0
        while i<=len(t)-N:
            g=t[i:i+N]
            if g in shared:
                grp=shared[g]; j=i
                while j<=len(t)-N and shared.get(t[j:j+N])==grp: j+=1
                spans.add((grp,t[i:j+N-1]))
                i=j
            else: i+=1
out=sorted(spans,key=lambda x:(-len(x[1]),x[1],tuple(sorted(x[0]))))  # 确定性排序：等长片段按文本再按组名
out=[(g,s) for g,s in out if not any(s in s2 and s!=s2 for _,s2 in out)]
pairs=defaultdict(list)
for grp,s in out: pairs[grp].append(s)
print('跨章逐字重复片段（≥%d 字，已剔除模板样板串）\n'%N)
for grp,ss in sorted(pairs.items(),key=lambda kv:(-sum(len(s) for s in kv[1]),tuple(sorted(kv[0])))):
    tot=sum(len(s) for s in ss)
    print('● %s —— %d 处，共 %d 字'%(' ⇄ '.join(sorted(grp)),len(ss),tot))
    for s in sorted(ss,key=len,reverse=True):
        print('    [%2d] 「%s」'%(len(s), s if len(s)<=58 else s[:56]+'…'))
    print()
print('耦合对 %d 组 · 片段 %d 处'%(len(pairs),len(out)))
