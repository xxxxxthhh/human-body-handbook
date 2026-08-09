import os as _os
_os.chdir(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)),"..",".."))  # 存档件：相对路径从仓库根解析，可在任意目录调用
import re,sys,pathlib
SHARED=set(re.findall(r'\.([A-Za-z][\w-]*)',
    re.sub(r'/\*.*?\*/','',pathlib.Path('assets/style.css').read_text(encoding='utf-8'),flags=re.S)))
for fn in sys.argv[1:]:
    s=pathlib.Path(fn).read_text(encoding='utf-8')
    inline=''.join(re.findall(r'<style\b[^>]*>(.*?)</style>',s,re.S))
    defined=set(re.findall(r'\.([A-Za-z][\w-]*)',re.sub(r'/\*.*?\*/','',inline,flags=re.S)))|SHARED
    body=s[s.index('<body'):]
    used=set(c for a in re.findall(r'class="([^"]+)"',body) for c in a.split())
    used|=set(c for a in re.findall(r"classList\.(?:toggle|add)\('([\w-]+)'",s) for c in a.split())
    print('%-30s 未定义 class: %s' % (fn.split('/')[-1], sorted(used-defined) or '无'))

    # CJK 字宽估算：中日韩全角≈1.0em，ASCII≈0.55em
    def w(t,fs):
        return sum(fs*(1.0 if ord(ch)>0x2E80 else 0.55) for ch in t)
    FS={}
    for sel,body_ in re.findall(r'#[\w-]+\s+\.([\w-]+)\s*\{([^}]*)\}',inline):
        m=re.search(r'font-size:\s*([\d.]+)px',body_)
        if m: FS[sel]=float(m.group(1))
    over=[]
    for svg in re.findall(r'<svg\b[^>]*viewBox="0 0 (\d+) (\d+)"(.*?)</svg>',s,re.S):
        VW=int(svg[0])
        for tag,txt in re.findall(r'(<text\b[^>]*>)(.*?)</text>',svg[2],re.S):
            txt=re.sub(r'<[^>]+>','',txt).strip()
            if not txt: continue
            cls=(re.search(r'class="([^"]+)"',tag) or [None,''])[1].split()
            fs=next((FS[c] for c in cls if c in FS),12.0)
            fsm=re.search(r'font-size="([\d.]+)"',tag)
            if fsm: fs=float(fsm.group(1))
            x=float(re.search(r'\sx="([-\d.]+)"',tag).group(1))
            anc=(re.search(r'text-anchor="(\w+)"',tag) or [None,'start'])[1]
            wd=w(txt,fs)
            lo = x if anc=='start' else x-wd/2 if anc=='middle' else x-wd
            if lo< -1 or lo+wd> VW+1:
                over.append('%.0f–%.0f / %d 「%s」'%(lo,lo+wd,VW,txt[:22]))
    print('%-30s SVG 文本越界: %s'%('',over or '无'))
