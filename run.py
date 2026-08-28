#!/usr/bin/env python3
"""
孙本位 / sun-standard —— CLI（纯 stdlib，不联网，不调 LLM）

  python3 run.py convert 4800                  # 一笔钱 → 孙本位单位
  python3 run.py convert 50000000 -c USD
  python3 run.py score draft.txt               # 账本密度跑分（也吃 stdin）
  python3 run.py card ledger.json              # 结账单：文本卡 + SVG
  python3 run.py rates                         # 看汇率表

任何子命令加 --json 出机器可读，喂给 agent。
写作不在这里：抽科目 / 挑对照 / 写正文由 agent 做，见 SKILL.md。
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sun_standard as S  # noqa: E402


def cmd_convert(a):
    R = S.load_rates(a.rates)
    res = S.convert(a.amount, a.currency, R, limit=a.limit)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    inp = res["input"]
    print()
    print(S.cn_money(inp["amount"], inp["currency"]) + "。")
    print()
    if not res["units"]:
        print("这个数量级换算出来没有意思。换个金额。")
        print()
        return
    for u in res["units"]:
        unit = S.cn_money(u["unit_value"], u["unit_currency"])
        cw, name = u.get("cw", ""), u["name"]
        print(f"{S.cn_qty(u['ratio_display'])}{cw}{name}。"
              f"一{cw}{name}{unit}，{u['note']}。")
    print()


def cmd_score(a):
    if a.file and a.file != "-":
        text = Path(a.file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    rep = S.score(text)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return
    print()
    print(S.format_score(rep))
    print()


def cmd_card(a):
    ledger = json.loads(Path(a.ledger).read_text(encoding="utf-8"))
    txt = S.render_text_card(ledger, width=a.width)
    svg = S.render_svg_card(ledger, px=a.px)

    out_dir = HERE / "output"
    out_dir.mkdir(exist_ok=True)
    stem = a.name or Path(a.ledger).stem
    tp, sp = out_dir / f"{stem}.txt", out_dir / f"{stem}.svg"
    tp.write_text(txt + "\n", encoding="utf-8")
    sp.write_text(svg, encoding="utf-8")

    if a.json:
        print(json.dumps({"text": txt, "text_path": str(tp), "svg_path": str(sp)},
                         ensure_ascii=False, indent=2))
        return
    print()
    print(txt)
    print()
    print(f"→ {tp}")
    print(f"→ {sp}")
    print()


def cmd_compare(a):
    cmp = json.loads(Path(a.compare).read_text(encoding="utf-8"))
    svg = S.render_compare_svg(cmp, px=a.px)
    out_dir = HERE / "output"
    out_dir.mkdir(exist_ok=True)
    stem = a.name or Path(a.compare).stem
    sp = out_dir / f"{stem}.svg"
    sp.write_text(svg, encoding="utf-8")

    if a.json:
        print(json.dumps({"svg_path": str(sp)}, ensure_ascii=False))
        return
    print()
    if cmp.get("title"):
        print(cmp["title"])
    for side in ("left", "right"):
        blk = cmp.get(side) or {}
        print()
        if blk.get("label"):
            print(f"[{blk['label']}]")
        for ln in blk.get("lines") or []:
            print(ln)
        if blk.get("verdict"):
            print()
            print(blk["verdict"])
    print()
    print(f"→ {sp}")
    print()


def cmd_rates(a):
    R = S.load_rates(a.rates)
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2))
        return
    print(f"\n{R['meta']['name']}  v{R['meta']['version']}")
    print(f"美元兑人民币{S.cn_num(R['meta']['usd_cny'])}。{R['meta']['usd_cny_note']}")

    labels = {"money": "钱", "weight": "重量", "headcount": "人头",
              "duration": "时长", "count": "计数", "loss": "损耗"}
    for key, label in labels.items():
        rows = R.get(key, [])
        if not rows:
            continue
        print(f"\n{label}。\n")
        for u in rows:
            if key == "money":
                v = S.cn_money(u["value"], u["currency"])
                head = "一" + u.get("cw", "") + u["name"]
            elif "value" in u:
                v = u.get("display") or (S.cn_qty(u["value"]) + u.get("unit", ""))
                head = u["name"]
            else:
                v, head = "", u["name"]
            note = u.get("note", "").rstrip("。")
            print(head + ("，" + v if v else "") + "。" + (note + "。" if note else ""))
    print()


def main():
    ap = argparse.ArgumentParser(prog="sun-standard", description="孙本位")
    ap.add_argument("--rates", default=None, help="自定义 rates.json 路径")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convert", help="金额 → 孙本位单位")
    c.add_argument("amount", type=float)
    c.add_argument("-c", "--currency", default="CNY", help="CNY(默认) / USD")
    c.add_argument("--limit", type=int, default=6)
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_convert)

    s = sub.add_parser("score", help="账本密度跑分")
    s.add_argument("file", nargs="?", default="-", help="文本文件，或 - 读 stdin")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_score)

    k = sub.add_parser("card", help="ledger.json → 结账单（文本 + SVG）")
    k.add_argument("ledger")
    k.add_argument("--name", default=None, help="输出文件名（默认取 ledger 文件名）")
    k.add_argument("--width", type=int, default=46, help="文本卡宽度")
    k.add_argument("--px", type=int, default=760, help="SVG 宽度")
    k.add_argument("--json", action="store_true")
    k.set_defaults(fn=cmd_card)

    p = sub.add_parser("compare", help="对照图（常见写法 vs 孙本位）→ svg")
    p.add_argument("compare")
    p.add_argument("--name", default=None)
    p.add_argument("--px", type=int, default=880)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_compare)

    r = sub.add_parser("rates", help="看汇率表")
    r.add_argument("--json", action="store_true")
    r.set_defaults(fn=cmd_rates)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
