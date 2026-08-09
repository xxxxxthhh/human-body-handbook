#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tools/check.py — 《人体手册》全站结构 / 导航 / 计数校验

零第三方依赖（stdlib：re / html.parser / pathlib / argparse）。
契约来源：BUILD_SPEC.md（文件地图与标题从中程序化解析，不在本脚本硬编码）。

用法：
    python3 tools/check.py                 # 校验项目根目录
    python3 tools/check.py --strict        # 缺文件 / 死链 由 WARN 升级为 FAIL
    python3 tools/check.py --root DIR      # 校验另一棵目录树（变异测试用）
    python3 tools/check.py --no-report     # 不打印绝对化表述清单

退出码：0 = 无 FAIL；1 = 有 FAIL。--strict 下 WARN 亦计入失败。

检查项（编号与 lead 任务书一致）：
    0  解析：标签闭合完整（其他检查的前提）
    1  文件地图齐全
    2  每章结构：章头/面包屑/引子/小节/图/前沿窗口/规格表/测验/页脚
    3  .meta 三段数字与实际内容一致
    4  导航链：面包屑、footnav 上下章、index 全章链接、相对链接可达
    5  无外部资源
    6  #themeBtn 与 prefers-reduced-motion
    7  绝对化表述（仅 REPORT，不计入成败）
    8  <title> 与 BUILD_SPEC 一致
    9  SVG 字面色值（<svg> 属性 + 样式表 fill/stroke 声明）—— FAIL
   10  使用了未定义样式的 class —— WARN
   11  SVG 块 XML 合法性 —— FAIL
   12  SVG 文本越界 / 重叠估算 —— WARN（宽度为估算值）
