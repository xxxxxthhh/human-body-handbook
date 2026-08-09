# archive/audit — 构建期审计工具存档

**定位**：审计／流程工具存档，非发布产物、非门禁。发布门禁只有 `tools/check.py`。
**维护**：pilot。**调用**：可在任意目录调用，脚本自行 chdir 到仓库根。

| 脚本 | 作用 | 用法 |
|---|---|---|
| `quotes.py` | 跨章**逐字**耦合探测（≥18 字，剔除模板样板串）。零漏报：片段一旦不再逐字相同，耦合对当场从清单消失 | `python3 archive/audit/quotes.py` |
| `nearquotes.py` | 跨章**近似句**探测（句级，阈值 0.70，经标定；已显式 `autojunk=False`） | 同上 |
| `xref.py` | **前向承诺**登记表（第三类"指涉"耦合）。含序章/终章写法 | `xref.py [--all]` |
| `audit7.py` | 口吻三角测量：第二人称密度／历史锚点／register 词表／孕周口径 | `audit7.py tri` |
| `audit13.py` | 正文外字符串分槽位清单 + register + 标题层绝对化词 | `audit13.py chapters/*.html [--dump]` |
| `selfcheck.py` | 单章栏目/计数/SVG 几何自查 | `selfcheck.py chapters/chNN-*.html` |

`snapshots/` 为基线与定稿快照，供"改动前后对照"用：diff 干净＝没断。

## 三类耦合（可检性各不相同）
1. **逐字** — `quotes.py`，零漏报。
2. **近似** — `nearquotes.py`，有**子句级盲区**（嵌在不同句中的相同子句看不见），靠作者报备兜底。
3. **指涉** — `xref.py`，两章互指却无共同措辞；断裂时措辞完全不变，只剩空头承诺。

阈值经标定：近似句 0.70 得 22 对（几乎条条有意义），降到 0.62 得 40 对（多为套语碎片）。**不建议下调**——清册一旦稀释成长表就没人看了。

详细维护经验见 `REGISTRY_NOTES.md`。
