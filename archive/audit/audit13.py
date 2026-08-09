# -*- coding: utf-8 -*-
import os as _os
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"..",".."))  # 存档件：相对路径从仓库根解析，可在任意目录调用
"""#7 专项第 ⑬ 条：正文外字符串审计器。只读，不改文件。
产出 = 每章一份『正文外字符串』清单（供人眼过），外加两项高精度扫描。"""
import re,sys,os

def strip(h): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',h)).strip()

SLOTS=[('title',r'<title>(.*?)</title>'),('crumbs',r'<nav class="crumbs">(.*?)</nav>'),
 ('series',r'<div class="series">(.*?)</div>'),('h1',r'<h1>(.*?)</h1>'),
 ('subtitle',r'<p class="subtitle">(.*?)</p>'),('meta',r'<div class="meta">(.*?)</div>'),
 ('eyebrow',r'<div class="eyebrow">(.*?)</div>'),('h2',r'<h2>(.*?)</h2>'),('h3',r'<h3>(.*?)</h3>'),
 ('figcaption',r'<figcaption>(.*?)</figcaption>'),('tag',r'<span class="tag">(.*?)</span>'),
 ('stamp',r'<div class="stamp">(.*?)</div>'),('spec.head',r'<div class="spec-head">(.*?)</div>'),
 ('spec.k',r'<td class="k">(.*?)</td>'),('spec.v',r'<td class="v">(.*?)</td>'),('spec.n',r'<td class="n">(.*?)</td>'),
 ('quiz.qt',r'<div class="qt">(.*?)</div>'),('quiz.opt',r'<button(?:\s+data-c="1")?>(.*?)</button>'),
 ('quiz.explain',r'<div class="explain">(.*?)</div>'),('next.label',r'<div class="label">(.*?)</div>'),
 ('next.title',r'<div class="title">(.*?)</div>')]

# 工业/计算机 register 词表（红线 2）——出现在正文外字符串里尤其刺眼
REG=['流水线','生产线','下线','出厂','车间','工厂','装配','组装','机器','引擎','发动机','马达'
    ,'电路','程序','代码','芯片','软件','硬件','数据库','缓存','接口','模块','算法','开关电源'
    ,'管道','阀门','传感器','控制器','服务器','网络','信号塔','齿轮','杠杆','泵站','电池','充电']
REG_OK={'马达蛋白','分子机器','旋转分子机器','钠钾泵'}   # 学名/已裁定合规，不计
ABS=['最','唯一','所有','永远','从不','第一个','必然','完全','彻底']

def slots(html):
    out=[]
    for k,p in SLOTS:
        for m in re.finditer(p,html,re.S):
            t=strip(m.group(1))
            if t: out.append((k,t))
    for m in re.finditer(r'<svg.*?</svg>',html,re.S):
        for t in re.finditer(r'<text[^>]*>(.*?)</text>',m.group(0),re.S):
            s=strip(t.group(1))
            if s: out.append(('svg.text',s))
    return out

def scan(path,dump=False):
    html=open(path,encoding='utf-8').read()
    S=slots(html)
    reg=[];ab=[]
    for k,t in S:
        for w in REG:
            for m in re.finditer(w,t):
                ctx=t[max(0,m.start()-4):m.start()+len(w)+4]
                if any(ok in t[max(0,m.start()-3):m.start()+len(w)+3] for ok in REG_OK): continue
                reg.append((k,w,t))
        if k in ('h1','h2','h3','eyebrow','subtitle','spec.k','spec.v','svg.text','next.title'):
            for w in ABS:
                if w in t and w+'之一' not in t and '最后' not in t and '最初' not in t:
                    ab.append((k,w,t))
    if dump:
        print('---- %s · 正文外字符串 %d 条 ----'%(os.path.basename(path),len(S)))
        for k,t in S: print('  %-11s %s'%(k,t))
    return S,reg,ab

if __name__=='__main__':
    dump = '--dump' in sys.argv
    files=[a for a in sys.argv[1:] if a.endswith('.html')]
    R=A=N=0
    for p in files:
        if not os.path.exists(p): continue
        S,reg,ab=scan(p,dump)
        N+=len(S); R+=len(reg); A+=len(ab)
        if reg or ab:
            print('== %s =='%os.path.basename(p))
            for k,w,t in reg: print('   [register] 「%s」 @%-11s %s'%(w,k,t[:52]))
            for k,w,t in ab:  print('   [绝对化]   「%s」 @%-11s %s'%(w,k,t[:52]))
    print('\n正文外字符串 %d 条 | register 命中 %d | 绝对化（仅标题/短串位）%d'%(N,R,A))