"""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

# ============================================================
# HTML 解析：足够支撑结构检查的极简 DOM + 闭合校验
# ============================================================

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
        'link', 'meta', 'param', 'source', 'track', 'wbr'}
# HTML5 允许省略结束标签的元素——未闭合不算错误
OPTIONAL_END = {'p', 'li', 'td', 'th', 'tr', 'tbody', 'thead', 'tfoot',
                'dt', 'dd', 'option'}
# 这些开始标签会隐式关闭上一个未闭合的 <p>
CLOSES_P = {'p', 'div', 'section', 'figure', 'figcaption', 'ul', 'ol', 'table',
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'footer', 'nav',
            'blockquote', 'pre', 'hr', 'li', 'aside', 'form', 'article', 'main'}


class Node:
    __slots__ = ('tag', 'attrs', 'classes', 'content', 'parent', 'line')

    def __init__(self, tag, attrs, line):
        self.tag = tag
        self.attrs = {k: (v if v is not None else '') for k, v in attrs}
        self.classes = set(self.attrs.get('class', '').split())
        self.content = []          # 混合内容：str 或 Node，保持文档顺序
        self.parent = None
        self.line = line


class Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#document', [], 0)
        self.stack = [self.root]
        self.errors = []

    # -- 内部 --
    def _push(self, tag, attrs, push):
        node = Node(tag, attrs, self.getpos()[0])
        node.parent = self.stack[-1]
        self.stack[-1].content.append(node)
        if push:
            self.stack.append(node)

    def _auto_close(self, tag):
        while len(self.stack) > 1:
            top = self.stack[-1].tag
            if top == 'p' and tag in CLOSES_P:
                self.stack.pop()
            elif top == 'li' and tag == 'li':
                self.stack.pop()
            elif top in ('td', 'th') and tag in ('td', 'th', 'tr'):
                self.stack.pop()
            elif top == 'tr' and tag == 'tr':
                self.stack.pop()
            else:
                break

    # -- HTMLParser 回调 --
    def handle_starttag(self, tag, attrs):
        self._auto_close(tag)
        self._push(tag, attrs, push=tag not in VOID)

    def handle_startendtag(self, tag, attrs):
        self._auto_close(tag)
        self._push(tag, attrs, push=False)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for k in range(len(self.stack) - 1, 0, -1):
            if self.stack[k].tag == tag:
                for n in self.stack[k + 1:]:
                    if n.tag not in OPTIONAL_END:
                        self.errors.append(
                            '第 %d 行 <%s> 未闭合（被 </%s> 截断）' % (n.line, n.tag, tag))
                del self.stack[k:]
                return
        self.errors.append('第 %d 行 </%s> 没有对应的开始标签' % (self.getpos()[0], tag))

    def handle_data(self, data):
        self.stack[-1].content.append(data)

    def finish(self):
        self.close()
        for n in self.stack[1:]:
            if n.tag not in OPTIONAL_END:
                self.errors.append('第 %d 行 <%s> 未闭合（文件结束）' % (n.line, n.tag))


def parse(text):
    b = Builder()
    b.feed(text)
    b.finish()
    return b.root, b.errors


def walk(node):
    for c in node.content:
        if isinstance(c, Node):
            yield c
            for g in walk(c):
                yield g


def find(node, tag=None, cls=None, node_id=None):
    out = []
    for n in walk(node):
        if tag and n.tag != tag:
            continue
        if cls and cls not in n.classes:
            continue
        if node_id and n.attrs.get('id') != node_id:
            continue
        out.append(n)
    return out


def first(node, **kw):
    got = find(node, **kw)
    return got[0] if got else None


def text_of(node):
    parts = []

    def rec(n):
        for c in n.content:
            if isinstance(c, str):
                parts.append(c)
            elif c.tag not in ('script', 'style'):
                rec(c)
    rec(node)
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


# ============================================================
# BUILD_SPEC 契约解析
# ============================================================

def load_filemap(spec_path):
    """从 BUILD_SPEC 第 1 节代码块解析 [(路径, 标题)]，标题去掉尾部（注记）。"""
    text = spec_path.read_text(encoding='utf-8')
    block = re.search(r'```\n(.*?)```', text, re.S)
    if not block:
        raise SystemExit('无法从 %s 解析文件地图代码块' % spec_path)
    entries = []
    for line in block.group(1).splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        parts = re.split(r'\s{2,}', line.strip(), maxsplit=1)
        path = parts[0]
        desc = parts[1].strip() if len(parts) > 1 else ''
        desc = re.sub(r'（[^）]*）\s*$', '', desc).strip()
        entries.append((path, desc))
    return entries


def chapter_label(path):
    """ch08-birth.html -> ('8', 8)；ch00 -> ('序', 0)；ch26 -> ('终', 26)"""
    m = re.search(r'ch(\d\d)-', path)
    n = int(m.group(1))
    if n == 0:
        return '序', 0
    if n == 26:
        return '终', 26
    return str(n), n


# ============================================================
# 报告
# ============================================================

class Report:
    def __init__(self):
        self.files = []          # [(name, [(level, msg), ...])]
        self.notes = []          # 绝对化表述

    def add(self, name):
        self.files.append((name, []))
        return self.files[-1][1]


LEVELS = {'PASS': 0, 'WARN': 1, 'FAIL': 2}


# ============================================================
# 单页检查
# ============================================================

ABSOLUTE_TERMS = ['最', '唯一', '所有', '永远', '从不', '第一个']


def check_no_external(doc, css_texts, issues):
    """检查 5：link/script/img/@font-face 不得引用 http(s)://（svg 的 xmlns 不算）"""
    bad = []
    for n in walk(doc):
        for attr in ('href', 'src'):
            if n.tag not in ('link', 'script', 'img'):
                continue
            v = n.attrs.get(attr, '')
            if re.match(r'https?://', v):
                bad.append('第 %d 行 <%s %s="%s">' % (n.line, n.tag, attr, v))
    for css in css_texts:
        for m in re.finditer(r'(@import[^;]*|url\(\s*[\'"]?)https?://', css):
            bad.append('样式表引用了外部地址：%s…' % m.group(0)[:40])
    if bad:
        issues.append(('FAIL', '存在外部资源引用：' + '；'.join(bad)))


def collect_css(doc):
    out = []
    for n in find(doc, tag='style'):
        out.append(''.join(c for c in n.content if isinstance(c, str)))
    return out


# SVG 里承载颜色的属性；style 属性内的 fill:/stroke: 一并覆盖
COLOR_ATTRS = ('fill', 'stroke', 'stop-color', 'flood-color', 'lighting-color',
               'color', 'style')
# 关键字取值不是字面色值，放行
COLOR_KEYWORDS = {'none', 'currentcolor', 'transparent', 'inherit', 'initial',
                  'unset', 'context-fill', 'context-stroke'}
# 具名颜色与十六进制同样不随昼夜切换，一并拦截
NAMED_COLORS = {'white', 'black', 'red', 'blue', 'green', 'yellow', 'orange',
                'purple', 'gray', 'grey', 'pink', 'brown', 'cyan', 'magenta',
                'silver', 'gold', 'navy', 'teal', 'lime', 'maroon', 'olive',
                'aqua', 'fuchsia', 'darkgray', 'darkgrey', 'lightgray',
                'lightgrey', 'beige', 'ivory', 'crimson', 'salmon'}


