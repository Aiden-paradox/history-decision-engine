#!/usr/bin/env python3
"""查看评分 JSON 的明细：逐条列出非完全可核的引文与缺失的结构项。"""

import importlib.util
import json
import pathlib
import sys

sys.path.insert(0, "src")

for name in ("arm-c-full", "arm-c-media"):
    p = pathlib.Path(f"eval/results/{name}.json")
    if not p.exists():
        continue
    d = json.loads(p.read_text(encoding="utf-8"))
    print(f"--- {name} ---")
    print(f"  可核率 {d['verifiable_rate']:.1%}｜来源标记率 {d['source_marked_rate']:.1%}｜结构 {d['structure_covered']}/{d['structure_total']}")
    for r in d["details"]:
        if r["verdict"] != "可核":
            print(f"  非完全可核 [{r['coverage']:.0%}] {r['quote'][:70]}")

spec = importlib.util.spec_from_file_location("score", "eval/score.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

text = pathlib.Path("eval/results/arm-c-media.md").read_text(encoding="utf-8")
missing = [k for k, v in mod.structure_coverage(text).items() if not v]
print(f"\n发布版缺失的结构项：{missing or '无'}")
