#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正文汉字计数 —— 供作者自报体量与审计波抽查使用。

    python3 tools/wordcount.py chapters/*.html

**不是 check.py 的一部分**：BUILD_SPEC §7b.12 明确「脚本与审计不核对时长与
字数的换算，只核对存在性」。本工具只报事实（字数 + 按公式折算的建议时长），
不与 .meta 已写的时长做比对、不判定通过与否。

## 计数口径（原作者 writer-05-07，**已冻结，勿轻改**）

剥离 `<script>` / `<style>` / `<svg>`（图内标注不算正文），排除 `#spec` 与
`#quiz` 两节，统计 CJK 统一汉字 `[一-鿿]`。计入的有：章头标题与副题、面包屑、
引子、正文各节、figcaption、页脚预告——合计约 150–250 字的固定开销。

口径为何冻结：BUILD_SPEC §3 的体量带（正文 4800–7200 字，终章 2500–3500）
是**按这个口径标定的**。改口径（比如改成排除页脚预告）会让每一章的达标结论
整体平移，等于悄悄改了契约。要改必须连同体量带一起重标，并报 lead。

## 时长折算

按 §7b.12（2026-08 修订）：`.meta` 时长 = min(round(字数 ÷ 350), 18)，终章 ≈8。

两个易错点：
1. 封顶 18 分钟——解决「6300 字以上无法同时满足字数区间与 14–18 分钟」的矛盾。
2. 这里的 round 是**四舍五入**，不是 Python 内置的 `round()`。内置 round 走
   银行家舍入：`round(16.5)` 返回 16 而非 17，恰好会在 5775 / 6125 字这类
   整半点上少报一分钟。故实现写作 `int(n / RATE + 0.5)`。
"""

import re
import sys
from pathlib import Path

RATE = 350          # 字/分钟
CAP = 18            # 分钟上限（§7b.12）
BAND = (4800, 7200)         # 普通章体量带
BAND_FINALE = (2500, 3500)  # 终章


def count(path):
    raw = Path(path).read_text(encoding='utf-8')
    for pat in (r'<script\b.*?</script>', r'<style\b.*?</style>', r'<svg\b.*?</svg>'):
        raw = re.sub(pat, '', raw, flags=re.S | re.I)
    raw = re.sub(r'<section id="spec".*?</section>', '', raw, flags=re.S)
    raw = re.sub(r'<section id="quiz".*?</section>', '', raw, flags=re.S)
    return len(re.findall(r'[一-鿿]', re.sub(r'<[^>]+>', '', raw)))


def main(paths):
    if not paths:
        print(__doc__.split('##')[0].strip())
        return 0
    print('%-30s %7s %9s   %s' % ('章', '字数', '建议时长', '体量带'))
    print('-' * 62)
    for p in paths:
        name = Path(p).name
        n = count(p)
        finale = 'ch26' in name
        lo, hi = BAND_FINALE if finale else BAND
        mins = 8 if finale else min(int(n / RATE + 0.5), CAP)   # 四舍五入，非银行家舍入
        band = '✓' if lo <= n <= hi else ('偏短 %d 字' % (lo - n) if n < lo
                                          else '超出 %d 字' % (n - hi))
        print('%-30s %7d %7d 分   %s' % (name, n, mins, band))
    print('\n口径见本文件 docstring；时长只作建议，check.py 不核对换算（BUILD_SPEC §7b.12）。')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