def check_svg_colors(doc, issues):
    """检查 9：<svg> 内不得出现字面色值——颜色必须走 CSS 变量，否则浅色模式失明。"""
    bad = []
    for svg in find(doc, tag='svg'):
        for n in [svg] + list(walk(svg)):
            for attr in COLOR_ATTRS:
                raw_val = n.attrs.get(attr)
                if not raw_val:
                    continue
                # url(#grad) 之类的引用不是色值，先剔除，避免把 id 当成十六进制
                val = re.sub(r'url\([^)]*\)', '', raw_val)
                val = re.sub(r'var\([^)]*\)', '', val)
                hexes = re.findall(r'#[0-9A-Fa-f]{3,8}\b|(?:rgba?|hsla?)\([^)]*\)', val)
                named = []
                for word in re.findall(r'[A-Za-z][A-Za-z-]*', val):
                    w = word.lower()
                    if w in NAMED_COLORS and w not in COLOR_KEYWORDS:
                        named.append(word)
                for lit in hexes + named:
                    bad.append('第 %d 行 <%s %s="%s">' % (n.line, n.tag, attr, raw_val[:48]))
                    break
    if bad:
        issues.append(('FAIL', 'SVG 内使用了字面色值（必须改用 var(--token)）：'
                       + '；'.join(bad[:8])
                       + ('… 共 %d 处' % len(bad) if len(bad) > 8 else '')))


# fill/stroke 等只作用于 SVG，扫它们不会撞上设计令牌（--bg:#0F1216 是自定义属性）
# 也不会撞上 ::selection{color:#111}（那是 color:，不在此列）
SVG_COLOR_PROPS = r'(?<![-\w])(?:fill|stroke|stop-color|flood-color|lighting-color)\s*:\s*([^;}]+)'


def check_css_svg_colors(css_texts, issues, where):
    """检查 9 续：样式表里给 SVG 上色的声明同样必须走变量。

    章内 <style> 才是 SVG 上色的主战场（样章整张电路图都在那里着色），
    只扫 <svg> 属性会漏掉同一个缺陷。
    """
    bad = []
    for css in css_texts:
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        for m in re.finditer(SVG_COLOR_PROPS, css):
            val = re.sub(r'var\([^)]*\)|url\([^)]*\)', '', m.group(1))
            named = [w for w in re.findall(r'[A-Za-z][A-Za-z-]*', val)
                     if w.lower() in NAMED_COLORS]
            if re.search(r'#[0-9A-Fa-f]{3,8}\b|(?:rgba?|hsla?)\(', val) or named:
                bad.append('%s{…%s}' % (where, m.group(0).strip()[:40]))
    if bad:
        issues.append(('FAIL', '样式表中给 SVG 上色用了字面色值（必须改用 var(--token)）：'
                       + '；'.join(bad[:6])
                       + ('… 共 %d 处' % len(bad) if len(bad) > 6 else '')))


SVG_BLOCK = re.compile(r'<svg\b.*?</svg>', re.S)
XML_ENTITIES = {'amp', 'lt', 'gt', 'quot', 'apos'}


def _svg_for_xml(block):
    """把 HTML 具名实体换成占位符——内联 SVG 由 HTML 解析器处理，&nbsp; 等
    在浏览器里合法，但 XML 解析器不认；不中和会造成假 FAIL。"""
    return re.sub(r'&([A-Za-z][A-Za-z0-9]*);',
                  lambda m: m.group(0) if m.group(1) in XML_ENTITIES else '_', block)


def check_svg_wellformed(raw, issues):
    """检查 11：每个 <svg> 块必须是合法 XML。

    手写 SVG 漏个 </g>、属性少个引号，浏览器可能静默吞掉整块图——页面不报错，
    图直接不见。零误报，故判 FAIL。解析的是原始源码而非重新序列化的 DOM，
    以保住 viewBox / textLength 这类大小写敏感的属性名。
    """
    import xml.etree.ElementTree as ET
    for m in SVG_BLOCK.finditer(raw):
        line0 = raw.count('\n', 0, m.start()) + 1
        try:
            ET.fromstring(_svg_for_xml(m.group(0)))
        except ET.ParseError as e:
            el, ec = e.position
            issues.append(('FAIL', '第 %d 行起的 <svg> 不是 XML 严格合法（本书规范）：%s'
                           '（块内第 %d 行第 %d 列，约当文件第 %d 行）。'
                           '漏闭合标签浏览器可能整块吞掉；属性不加引号一类浏览器虽能渲染，'
                           '但校验器无法解析该块，检查 12（文本越界/重叠）会对这张图静默失效'
                           % (line0, e.msg.split(':')[0], el, ec, line0 + el - 1)))


# ---- SVG 文本几何估算（收编自 pilot 的自查脚本，阈值放宽 + 祖先 transform 处理）----
GEOM_MARGIN = 4.0        # 越界容差：字宽估算误差约 ±8%
GEOM_OVERLAP = 6.0       # 两轴各需交叠超过此值才判重叠


def css_font_sizes(css):
    """class -> font-size(px)，从 CSS 收割，后定义覆盖先定义（与层叠同向）。"""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out = {}
    for sel, body in re.findall(r'(?:^|[{}])([^{}@]*)\{([^{}]*)\}', css):
        m = re.search(r'font-size:\s*([\d.]+)px', body)
        if not m:
            continue
        for cls in re.findall(r'\.(-?[A-Za-z_][\w-]*)', sel):
            out[cls] = float(m.group(1))
    return out


