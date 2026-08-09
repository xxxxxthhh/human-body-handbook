# -*- coding: utf-8 -*-
import os as _os
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"..",".."))  # 存档件：相对路径从仓库根解析，可在任意目录调用
"""#7 口吻与字符串侧审计（只读）。机械三角测量 → 定位需人眼细读的章节。"""
import re,os,glob,sys

# 收窄后的工业/计算机 register 词表（已剔除解剖学译名与学名：管道/程序/算法/网络/机器/泵/开关/系统/调试/重启）
REG=['流水线','生产线','下线','出厂','车间','工厂','装配','组装','引擎','发动机','电路','代码','芯片',
     '软件','硬件','数据库','缓存','服务器','内存','带宽','编译','齿轮','传送带','阀门','电机','电池','焊']
ABS=['最','唯一','所有','永远','从不','第一个','必然','完全','彻底']
TITLE_SLOTS={'h1','h2','h3','eyebrow','subtitle','spec.k','spec.v','svg.text','next.title'}
SLOTS=[('title',r'<title>(.*?)</title>'),('crumbs',r'<nav class="crumbs">(.*?)</nav>'),
 ('series',r'<div class="series">(.*?)</div>'),('h1',r'<h1>(.*?)</h1>'),('subtitle',r'<p class="subtitle">(.*?)</p>'),
 ('meta',r'<div class="meta">(.*?)</div>'),('eyebrow',r'<div class="eyebrow">(.*?)</div>'),
 ('h2',r'<h2>(.*?)</h2>'),('h3',r'<h3>(.*?)</h3>'),('figcaption',r'<figcaption>(.*?)</figcaption>'),
 ('tag',r'<span class="tag">(.*?)</span>'),('stamp',r'<div class="stamp">(.*?)</div>'),
 ('spec.head',r'<div class="spec-head">(.*?)</div>'),('spec.k',r'<td class="k">(.*?)</td>'),
 ('spec.v',r'<td class="v">(.*?)</td>'),('spec.n',r'<td class="n">(.*?)</td>'),
 ('quiz.qt',r'<div class="qt">(.*?)</div>'),('quiz.opt',r'<button(?:\s+data-c="1")?>(.*?)</button>'),
 ('quiz.explain',r'<div class="explain">(.*?)</div>'),('next.label',r'<div class="label">(.*?)</div>'),
 ('next.title',r'<div class="title">(.*?)</div>')]

def st(h): return re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',h)).strip()
def han(t): return len(re.findall(r'[一-鿿]',t))

def load(p):
    h=open(p,encoding='utf-8').read()
    b=re.sub(r'<script.*?</script>','',re.search(r'<body.*?</body>',h,re.S).group(0),flags=re.S)
    nosvg=re.sub(r'<svg.*?</svg>','',b,flags=re.S)
    return h,b,nosvg

def slots(h):
    out=[]
    for k,p in SLOTS:
        for m in re.finditer(p,h,re.S):
            t=st(m.group(1))
            if t: out.append((k,t))
    for m in re.finditer(r'<svg.*?</svg>',h,re.S):
        for t in re.finditer(r'<text[^>]*>(.*?)</text>',m.group(0),re.S):
            s=st(t.group(1))
            if s: out.append(('svg.text',s))
    return out

def report(p):
    h,b,nosvg=load(p)
    name=os.path.basename(p)
    lede=st(re.search(r'<div class="lede">(.*?)</div>',nosvg,re.S).group(1)) if re.search(r'<div class="lede">',nosvg) else ''
    secs=[(st(a),st(c)) for a,c in re.findall(r'<div class="eyebrow">(.*?)</div>\s*<h2>(.*?)</h2>',nosvg,re.S)]
    body=st(re.sub(r'<[^>]+>',' ',nosvg))
    # 第二人称密度
    you=len(re.findall('你',body)); dens=you/max(han(body),1)*1000
    lyou=len(re.findall('你',lede))
    # 历史锚点信号
    years=sorted(set(re.findall(r'(1[6-9]\d{2}|20[0-2]\d)\s*年',body)))
    names=sorted(set(re.findall(r'[一-龥]{1,4}·[一-龥]{2,6}',body)))
    # register / 绝对化
    S=slots(h)
    reg=[(k,w,t) for k,t in S for w in REG if w in t]
    regb=[(w,body[max(0,m.start()-14):m.start()+len(w)+14]) for w in REG for m in re.finditer(w,body)]
    ab=[(k,w,t) for k,t in S if k in TITLE_SLOTS for w in ABS
        if w in t and (w+'之一') not in t and '最后' not in t and '最初' not in t and '最早' not in t]
    # 孕周口径
    gest=re.findall(r'孕\s*\d+\s*(?:周|个月)|第\s*\d+\s*周',body)
    declared=bool(re.search(r'孕龄|胚龄|末次月经',h))
    return dict(name=name,lede=lede,secs=secs,han=han(body),you=you,dens=dens,lyou=lyou,
                years=years,names=names,reg=reg,regb=regb,ab=ab,gest=len(gest),decl=declared,slots=len(S))

if __name__=='__main__':
    mode=sys.argv[1] if len(sys.argv)>1 else 'tri'
    files=sorted(glob.glob('chapters/ch*.html'))
    if mode=='tri':
        print('%-26s %5s %4s %6s %4s %5s %5s %4s %4s %s'%('章','汉字','你','你/千字','引子你','年份','人名','reg','绝对','孕周口径'))
        for f in files:
            r=report(f)
            flag=''
            if r['dens']<3: flag+=' ⚑第二人称稀'
            if not r['years'] and not r['names']: flag+=' ⚑无历史锚点'
            if r['reg'] or r['regb']: flag+=' ⚑register'
            if r['gest'] and not r['decl']: flag+=' ⚑孕周未声明口径'
            print('%-26s %5d %4d %6.1f %4d %5d %5d %4d %4d  %-3s%s'%(
                r['name'],r['han'],r['you'],r['dens'],r['lyou'],len(r['years']),len(r['names']),
                len(r['regb']),len(r['ab']),'已声明' if r['decl'] else ('—' if not r['gest'] else '未声明'),flag))
