#!/usr/bin/env python3
"""在本地语料中检索关键词，返回命中位置与上下文。

用法：
    python src/retrieve.py --corpus data/sample --keywords 乐毅,燕惠王,骑劫
    python src/retrieve.py --corpus data/full --keywords "交绝不出恶声" --window 300

设计要点：
  - 语料只读，不写入、不上传
  - 检索前统一做三步归一化（见 normalize.py）
  - 命中的上下文按原始文本返回，保留标点，便于核对出处
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import build_map, normalize, normalize_keyword  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def iter_corpus(path: Path, suffixes=(".txt", ".md")):
    if path.is_file():
        yield path
        return
    for p in sorted(path.rglob("*")):
        if p.is_file() and p.suffix.lower() in suffixes:
            yield p


def build_index(path: Path, suffixes):
    """返回 [(文件名, 归一化全文, 原文全文, 位置映射)]。"""
    index = []
    for p in iter_corpus(path, suffixes):
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"  [跳过] {p.name}: {exc}", file=sys.stderr)
            continue
        flat, index_map = build_map(raw)
        index.append((p.name, flat, raw, index_map))
    return index


def context_window(raw: str, flat: str, index_map: list[int], key: str, window: int, back: int) -> str | None:
    """用精确映射把命中位置还原到原文，再截取上下文。"""
    pos_flat = flat.find(normalize_keyword(key))
    if pos_flat < 0:
        return None
    raw_pos = index_map[pos_flat]
    start = max(0, raw_pos - back)
    end = min(len(raw), raw_pos + window)
    return " ".join(raw[start:end].split())


def main() -> int:
    ap = argparse.ArgumentParser(description="古籍语料关键词检索")
    ap.add_argument("--corpus", required=True, help="语料目录或单个文件")
    ap.add_argument("--keywords", required=True, help="逗号分隔的检索词")
    ap.add_argument("--window", type=int, default=400, help="命中后展示的字符数")
    ap.add_argument("--back", type=int, default=150, help="命中前回看的字符数")
    ap.add_argument("--suffixes", default=".txt", help="参与检索的扩展名")
    args = ap.parse_args()

    corpus = Path(args.corpus)
    if not corpus.exists():
        print(f"语料路径不存在：{corpus}", file=sys.stderr)
        return 2

    suffixes = tuple(s.strip() for s in args.suffixes.split(",") if s.strip())
    index = build_index(corpus, suffixes)
    if not index:
        print("未找到可检索的文本文件", file=sys.stderr)
        return 2
    total_chars = sum(len(flat) for _, flat, _, _ in index)
    print(f"语料 {len(index)} 个文件，归一化后 {total_chars:,} 字\n")

    hits = 0
    for keyword in [k.strip() for k in args.keywords.split(",") if k.strip()]:
        key = normalize_keyword(keyword)
        matched = [item for item in index if key in item[1]]
        hits += len(matched)
        print(f"『{keyword}』 → 命中 {len(matched)} 个文件")
        for name, flat, raw, index_map in matched[:3]:
            snippet = context_window(raw, flat, index_map, keyword, args.window, args.back)
            print(f"  [{name}]")
            print(f"    {snippet}")
        if len(matched) > 3:
            print(f"    …… 另有 {len(matched) - 3} 个文件命中")
        print()

    print(f"合计命中 {hits} 处" + ("" if hits else "（检查别名表与检索词拼写）"))
    return 0 if hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