def css_hidden_classes(css):
    """收集出现在 opacity:0 规则里的 class。

    交互图常把两段文字叠在同一坐标、用 opacity 互斥切换（样章
    `.st-fetal` / `.st-after` 即是，BUILD_SPEC 要求每章 ≥1 张交互图，
    这个写法会反复出现）。这类"重叠"是设计意图，不能报。
    """
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    out = set()
    for sel, body in re.findall(r'(?:^|[{}])([^{}@]*)\{([^{}]*)\}', css):
        if not re.search(r'opacity:\s*0(?![.\d])', body):
            continue
        for cls in re.findall(r'\.(-?[A-Za-z_][\w-]*)', sel):
            out.add(cls)
    return out


def _text_width(s, fs, mono):
    w = 0.0
    for ch in s:
        o = ord(ch)
        wide = o > 0x2E80 or 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF or ch == '—'
        w += fs if wide else fs * (0.6 if mono else 0.55)
    return w


def check_svg_geometry(raw, css_texts, shared_css, issues):
    """检查 12（WARN）：SVG 文本越界 / 互相重叠的估算。

    坐标都合法、纯读代码看不出来的那类缺陷。宽度靠字符宽度估算（±8%），
    故一律 WARN 不 FAIL；带 transform 的文本无法可靠定位，列入"需人眼"清单，
    绝不静默放过。
    """
    import xml.etree.ElementTree as ET
    sizes = css_font_sizes(shared_css)
    hidden = css_hidden_classes(shared_css)
    for css in css_texts:
        sizes.update(css_font_sizes(css))
        hidden |= css_hidden_classes(css)

    for m in SVG_BLOCK.finditer(raw):
        line0 = raw.count('\n', 0, m.start()) + 1
        try:
            root = ET.fromstring(_svg_for_xml(m.group(0)))
        except ET.ParseError:
            continue                      # 合法性由检查 11 报，这里不重复
        vb = (root.get('viewBox') or '').split()
        if len(vb) != 4:
            continue
        W = float(vb[2])
        parent = {c: p for p in root.iter() for c in p}

        def tainted(el):
            """自身或任一祖先带 transform —— 框会落在错误的坐标系里。"""
            cur = el
            while cur is not None:
                if cur.get('transform'):
                    return True
                cur = parent.get(cur)
            return False

        boxes, skipped = [], []
        for el in root.iter():
            if el.tag.split('}')[-1] != 'text':
                continue
            s = ''.join(el.itertext()).strip()
            if not s:
                continue
            # 无法可靠估算的情形，一律列入需人眼，不当成通过
            if (tainted(el) or el.get('dx') or el.get('dy') or el.get('textLength')
                    or el.get('x') is None or el.get('y') is None
                    or any(t.get('x') or t.get('y') for t in el)):
                skipped.append(s[:14])
                continue
            cls = el.get('class') or ''
            fs = None
            if el.get('font-size'):
                try:
                    fs = float(re.sub(r'px$', '', el.get('font-size')))
                except ValueError:
                    fs = None
            if fs is None:
                for c in cls.split():
                    if c in sizes:
                        fs = sizes[c]
                        break
            fs = fs or 12.0
            try:
                x, y = float(el.get('x')), float(el.get('y'))
            except ValueError:
                skipped.append(s[:14])
                continue
            w = _text_width(s, fs, 'mono' in cls)
            a = el.get('text-anchor', 'start')
            lo = x - w / 2 if a == 'middle' else (x - w if a == 'end' else x)
            # 带 opacity:0 状态类的文本：显隐由 JS 状态决定，静态判不了重叠
            state = bool(set(cls.split()) & hidden)
            boxes.append((lo, lo + w, y - fs * 0.85, y + fs * 0.20, s, state))

        out = []
        for lo, hi, top, bot, s, _st in boxes:
            if lo < -GEOM_MARGIN or hi > W + GEOM_MARGIN:
                out.append('「%s」超出画布（x %.0f–%.0f，viewBox 宽 %.0f）' % (s[:14], lo, hi, W))
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[5] or b[5]:          # 互斥状态层，重叠是设计意图
                    continue
                ox = min(a[1], b[1]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[2], b[2])
                if ox > GEOM_OVERLAP and oy > GEOM_OVERLAP:
                    out.append('「%s」与「%s」重叠（约 %.0f×%.0f px）'
                               % (a[4][:12], b[4][:12], ox, oy))
        if out:
            issues.append(('WARN', '第 %d 行起的 SVG 文本疑似越界/重叠（宽度为估算值，请人眼确认）：'
                           % line0 + '；'.join(out[:6])
                           + ('… 共 %d 处' % len(out) if len(out) > 6 else '')))
        if skipped:
            issues.append(('WARN', '第 %d 行起的 SVG 有 %d 处文本无法自动估算'
                           '（带 transform/tspan 定位/textLength），需人眼确认：%s'
                           % (line0, len(skipped), '、'.join(skipped[:6]))))


