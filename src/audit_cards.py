#!/usr/bin/env python3
"""案例卡漏检检查（质量控制闸门）。

每张案例卡带一个 `**检索词**` 字段。入库前用这些词回跑全库检索，
全部命中才算通过。任一关键词未命中即返回非零退出码，可直接用于 CI。

用法：
    python src/audit_cards.py --cards cases/cards --corpus data/sample

为什么需要这个闸门：检索失败是静默的。没有这道检查，一张卡可能
长期无法被搜到，而使用者只会以为"库里没有这个案例"。
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize, normalize_keyword  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_RE_KEYS = re.compile(r"\*\*检索词\*\*\s*(.+)")


def load_keywords(card: Path) -> list[str]:
    text = card.read_text(encoding="utf-8", errors="replace")
    m = _RE_KEYS.search(text)
    if not m:
        return []
    raw = m.group(1).strip()
    return [k.strip() for k in re.split(r"[、,，]", raw) if k.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description="案例卡漏检检查")
    ap.add_argument("--cards", required=True, help="案例卡目录")
    ap.add_argument("--corpus", required=True, help="语料目录")
    ap.add_argument("--suffixes", default=".txt")
    ap.add_argument("--only", help="只检查匹配该通配符的卡片，例如 case-001*")
    args = ap.parse_args()

    suffixes = tuple(s.strip() for s in args.suffixes.split(",") if s.strip())
    corpus_texts = []
    for p in sorted(Path(args.corpus).rglob("*")):
        if p.is_file() and p.suffix.lower() in suffixes:
            corpus_texts.append(normalize(p.read_text(encoding="utf-8", errors="replace")))

    if not corpus_texts:
        print("语料为空，无法检查", file=sys.stderr)
        return 2

    pattern = args.only or "*.md"
    cards = sorted(Path(args.cards).glob(pattern))
    if not cards:
        print("未找到案例卡", file=sys.stderr)
        return 2

    total = passed = 0
    failures = []
    print(f"检查 {len(cards)} 张卡，语料 {len(corpus_texts)} 个文件\n")
    for card in cards:
        keys = load_keywords(card)
        if not keys:
            print(f"  {card.stem}: 未找到检索词字段")
            failures.append((card.name, ["<缺少检索词字段>"]))
            continue
        miss = [k for k in keys if not any(normalize_keyword(k) in t for t in corpus_texts)]
        total += len(keys)
        passed += len(keys) - len(miss)
        status = "OK" if not miss else f"漏检 {miss}"
        print(f"  {card.stem:28s} {len(keys):2d} 词  {status}")
        if miss:
            failures.append((card.name, miss))

    print(f"\n合计 {passed}/{total} 命中")
    if failures:
        print("\n未通过：")
        for name, miss in failures:
            print(f"  {name}: {miss}")
        print("\n排查顺序：① 检索词是否取自原文连续片段 ② 是否需要补别名 ③ 归一化是否覆盖该标点")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
