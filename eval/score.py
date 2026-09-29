#!/usr/bin/env python3
"""引用可核性打分器。

把一份分析报告里的每条引文拿出来，回本地语料库逐条核对，统计：

  1. 引文可核性  —— 能否在语料中定位到（编造引文是这类系统的头号失败模式）
  2. 来源标记覆盖率 —— 引文是否标注了来源类型（原文／史家评／今人解读）
  3. 结构完整度  —— 是否覆盖规定的输出字段

为什么只做这三项：它们**不依赖主观判断**。裁判与选手同源时，任何主观打分都不可信，
所以这里只保留可机械验证的指标。人判指标见 eval/rubric.md。

用法：
    python eval/score.py --analysis eval/results/arm-c-full.md --corpus data/sample
    python eval/score.py --analysis x.md --corpus <语料目录> --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from normalize import normalize  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------- 引文抽取 ----------

_RE_BLOCK = re.compile(r"^>\s?(.*)$", re.M)
_RE_CORNER = re.compile(r"「([^」]{6,})」")
_RE_CURLY = re.compile(r"“([^”]{6,})”")
# 行内代码：禁止跨行匹配，否则两个不相邻的反引号会把整段正文吞进来
_RE_CODE = re.compile(r"`([^`\n]{10,})`")

# 引文长度上限：超过这个长度基本是作者自述，不是引文
MAX_QUOTE_CHARS = 400


def extract_quotes(text: str, min_len: int = 10, max_len: int = MAX_QUOTE_CHARS) -> list[str]:
    """从分析文本中抽出所有引文候选。"""
    quotes: list[str] = []

    # 引用块：连续的 > 行合并成一段
    buffer: list[str] = []
    for line in text.splitlines():
        m = _RE_BLOCK.match(line)
        if m:
            buffer.append(m.group(1))
        else:
            if buffer:
                quotes.append(" ".join(buffer))
                buffer = []
    if buffer:
        quotes.append(" ".join(buffer))

    for pattern in (_RE_CORNER, _RE_CURLY, _RE_CODE):
        quotes.extend(pattern.findall(text))

    seen: set[str] = set()
    result: list[str] = []
    for q in quotes:
        q = q.strip()
        flat = normalize(q)
        if len(flat) < min_len or len(flat) > max_len or flat in seen:
            continue
        seen.add(flat)
        result.append(q)
    return result


# ---------- 可核性 ----------


# 省略号：节引的标志。引文被省略号切成多段时，应逐段核对后加权平均，
# 而不是把整条当成连续文本 —— 否则正当的节引会被误判为编造。
_RE_ELLIPSIS = re.compile(r"…{2,}|\.{3,}|。{2,}")


def _segment_coverage(flat: str, corpus_flat: str, seg: int = 20, step: int = 10) -> float:
    if not flat:
        return 0.0
    if len(flat) < seg:
        return 1.0 if flat in corpus_flat else 0.0
    segs = [flat[i : i + seg] for i in range(0, len(flat) - seg + 1, step)]
    if not segs:
        return 0.0
    hit = sum(1 for s in segs if s in corpus_flat)
    return hit / len(segs)


def coverage(quote: str, corpus_flat: str, seg: int = 20, step: int = 10) -> float:
    """引文与语料的重合度。支持节引（省略号分段），抗注释插入与标点差异。"""
    parts = [p for p in _RE_ELLIPSIS.split(quote) if normalize(p)]
    if not parts:
        return 0.0
    total = sum(len(normalize(p)) for p in parts)
    if total == 0:
        return 0.0
    weighted = sum(_segment_coverage(normalize(p), corpus_flat, seg, step) * len(normalize(p)) for p in parts)
    return weighted / total


def classify(score: float) -> str:
    if score >= 0.8:
        return "可核"
    if score >= 0.5:
        return "部分可核"
    return "不可核"


# ---------- 来源标记 ----------

MARKERS = ("原文", "史家评", "今人解读", "案例叙述", "史家", "出自", "见《", "引自", "《史记》", "《资治通鉴》")


def marked(text: str, quote: str, window: int = 120) -> bool:
    idx = text.find(quote[:20])
    if idx < 0:
        idx = text.find(quote[:10])
    if idx < 0:
        return False
    near = text[max(0, idx - window) : idx + len(quote) + window]
    return any(m in near for m in MARKERS)


# ---------- 结构完整度 ----------

STRUCTURE = {
    "情景内核": ("内核", "处境", "结构特征"),
    "案例": ("案例", "主卡", "对照", "警示"),
    "判断依据": ("判断", "依据", "为什么这么选"),
    "结果": ("结果", "结局", "后来"),
    "代价": ("代价", "成本"),
    "相反评价": ("另一个声音", "相反", "分歧", "另一方面", "并列"),
    "规律": ("规律", "启发"),
    "风险提醒": ("风险", "提醒", "不能推概率", "局限"),
    "行动方案": ("行动", "能做", "建议", "第 1 步", "第一步", "第 2 步"),
}


def structure_coverage(text: str) -> dict[str, bool]:
    return {name: any(k in text for k in keys) for name, keys in STRUCTURE.items()}


# ---------- 主流程 ----------


def load_corpus(paths: list[str]) -> str:
    chunks = []
    for p in paths:
        root = Path(p)
        files = [root] if root.is_file() else [f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in (".txt", ".md")]
        for f in files:
            chunks.append(normalize(f.read_text(encoding="utf-8", errors="replace")))
    return "\n".join(chunks)


def main() -> int:
    ap = argparse.ArgumentParser(description="引文可核性打分")
    ap.add_argument("--analysis", required=True, help="待评分的分析文本")
    ap.add_argument("--corpus", required=True, action="append", help="语料目录（可重复指定）")
    ap.add_argument("--json", dest="json_out", help="把结果写入 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总，不逐条列出")
    args = ap.parse_args()

    analysis = Path(args.analysis).read_text(encoding="utf-8", errors="replace")
    corpus_flat = load_corpus(args.corpus)
    if not corpus_flat:
        print("语料为空，无法核对", file=sys.stderr)
        return 2

    quotes = extract_quotes(analysis)
    rows = []
    for q in quotes:
        cov = coverage(q, corpus_flat)
        rows.append(
            {
                "quote": q[:60] + ("…" if len(q) > 60 else ""),
                "coverage": round(cov, 3),
                "verdict": classify(cov),
                "marked": marked(analysis, q),
            }
        )

    total = len(rows)
    ok = sum(1 for r in rows if r["verdict"] == "可核")
    partial = sum(1 for r in rows if r["verdict"] == "部分可核")
    bad = total - ok - partial
    marked_n = sum(1 for r in rows if r["marked"])
    struct = structure_coverage(analysis)
    struct_n = sum(1 for v in struct.values() if v)

    print(f"分析文本：{Path(args.analysis).name}")
    print(f"语料：{', '.join(args.corpus)}（{len(corpus_flat):,} 字）\n")
    print("== 引文核对 ==")
    print(f"  引文总数 {total}")
    if total:
        print(f"  可核     {ok}  ({ok / total:.1%})")
        print(f"  部分可核 {partial}")
        print(f"  不可核   {bad}")
    if not args.quiet and bad:
        print("\n  不可核引文（需人工复核，可能是编造或语料中确无此句）：")
        for r in rows:
            if r["verdict"] == "不可核":
                print(f"    ✗ [{r['coverage']:.0%}] {r['quote']}")

    print("\n== 来源标记 ==")
    print(f"  带标记 {marked_n}/{total}" + (f"  ({marked_n / total:.1%})" if total else ""))

    print("\n== 结构完整度 ==")
    print(f"  覆盖 {struct_n}/{len(STRUCTURE)}")
    for name, hit in struct.items():
        print(f"    {'✓' if hit else '✗'} {name}")

    if args.json_out:
        payload = {
            "analysis": str(args.analysis),
            "corpus": args.corpus,
            "corpus_chars": len(corpus_flat),
            "quotes_total": total,
            "quotes_ok": ok,
            "quotes_partial": partial,
            "quotes_unverifiable": bad,
            "verifiable_rate": round(ok / total, 3) if total else None,
            "source_marked": marked_n,
            "source_marked_rate": round(marked_n / total, 3) if total else None,
            "structure_covered": struct_n,
            "structure_total": len(STRUCTURE),
            "details": rows,
        }
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON 已写入 {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