def css_selector_classes(css):
    """从 CSS 中提取被定义过的 class 名。

    只扫选择器（每个 `{` 之前的片段），不扫声明值——否则 `transition:.35s`
    这类小数会被误当成类名。复合选择器（.quiz-q.done / html.light /
    #circuit.after）里的每一段都会被提取，这样 JS 运行时状态类不会误报。
    """
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    names = set()
    for sel in re.findall(r'(?:^|[{}])([^{}]*)\{', css):
        if sel.lstrip().startswith('@'):      # at-rule 前奏，其内部规则下一轮会匹配到
            continue
        for m in re.finditer(r'\.(-?[A-Za-z_][\w-]*)', sel):
            names.add(m.group(1))
    return names


def check_undefined_classes(doc, defined, issues):
    """检查 10：HTML 里用到、但共享表与本页内联 <style> 都没有定义的 class。"""
    used = {}
    for n in walk(doc):
        for c in n.classes:
            used.setdefault(c, n.line)
    unknown = sorted((c, ln) for c, ln in used.items() if c not in defined)
    if unknown:
        issues.append(('WARN', '使用了未定义样式的 class（拼错？还是漏写规则？）：'
                       + '；'.join('.%s（第 %d 行）' % (c, ln) for c, ln in unknown[:10])
                       + ('… 共 %d 个' % len(unknown) if len(unknown) > 10 else '')))


def check_page_common(doc, raw, css_texts, issues, css_has_rm, shared):
    """检查 5 / 6 / 9 / 10：外部资源、主题开关、reduced-motion、SVG 色值、未定义 class"""
    check_no_external(doc, css_texts, issues)
    if not find(doc, node_id='themeBtn'):
        issues.append(('FAIL', '缺少 #themeBtn 昼夜切换按钮'))
    if 'prefers-reduced-motion' not in raw and not css_has_rm:
        issues.append(('FAIL', '未见 prefers-reduced-motion（共享 style.css 中也没有）'))
    check_svg_colors(doc, issues)
    check_css_svg_colors(css_texts, issues, '章内 <style>')
    check_svg_wellformed(raw, issues)
    check_svg_geometry(raw, css_texts, shared['css'], issues)
    defined = set(shared['classes'])
    for css in css_texts:
        defined |= css_selector_classes(css)
    check_undefined_classes(doc, defined, issues)


def check_links(path, doc, root, issues, strict):
    """检查 4 尾项：所有相对 href/src 落在存在的文件上"""
    dead, dead_asset = [], []
    for n in walk(doc):
        attr = 'href' if n.tag in ('a', 'link') else 'src' if n.tag in ('script', 'img') else None
        if not attr:
            continue
        ref = n.attrs.get(attr, '').strip()
        if not ref or ref.startswith('#') or re.match(r'https?:|mailto:|data:', ref):
            continue
        if not (path.parent / ref.split('#')[0]).resolve().exists():
            (dead if n.tag == 'a' else dead_asset).append('第 %d 行 → %s' % (n.line, ref))
    # 资源（样式表/脚本/图片）断链一律 FAIL：页面会直接失去样式
    if dead_asset:
        issues.append(('FAIL', '资源引用指向不存在的文件：' + '；'.join(dead_asset)))
    # 章节间链接在批量写作期允许尚未存在
    if dead:
        issues.append(('FAIL' if strict else 'WARN',
                       '相对链接指向不存在的文件：' + '；'.join(dead)))


