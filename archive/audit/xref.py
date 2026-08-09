# -*- coding: utf-8 -*-
import os as _os
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"..",".."))  # 存档件：相对路径从仓库根解析，可在任意目录调用
"""前向承诺登记表（常设，lead 批准）。只读。
定位：待查表，不是判决器——只判"目标章有没有谈这件事"，判不了"谈得够不够"。
注意：v1 用"承诺句附近稀有词"做判据，跑出 41 条垃圾（判据词形如「一座冰」「上每一」），已废弃。
本版只取明确承诺句式 + 目标章回指作弱提示，最终由人逐条核。"""
import re,os,glob,sys
def chnum(f): return int(re.match(r'ch(\d+)',os.path.basename(f)).group(1))
def body(p):
    h=open(p,encoding='utf-8').read()
    b=re.sub(r'<script.*?</script>','',re.search(r'<body.*?</body>',h,re.S).group(0),flags=re.S)
    return re.sub(r'\s+','',re.sub(r'<[^>]+>','',re.sub(r'<svg.*?</svg>','',b,flags=re.S)))
B={chnum(f):body(f) for f in sorted(glob.glob('chapters/ch*.html'))}
# 目标可为「第 N 章」或「终章」；源为序章时 chnum=0。序章作目标一律是回指、非承诺，自然被 tgt<=src 滤掉。
PROM=re.compile(r'(?:放到|留到|留给|等到|我们到|见|参见)?(?:第\s*(\d+)\s*章|(终章))(?:和第\s*(\d+)\s*章)?(?:[^。；]{0,12}?)'
                r'(再说|再讲|再细说|会讲|会回到|还会回到|会再|再碰|展开|细说|专门讲|讲到|回到这)')
def selfref(n):   # 该章在别处被称呼的写法
    return '序章' if n==0 else ('终章' if n==26 else '第%d章'%n)
rows=[]
for src,txt in sorted(B.items()):
    for m in PROM.finditer(txt):
        tgts=[]
        if m.group(2): tgts.append(26)                       # 「终章」
        for gt in (m.group(1),m.group(3)):                   # 「第 N 章」「…和第 M 章」
            if gt: tgts.append(int(gt))
        for tgt in dict.fromkeys(tgts):                      # 去重，保序
            if tgt<=src or tgt not in B: continue
            rows.append((src,tgt,selfref(src) in B[tgt],txt[max(0,m.start()-45):m.end()+8]))
back=[r for r in rows if r[2]]; noback=[r for r in rows if not r[2]]
print('前向承诺 %d 条 | 目标章有回指 %d 条 | 无回指（待人工核）%d 条\n'%(len(rows),len(back),len(noback)))
for s,t,_,ctx in noback:
    print('  ch%02d → 第%-2d章   …%s…'%(s,t,ctx[:96]))
print('\n（有回指的 %d 条视为已兑现，不逐条列；如需全量加 --all）'%len(back))
if '--all' in sys.argv:
    for s,t,_,c in back: print('  ch%02d → 第%d章 ✔'%(s,t))
