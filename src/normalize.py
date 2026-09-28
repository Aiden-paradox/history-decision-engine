"""文本归一化：古籍电子书检索前的三步清洗。

三步缺一不可。每一步都对应一类实测过的**静默漏检** —— 检索失败不会报错，
只会让你以为"库里没有"，然后基于缺失信息得出结论。

1. 去空白：部分电子书排版逐字带空格
2. 去注号：注释序号常插在词与词之间，例如正文实际作"不善[23]代之"
3. 去标点：标点差异会让字面匹配失败，例如"狡兔死，走狗烹"
"""

from __future__ import annotations

import re

# 中英文常见标点（含全角空格与各类引号）
_PUNCT = (
    "，。、；：！？"
    "\u201c\u201d\u2018\u2019"  # 弯引号
    "\u300a\u300b\u3008\u3009\u300c\u300d\u300e\u300f\u3010\u3011"
    "\u2014\u2013\u2026\u00b7\uff0d"
    "\u3000"
    '"\',.;:!?()[]{}<>-_/\\'
)

_RE_NOTE = re.compile(r"\[\d+\]")
_RE_WS = re.compile(r"\s+")
_RE_PUNCT = re.compile("[" + re.escape(_PUNCT) + "]")


def normalize(text: str) -> str:
    """把文本压成可比较的形式：去空白、去注号、去标点。"""
    text = _RE_NOTE.sub("", text)
    text = _RE_WS.sub("", text)
    return _RE_PUNCT.sub("", text)


def normalize_keyword(keyword: str) -> str:
    """检索词走同一套归一化，保证与语料可比。"""
    return normalize(keyword)


def build_map(raw: str) -> tuple[str, list[int]]:
    """构建"归一化文本 → 原文下标"的映射。

    返回 (flat_text, index_map)，其中 index_map[i] 是 flat_text[i] 在 raw 中的位置。

    用途：检索在归一化文本上进行（消除空白、注号、标点带来的假阴性），
    但展示给用户的必须是**原文**。按字符比例估算位置会导致上下文窗口漂移，
    精确映射可以彻底避免这个问题。
    """
    flat_chars: list[str] = []
    index_map: list[int] = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] == "[":
            m = _RE_NOTE.match(raw, i)
            if m:
                i = m.end()
                continue
        ch = raw[i]
        if not _RE_WS.match(ch) and not _RE_PUNCT.match(ch):
            flat_chars.append(ch)
            index_map.append(i)
        i += 1
    return "".join(flat_chars), index_map