def check_chapter(path, rel, doc, raw, spec_title, prev_rel, next_rel,
                  issues, css_has_rm, strict, root, shared):
    label, num = chapter_label(rel)
    is_finale = (num == 26)
    is_prologue = (num == 0)
    css_texts = collect_css(doc)

    # ---- 8. title ----
    t = first(doc, tag='title')
    want = spec_title + ' — 人体手册'
    got = text_of(t) if t else ''
    if got != want:
        issues.append(('FAIL', '<title> 应为「%s」，实为「%s」' % (want, got)))

    # ---- 6/5. 通用 ----
    check_page_common(doc, raw, css_texts, issues, css_has_rm, shared)

    # ---- 2. 章头 / 面包屑 ----
    header = first(doc, tag='header', cls='chap')
    if not header:
        issues.append(('FAIL', '缺少 <header class="chap"> 章头'))
    crumbs = first(doc, cls='crumbs')
    if not crumbs:
        issues.append(('FAIL', '缺少 .crumbs 面包屑'))
    else:
        hrefs = [a.attrs.get('href', '') for a in find(crumbs, tag='a')]
        if '../index.html' not in hrefs:
            issues.append(('FAIL', '面包屑未链接 ../index.html'))
        ctext = text_of(crumbs)
        if is_prologue and '序章' not in ctext:
            issues.append(('FAIL', '序章面包屑应含「序章」，实为「%s」' % ctext))
        elif is_finale and '终章' not in ctext:
            issues.append(('FAIL', '终章面包屑应含「终章」，实为「%s」' % ctext))
        elif not (is_prologue or is_finale) and ('第 %d 章' % num) not in ctext:
            issues.append(('FAIL', '面包屑应含「第 %d 章」，实为「%s」' % (num, ctext)))

    # ---- 2. 引子 ----
    if not find(doc, cls='lede'):
        issues.append(('FAIL', '缺少 .lede 引子'))

    # ---- 2. 正文小节 ----
    prose = [s for s in find(doc, tag='section')
             if find(s, cls='eyebrow') and s.attrs.get('id') not in ('spec', 'quiz')]
    if len(prose) < 4:
        issues.append(('FAIL', '正文小节（含 .eyebrow）仅 %d 节，要求 ≥4' % len(prose)))
    elif len(prose) > 6:
        issues.append(('WARN', '正文小节 %d 节，CLAUDE.md 建议 4–6 节' % len(prose)))

    # ---- 2. 图表 ----
    figs = find(doc, tag='figure')
    if len(figs) < 2:
        issues.append(('FAIL', '手写 SVG 图表仅 %d 张，要求 ≥2' % len(figs)))
    for f in figs:
        cap = first(f, tag='figcaption')
        if not cap:
            issues.append(('FAIL', '第 %d 行的 <figure> 缺 figcaption' % f.line))
            continue
        m = re.search(r'图\s*([0-9]+|序|终)\s*[-–—]\s*(\d+)', text_of(cap))
        if not m:
            issues.append(('FAIL', '第 %d 行 figcaption 缺「图 %s-x」编号' % (cap.line, label)))
        elif m.group(1) != label:
            issues.append(('FAIL', '第 %d 行 figcaption 编号为「图 %s-%s」，本章应为「图 %s-x」'
                           % (cap.line, m.group(1), m.group(2), label)))
        if not find(f, tag='svg'):
            issues.append(('WARN', '第 %d 行的 <figure> 内没有 <svg>' % f.line))

    # ---- 2. 前沿窗口 ----
    frontier = [n for n in walk(doc) if {'callout', 'frontier'} <= n.classes]
    lo, hi = (1, 2) if num == 23 else (1, 1)
    if not (lo <= len(frontier) <= hi):
        issues.append(('FAIL', '前沿窗口 %d 个，本章应为 %s 个'
                       % (len(frontier), lo if lo == hi else '%d–%d' % (lo, hi))))
    for c in frontier:
        stamp = first(c, cls='stamp')
        if not stamp:
            issues.append(('FAIL', '第 %d 行前沿窗口缺 .stamp 日期戳' % c.line))
        elif not re.search(r'截至\s*20\d\d-\d\d', text_of(stamp)):
            issues.append(('FAIL', '第 %d 行前沿窗口日期戳格式应为「截至 YYYY-MM」，实为「%s」'
                           % (stamp.line, text_of(stamp))))

    # ---- 2. 规格表 ----
    spec_box = first(doc, cls='spec')
    rows = len(find(spec_box, tag='tr')) if spec_box else 0
    slo, shi = (6, 8) if is_finale else (10, 12)
    if not spec_box:
        issues.append(('FAIL', '缺少 .spec 规格表'))
    elif not (slo <= rows <= shi):
        issues.append(('FAIL', '规格表 %d 行，本章应为 %d–%d 行' % (rows, slo, shi)))

    # ---- 2. 测验 ----
    quizzes = find(doc, cls='quiz-q')
    if is_finale:
        if quizzes and not (4 <= len(quizzes) <= 6):
            issues.append(('WARN', '终章测验 %d 题（终章可免测验，若有则应 4–6 题）' % len(quizzes)))
    elif not (4 <= len(quizzes) <= 6):
        issues.append(('FAIL', '测验 %d 题，要求 4–6 题' % len(quizzes)))
    for q in quizzes:
        correct = [b for b in find(q, tag='button') if 'data-c' in b.attrs]
        if len(correct) != 1:
            issues.append(('FAIL', '第 %d 行测验题有 %d 个 data-c 正确项，应恰好 1 个'
                           % (q.line, len(correct))))

    # ---- 2/4. 页脚与三向导航 ----
    footer = first(doc, tag='footer', cls='next')
    if not footer:
        issues.append(('FAIL', '缺少 <footer class="next"> 预告块'))
        footnav = None
    else:
        footnav = first(footer, cls='footnav')
        if not footnav:
            issues.append(('FAIL', 'footer.next 内缺少 .footnav 三向导航'))
    if footnav:
        hrefs = [a.attrs.get('href', '') for a in find(footnav, tag='a')]
        if '../index.html' not in hrefs:
            issues.append(('FAIL', 'footnav 缺少返回目录链接 ../index.html'))
        if prev_rel:
            want_prev = prev_rel.split('/')[-1]
            if want_prev not in hrefs:
                issues.append(('FAIL', 'footnav 上一章应链接 %s' % want_prev))
        elif not find(footnav, cls='none'):
            issues.append(('FAIL', '序章无上一章，footnav 该位置应放 <span class="none">—</span>'))
        if next_rel:
            want_next = next_rel.split('/')[-1]
            if want_next not in hrefs:
                issues.append(('FAIL', 'footnav 下一章应链接 %s' % want_next))
        elif hrefs.count('../index.html') < 2:
            issues.append(('WARN', '终章下一章位应放「全书完 · 返回目录」链接指向 index'))

    # ---- 3. meta 三段数字与实际一致 ----
    meta = first(doc, cls='meta')
    if not meta:
        issues.append(('FAIL', '章头缺少 .meta（阅读时长 / 内容清单）'))
    else:
        mt = text_of(meta)
        expect = [('图', r'图\s*(\d+)', len(figs), True),
                  ('测验', r'测验\s*(\d+)', len(quizzes), not is_finale),
                  ('前沿窗口', r'前沿窗口\s*(\d+)', len(frontier), True),
                  ('规格表', r'规格表\s*(\d+)\s*项', rows, True)]
        for name, pat, actual, required in expect:
            m = re.search(pat, mt)
            if not m:
                if required:
                    issues.append(('FAIL', '.meta 未声明「%s N」' % name))
                continue
            if int(m.group(1)) != actual:
                issues.append(('FAIL', '.meta 声明%s %s，实际 %d'
                               % (name, m.group(1), actual)))
        if not re.search(r'阅读\s*[≈~约]?\s*\d+', mt):
            issues.append(('WARN', '.meta 未声明阅读时长'))

    # ---- 4. 死链 ----
    check_links(path, doc, root, issues, strict)


