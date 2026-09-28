#!/usr/bin/env python3
"""用 Calibre 的 ebook-convert 批量把电子书转成纯文本。

优先使用 epub（保留原文/译文/注释的样式类，便于程序化分离），
其次是 azw3、mobi；PDF 仅在必要时转，且需先确认有文字层。

用法：
    python src/extract_text.py --input "D:/电子书" --output data/full
    python src/extract_text.py --input "D:/电子书" --output data/full --calibre "D:/Apps/Calibre Portable/Calibre/ebook-convert.exe"
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SUFFIXES = (".epub", ".azw3", ".mobi", ".pdf")
CANDIDATES = [
    r"C:\Program Files\Calibre2\ebook-convert.exe",
    r"C:\Program Files (x86)\Calibre2\ebook-convert.exe",
    r"C:\Program Files\Calibre\ebook-convert.exe",
]


def find_calibre(explicit: str | None) -> str | None:
    if explicit:
        return explicit if Path(explicit).exists() else None
    found = shutil.which("ebook-convert")
    if found:
        return found
    for c in CANDIDATES:
        if Path(c).exists():
            return c
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="电子书批量转纯文本")
    ap.add_argument("--input", required=True, help="电子书所在目录")
    ap.add_argument("--output", required=True, help="输出目录")
    ap.add_argument("--calibre", help="ebook-convert 路径（默认自动查找）")
    args = ap.parse_args()

    engine = find_calibre(args.calibre)
    if not engine:
        print("未找到 ebook-convert。请安装 Calibre 或用 --calibre 指定路径。", file=sys.stderr)
        return 2

    src = Path(args.input)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)

    books = [p for p in sorted(src.rglob("*")) if p.is_file() and p.suffix.lower() in SUFFIXES]
    if not books:
        print(f"{src} 下没有找到支持的电子书格式")
        return 0

    for book in books:
        stem = book.relative_to(src).as_posix().replace("/", "__")
        dest = out / f"{Path(stem).stem}.txt"
        if dest.exists():
            print(f"  跳过（已存在）：{dest.name}")
            continue
        print(f"  转换：{book.name} → {dest.name}")
        result = subprocess.run(
            [engine, str(book), str(dest)],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if result.returncode != 0:
            print(f"    失败：{result.stderr.strip()[:200]}", file=sys.stderr)
            continue
        size = dest.stat().st_size
        chars = len(dest.read_text(encoding="utf-8", errors="replace"))
        print(f"    {chars:,} 字符 / {size / 1024:.0f} KB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
