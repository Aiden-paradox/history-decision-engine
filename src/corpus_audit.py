#!/usr/bin/env python3
"""语料体检：入库前判断一份材料能不能用。

对 PDF：判页数与文字层是否存在（扫描件提不出文字，需 OCR 或另寻版本）
对文本：查页眉残留、重复片段、繁简比例

用法：
    python src/corpus_audit.py --path data/sample
    python src/corpus_audit.py --path data/full --suffixes .txt,.pdf,.epub
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize import normalize  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TRAD = "後國說爲學經無與這來時會對開關們個"
SIMP = "后国说为学经无与这来时会对开关们个"


def audit_text(path: Path, sample_points: int = 10) -> dict:
    raw = path.read_text(encoding="utf-8", errors="replace")
    flat = normalize(raw)
    step = max(1, len(flat) // sample_points)
    dup = 0
    for i in range(1, sample_points):
        frag = flat[i * step : i * step + 50]
        if len(frag) >= 35 and flat.count(frag) > 1:
            dup += 1
    return {
        "chars": len(raw),
        "dup": f"{dup}/{sample_points - 1}",
        "header": raw.count("页 共") + raw.count("页共"),
        "trad": sum(raw.count(c) for c in TRAD),
        "simp": sum(raw.count(c) for c in SIMP),
    }


def audit_pdf(path: Path) -> dict:
    try:
        from pypdf import PdfReader
    except ImportError:
        return {"error": "需要 pypdf：pip install pypdf"}
    try:
        reader = PdfReader(str(path), strict=False)
        pages = len(reader.pages)
        chars = 0
        for i in range(min(3, pages)):
            chars += len(reader.pages[i].extract_text() or "")
        return {"pages": pages, "head_chars": chars}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="语料体检")
    ap.add_argument("--path", required=True)
    ap.add_argument("--suffixes", default=".txt,.pdf")
    args = ap.parse_args()

    suffixes = tuple(s.strip().lower() for s in args.suffixes.split(",") if s.strip())
    files = [p for p in sorted(Path(args.path).rglob("*")) if p.is_file() and p.suffix.lower() in suffixes]
    if not files:
        print("未找到待检文件")
        return 0

    for p in files:
        print(f"\n{'=' * 60}\n{p.name}  ({p.stat().st_size / 1024:.0f} KB)")
        if p.suffix.lower() == ".pdf":
            info = audit_pdf(p)
            if "error" in info:
                print(f"  读取失败：{info['error']}")
            else:
                verdict = "有文字层" if info["head_chars"] > 0 else "无文字层（扫描件，需 OCR）"
                print(f"  页数 {info['pages']}｜前 3 页可提取字符 {info['head_chars']}｜{verdict}")
        else:
            info = audit_text(p)
            print(f"  字符 {info['chars']:,}｜重复片段 {info['dup']}｜页眉残留 {info['header']}")
            ratio = "繁体" if info["trad"] > info["simp"] * 2 else ("简体" if info["simp"] > info["trad"] * 2 else "混合")
            print(f"  繁简倾向：{ratio}（繁 {info['trad']:,} / 简 {info['simp']:,}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