def check_index(path, doc, raw, chapters, issues, css_has_rm, strict, root, shared):
    css_texts = collect_css(doc)
    check_page_common(doc, raw, css_texts, issues, css_has_rm, shared)

    t = first(doc, tag='title')
    if not t or '人体手册' not in text_of(t):
        issues.append(('FAIL', '<title> 应含「人体手册」'))

    hrefs = {a.attrs.get('href', '').split('#')[0] for a in find(doc, tag='a')}
    missing = [rel for rel, _ in chapters if rel not in hrefs]
    if missing:
        issues.append(('FAIL', '目录缺少 %d 个章节链接：%s'
                       % (len(missing), '、'.join(missing))))

    if '不构成医疗建议' not in raw:
        issues.append(('FAIL', '页脚缺少医疗声明'))

    anchors = {a.attrs.get('href', '')[1:] for a in find(doc, tag='a')
               if a.attrs.get('href', '').startswith('#')}
    ids = {n.attrs.get('id') for n in walk(doc) if n.attrs.get('id')}
    broken = sorted(a for a in anchors if a and a not in ids)
    if broken:
        issues.append(('FAIL', '页内锚点无对应元素：' + '、'.join(broken)))
    if not anchors:
        issues.append(('WARN', '四幕地图没有可键盘访问的锚点链接'))

    check_links(path, doc, root, issues, strict)


def scan_absolutes(rel, raw):
    hits = []
    for i, line in enumerate(raw.splitlines(), 1):
        if line.lstrip().startswith(('/*', '#', '.', '@')):
            continue
        for term in ABSOLUTE_TERMS:
            if term in line:
                snippet = re.sub(r'<[^>]+>', '', line).strip()
                hits.append((i, term, snippet[:60]))
                break
    return hits


# ============================================================
# 主流程
# ============================================================

