#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================================
# 【存档件 v2 · 原作者 writer-09-12 ·《人体手册》构建期自查工具】
# 未并入 check.py（lead 裁定：收官阶段不扩检查面）。v1 已作废，本件为替换版。
#
# 存档复核（由 infra 执行，结论已报 lead）：
#
# ✅ v2 已修好的两处（复核确认，作者结论可复现）：
#    1. difflib 的 autojunk。默认 True 时，长度 >200 的序列会把频次 >1% 的元素
#       当噪声丢弃；中文按字比对时高频字必然入选，长重合被腰斩。v2 全部显式
#       写 autojunk=False。**任何按字比对中文的 difflib 用法都要这么写**，
#       这个坑对中文是普遍的，不限于本脚本。
#    2. A 项改为包含性检查（页脚是否含下一章 <title> 正文部分），不再用
#       "最长公共子串"——后者会被正文里的巧合重合盖过标题串。
#    实跑复现：A 26 条链路全部到位；B 3 处；C 全部齐整。与作者所报一致。
#
# ⚠ v2 仍存在的一处假阴性（移植前建议一并修）：
#    B 项的 longest() 只取「唯一的最长匹配」，若它恰是体例串，**整对章节即被
#    丢弃**，排在其后的真实重合永远看不见。实测 ch07 ⇄ ch08：
#        1. 32 字「。前沿窗口·FRONTIER本栏内容更新较快·截至2026-08」← 体例串，整对被丢
#        2. 26 字「章人体手册·THEHUMANBODYHANDBOOK」             ← 体例串
#        3. 20 字「分钟图2·测验5·前沿窗口1规格表12项」            ← 章头 .meta，BOILERPLATE 漏收
#        4. 18 字「胎盘像树根扎进土壤那样扎进母亲的血流」          ← 真实重合，v2 看不见
#    修法：改用 get_matching_blocks() 按长度降序遍历，逐个剔除体例串后再判定。
#    连带：这么改之后 BOILERPLATE 必须补上章头与面包屑体例串，否则满屏假阳性：
#        '阅读≈\d+分钟', '图\d+·测验\d+·前沿窗口', '规格表\d+项',
#        '—人体手册☾夜间目录第.幕'
#
# 📌 本书的实际结论（内容层面）：干净。修正后扫出的 4 处跨章重合
#    （ch00⇄ch01 81 字、ch00⇄ch20 77 字、ch01⇄ch23 33 字、ch07⇄ch08 18 字）
#    经人工核对**全部是有意为之的呼应，且都在文中显式点明**：
#      「序章里用过一对说法，这一章从它接着往下讲」
#      「第 1 章预告过这一节」
#      「样章里说过…这句话方向是对的，但值得在这里补精确一点」（随后改用红树林类比）
#    不是复制粘贴事故，无需修改。
#
# 🔑 留给下一本书的教训（与 BUILD_SPEC §7b.15 同源）：
#    v1 曾报「全书 B 项 0 处」——那不是通过，是看不见。**绿灯既可能是「没问题」，
#    也可能是「没看」，两者在输出上完全一样。**原作者在 v1 的移植提示里写了
#    "将来并入前要做变异测试"，却没对 v1 自己做——这份档案就是那条建议的
#    现成反面教材。移植时：先注入一处已知撞车，确认 B 抓得到，再谈结论。
#
#    补两条，都来自本轮的实际经过：
#
#    (a) **发现 bug 的可复制方法：找检查项之间打架的结论。** autojunk 是这样
#        暴露的——A 项报「ch00→ch01 重合 81 字」，B 项比对同一对章节却报 0。
#        同一份数据，两个检查项给出互相矛盾的答案，就是 bug 的指纹。这比
#        "凭经验觉得哪里不对"可复制得多：设计多项检查时，**有意让它们的
#        覆盖面部分重叠**，重叠区就是免费的交叉验证。
#
#    (b) **修完之后仍然要做变异测试。** v1 的绿灯不能当证据，v2 的绿灯同样
#        不能。v2 专门重写过 longest()（加 autojunk=False），却没发现它的
#        返回值只有一个匹配块——修的时候眼里只有那一个参数。§7b.15 管的正是
#        这一刻：**改动之后的第一次全绿，必须用当前代码现场注入兑现。**
# ============================================================================

"""coupling_scan.py v2 — 跨章耦合扫描（构建期自查，未并入 check.py）

  A 页脚预告 ⇄ 被预告章标题：第 N 章页脚须复述第 N+1 章标题（契约体例）。
  B 跨章长串逐字重合：排除体例句后 ≥14 字的整段撞车（复制粘贴/伏笔半改）。
  C 前沿窗口体例齐整性：stamp 数与窗口数应相等。

零第三方依赖。用法：
    python3 coupling_scan.py                 # 扫全书（须在项目根运行）
    python3 coupling_scan.py ch09 ch10       # 只关注这几章（仍与全书比对）
退出码恒为 0：只报告，不做成败判定。
"""

import difflib, glob, os, re, sys
MIN_OVERLAP = 14
BOILERPLATE = [
    '若在20\\d\\d年后重读此栏，请先核实',
    '本栏内容更新较快·截至20\\d\\d-\\d\\d',
    '人体手册·THEHUMANBODYHANDBOOK',
    '前沿窗口·FRONTIER', '旁注·SIDENOTE',
    'SPECSHEET', 'SELF-CHECK', '本章规格表', '本章测验',
]
def norm(t): return re.sub(r'\s+', '', t)
def plain(path):
    s = open(path, encoding='utf-8').read()
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', s, flags=re.S)
    return norm(re.sub(r'<[^>]+>', '', s))
def footer(path):
    s = open(path, encoding='utf-8').read()
    m = re.search(r'<footer class="next">(.*?)</nav>', s, re.S)
    return norm(re.sub(r'<[^>]+>', '', m.group(1))) if m else ''
def chapter_title(path):
    s = open(path, encoding='utf-8').read()
    m = re.search(r'<title>(.*?)</title>', s, re.S)
    return norm(re.sub(r'—\s*人体手册\s*$', '', m.group(1))) if m else ''
def longest(a, b):
    m = difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size, a[m.a:m.a + m.size]
def main():
    files = sorted(glob.glob('chapters/ch*.html'))
    sel = files
    print('A · 页脚预告须复述下一章标题（包含性检查）')
    bad = 0
    for i, f in enumerate(files[:-1]):
        nxt = files[i + 1]
        t = chapter_title(nxt)
        if not (t and t in footer(f)):
            bad += 1
            print('   ✗ %-24s 页脚未复述「%s」' % (os.path.basename(f), t))
    print('   全部复述到位' if not bad else '   %d 条链路缺标题复述' % bad)
    print('\nB · 跨章长串逐字重合（≥%d 字，排除体例句）' % MIN_OVERLAP)
    cache = {f: plain(f) for f in files}
    hits, seen = [], set()
    for a in sel:
        for b in files:
            if a == b: continue
            k = tuple(sorted((a, b)))
            if k in seen: continue
            seen.add(k)
            n, seg = longest(cache[a], cache[b])
            if n >= MIN_OVERLAP and not any(re.search(p, seg) for p in BOILERPLATE):
                hits.append((n, os.path.basename(a), os.path.basename(b), seg))
    for n, a, b, seg in sorted(hits, reverse=True):
        print('   %-22s ⇄ %-22s %3d 字 「%s」' % (a, b, n, seg[:44]))
    if not hits: print('   （无）')
    print('\n共 %d 处' % len(hits))
    return 0
if __name__ == '__main__':
    sys.exit(main())