def main():
    ap = argparse.ArgumentParser(description='《人体手册》全站校验')
    ap.add_argument('--root', default=None, help='内容根目录（默认：项目根）')
    ap.add_argument('--strict', action='store_true', help='缺文件 / 死链升级为 FAIL')
    ap.add_argument('--no-report', action='store_true', help='不打印绝对化表述清单')
    args = ap.parse_args()

    proj = Path(__file__).resolve().parent.parent
    root = Path(args.root).resolve() if args.root else proj
    spec_path = root / 'BUILD_SPEC.md'
    if not spec_path.exists():
        spec_path = proj / 'BUILD_SPEC.md'
    entries = load_filemap(spec_path)
    chapters = [(p, d) for p, d in entries if p.startswith('chapters/')]

    rep = Report()
    exit_fail = False
    exit_warn = False

    # ---- 1. 文件地图 ----
    issues = rep.add('文件地图（BUILD_SPEC 第 1 节）')
    missing = [p for p, _ in entries if not (root / p).exists()]
    if missing:
        issues.append(('FAIL' if args.strict else 'WARN',
                       '%d/%d 个文件尚不存在：%s'
                       % (len(missing), len(entries), '、'.join(missing))))
    else:
        issues.append(('PASS', '%d 个文件齐全' % len(entries)))

    # 共享 CSS
    css_path = root / 'assets/style.css'
    css_has_rm = False
    shared = {'classes': set(), 'css': ''}
    if css_path.exists():
        css_raw = css_path.read_text(encoding='utf-8')
        css_has_rm = 'prefers-reduced-motion' in css_raw
        shared = {'classes': css_selector_classes(css_raw), 'css': css_raw}
        cissues = rep.add('assets/style.css')
        css_code = re.sub(r'/\*.*?\*/', '', css_raw, flags=re.S)   # 注释不参与匹配
        check_no_external(Node('#document', [], 0), [css_code], cissues)
        for cls in ('.crumbs', '.footnav', '.footnav .none'):
            if cls not in css_code:
                cissues.append(('FAIL', '缺少 %s 规则（BUILD_SPEC 第 5 节）' % cls))
        check_css_svg_colors([css_code], cissues, 'style.css')
        if not css_has_rm:
            cissues.append(('WARN', '共享样式未见 prefers-reduced-motion，各章须自行声明'))
        else:
            cissues.append(('PASS', 'prefers-reduced-motion 已在共享表声明'))
        if '#circuit' in css_code or '#timeline' in css_code:
            cissues.append(('WARN', '章内特有样式（#circuit / #timeline）不应进共享表'))
        else:
            cissues.append(('PASS', '.crumbs / .footnav / .footnav .none 齐备，无章内特有样式与外部资源'))

    # ---- index ----
    idx_path = root / 'index.html'
    if idx_path.exists():
        raw = idx_path.read_text(encoding='utf-8')
        doc, perr = parse(raw)
        issues = rep.add('index.html')
        if perr:
            issues.append(('FAIL', '标签闭合异常：' + '；'.join(perr[:5])))
        check_index(idx_path, doc, raw, chapters, issues, css_has_rm, args.strict,
                    root, shared)
        rep.notes.append(('index.html', scan_absolutes('index.html', raw)))

    # ---- 各章 ----
    for i, (rel, title) in enumerate(chapters):
        path = root / rel
        if not path.exists():
            continue
        prev_rel = chapters[i - 1][0] if i > 0 else None
        next_rel = chapters[i + 1][0] if i < len(chapters) - 1 else None
        raw = path.read_text(encoding='utf-8')
        doc, perr = parse(raw)
        issues = rep.add(rel)
        if perr:
            issues.append(('FAIL', '标签闭合异常：' + '；'.join(perr[:5])))
        check_chapter(path, rel, doc, raw, title, prev_rel, next_rel,
                      issues, css_has_rm, args.strict, root, shared)
        rep.notes.append((rel, scan_absolutes(rel, raw)))

    # ---- 输出 ----
    print('《人体手册》全站校验 · root = %s%s' % (root, ' · strict' if args.strict else ''))
    print('=' * 64)
    tally = {'PASS': 0, 'WARN': 0, 'FAIL': 0}
    for name, issues in rep.files:
        verdict = 'PASS'
        for lvl, _ in issues:
            if LEVELS[lvl] > LEVELS[verdict]:
                verdict = lvl
        tally[verdict] += 1
        if verdict == 'FAIL':
            exit_fail = True
        if verdict == 'WARN':
            exit_warn = True
        print('\n[%s] %s' % (verdict, name))
        for lvl, msg in issues:
            if lvl != 'PASS' or verdict == 'PASS':
                print('       · %s' % msg)

    if not args.no_report:
        print('\n' + '=' * 64)
        print('REPORT · 绝对化表述（最/唯一/所有/永远/从不/第一个）—— 需逐条确认有据，不计入成败')
        total = 0
        for name, hits in rep.notes:
            if not hits:
                continue
            total += len(hits)
            print('\n  %s（%d 处）' % (name, len(hits)))
            for line, term, snippet in hits:
                print('    第 %-4d 行 「%s」 %s' % (line, term, snippet))
        if total == 0:
            print('  （无）')

    print('\n' + '=' * 64)
    print('汇总：PASS %d · WARN %d · FAIL %d' % (tally['PASS'], tally['WARN'], tally['FAIL']))
    if exit_fail or (args.strict and exit_warn):
        print('结果：不通过')
        return 1
    print('结果：通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
