#!/usr/bin/env python3
"""
sun-standard engine —— 孙本位

三件确定性的活，全部纯 stdlib、不联网、不调 LLM：

  1. convert(...)  任意金额 → 孙本位单位（几根香蕉 / 几件羽绒服 / 几次沉默）
  2. score(...)    账本密度跑分：可计算、可解释，逐条列命中/未命中
  3. render_*(...) 结账单渲染：等宽文本卡 + SVG（可截图 / 接 site 管线）

写作本身不在这里。抽科目、挑汇率对照、找损耗项、写正文，由跑这个 skill 的
agent 来做（见 SKILL.md）。代码只负责算得准和排得齐。
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATES_PATH = HERE / "rates.json"


# ---------------------------------------------------------------- rates

def load_rates(path: str | Path | None = None) -> dict:
    return json.loads(Path(path or RATES_PATH).read_text(encoding="utf-8"))


def _to_cny(value: float, currency: str, usd_cny: float) -> float:
    cur = (currency or "CNY").upper()
    if cur in ("CNY", "RMB", "¥", "元"):
        return float(value)
    if cur in ("USD", "$", "US"):
        return float(value) * usd_cny
    raise ValueError(f"不认识的币种: {currency}（只支持 CNY / USD，要加就改 _to_cny）")


def _fmt_ratio(r: float) -> str:
    if r >= 1000:
        return f"{r:,.0f}"
    if r >= 100:
        return f"{r:.0f}"
    if r >= 10:
        return f"{r:.1f}"
    if r >= 1:
        return f"{r:.2f}"
    if r >= 0.01:
        return f"{r:.3f}".rstrip("0")
    if r >= 0.0001:
        return f"{r:.4f}".rstrip("0")
    return f"{r:.2e}"


def convert(amount: float, currency: str = "CNY", rates: dict | None = None,
            lo: float = 0.01, hi: float = 5_000_000.0, limit: int = 6) -> dict:
    """把一笔钱换算成孙本位。只保留读起来还有感觉的量级（lo..hi 之间）。"""
    R = rates or load_rates()
    usd_cny = float(R["meta"]["usd_cny"])
    cny = _to_cny(amount, currency, usd_cny)

    rows = []
    for u in R["money"]:
        unit_cny = _to_cny(u["value"], u["currency"], usd_cny)
        if unit_cny <= 0:
            continue
        ratio = cny / unit_cny
        rows.append({
            "id": u["id"], "name": u["name"], "cw": u.get("cw", ""), "note": u.get("note", ""),
            "unit_value": u["value"], "unit_currency": u["currency"],
            "ratio": ratio, "ratio_display": _fmt_ratio(ratio),
            "in_range": lo <= ratio <= hi,
        })

    keep = [r for r in rows if r["in_range"]]
    # 离 1 越近越好读
    keep.sort(key=lambda r: abs(__import__("math").log10(r["ratio"] or 1e-12)))
    keep = keep[:limit]
    keep.sort(key=lambda r: -r["ratio"])

    return {
        "input": {"amount": amount, "currency": (currency or "CNY").upper()},
        "cny": cny, "usd": cny / usd_cny, "usd_cny": usd_cny,
        "units": keep, "all_units": rows,
    }


# ---------------------------------------------------------------- 计量点

_NUM = r"(?:[0-9][0-9,]*(?:\.[0-9]+)?|[零一二三四五六七八九十百千万亿两]+)"
_UNIT = (
    "元|块|美元|人民币|港币|港元|万|亿|吨|公斤|千克|毫克|微克|克|"
    "公里|千米|米|厘米|分钟|小时|秒|天|日|年|月|周|"
    "卷|张|页|管|支|个|人|次|遍|度|岁|层|间|套|架|辆|台|部|条|把|杯|瓶|根|只|件|份|口|倍|%|％"
)
RE_MEASURE = re.compile(_NUM + r"[，,、\s]{0,1}(?:多|来|几|余)?(?:" + _UNIT + ")")
RE_BIGNUM = re.compile(r"[0-9][0-9,]{2,}(?:\.[0-9]+)?|[一二三四五六七八九两]?[零一二三四五六七八九十]*[百千万亿]+")
RE_MONEY = re.compile(r"[$¥￥]\s?[0-9][0-9,]*(?:\.[0-9]+)?")

# 抒情 / 强化 / 文学腔 —— 孙体里几乎不该出现
SENTIMENT = [
    "非常", "十分", "极其", "极度", "无比", "格外", "异常", "万分", "何其", "多么", "深深",
    "仿佛", "宛如", "犹如", "如同", "彷佛", "好似", "令人", "使人", "不禁", "忍不住",
    "震撼", "感动", "凄美", "苍凉", "孤独", "寂寞", "悲伤", "悲凉", "心酸", "酸楚",
    "撕心", "心碎", "崩溃", "泪流", "哽咽", "灼烧", "刺痛", "澎湃", "汹涌", "荡漾",
    "缠绵", "眷恋", "刻骨", "铭心", "沦陷", "救赎", "治愈", "永恒", "美好", "凄凉",
    "痛彻", "撕裂", "绝望地", "温柔地", "静静地", "缓缓地", "轻轻地",
]

# 克制动作 —— 报数不评论的标志招式
RESTRAINT = [
    "我说好", "我说，好", "我沉默了", "我没有说", "我也没有问", "我没问", "我不知道",
    "什么也没说", "没说话", "我笑了一下", "什么都没有发生", "什么也没干", "什么也没做",
    "什么也没发生", "什么都没发生", "没有人问", "我没有哭", "让我想想", "我批了",
    "我转了", "照常", "我忘了", "我看了一眼", "他不知道", "她不知道", "不需要知道",
    "我没有想", "一个字也不信", "我没有再", "我把它放回去了", "我划掉了", "我没看过",
    "我没有算", "我没算", "我也不知道", "我没有数", "我没数",
]

# 损耗科目 —— 花了钱/做了功，什么也没换来
LOSS = [
    "不退", "没拆", "一支没", "放掉", "不能留", "清不掉", "整块换", "照常",
    "划掉", "删了", "没有通过", "一次也没", "没人告诉", "没用上", "作废", "取消",
    "空置", "空着", "一套也没", "我没看过", "白跑", "退不了",
    "剩下的", "扔了", "倒了", "过期", "没动", "一口也没", "没喝完", "没吃完", "白花",
]

# 结尾升华 —— 出现即扣分（只查末尾几句）
UPLIFT = [
    "也许", "或许", "终究", "终于明白", "我明白了", "我懂了", "人生", "命运", "成长",
    "学会", "懂得", "意义", "值得", "珍惜", "释怀", "放下", "和解", "感恩",
    "愿她", "祝她", "祝愿", "未来", "明天会", "一切都会", "重新开始", "向前走",
    "教会了我", "让我懂", "回头看才", "才是最重要",
]

# 论述腔 —— 作者跳出来说理，孙体不干这个
ARGUE = ["我觉得", "我认为", "我想说", "说实话", "不得不说", "其实我", "总之", "换句话说", "由此可见"]

RE_SENT_SPLIT = re.compile(r"[。！？!?\n]+")


def _cjk_len(s: str) -> int:
    """按显示宽度算长度：全角 2，半角 1。"""
    n = 0
    for ch in s:
        n += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return n


def _spans(text: str) -> list[tuple[int, int, str]]:
    """所有计量点的 span（去重叠）。"""
    found: list[tuple[int, int, str]] = []
    for rx in (RE_MONEY, RE_MEASURE, RE_BIGNUM):
        for m in rx.finditer(text):
            found.append((m.start(), m.end(), m.group(0)))
    found.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    out: list[tuple[int, int, str]] = []
    last_end = -1
    for s, e, g in found:
        if s >= last_end:
            out.append((s, e, g))
            last_end = e
    return out


def _hits(text: str, vocab: list[str]) -> list[str]:
    return [w for w in vocab if w in text]


def _lin(x: float, good: float, bad: float) -> float:
    """good→1，bad→0，线性夹紧。good 可以大于或小于 bad。"""
    if good == bad:
        return 1.0
    v = (x - bad) / (good - bad)
    return max(0.0, min(1.0, v))


def score(text: str) -> dict:
    """账本密度跑分。0–100，逐维度可解释。"""
    body = (text or "").strip()
    chars = _cjk_len(body) / 2 if body else 0          # 折算成"汉字数"
    chars = max(chars, 1)

    sents = [s.strip() for s in RE_SENT_SPLIT.split(body) if s.strip()]
    n_sents = max(len(sents), 1)
    avg_len = sum(_cjk_len(s) / 2 for s in sents) / n_sents

    measures = _spans(body)
    density = len(measures) / chars * 100

    sent_hits = _hits(body, SENTIMENT)
    sent_count = sum(body.count(w) for w in sent_hits)
    sent_density = sent_count / chars * 100

    rest_hits = _hits(body, RESTRAINT)
    rest_count = sum(body.count(w) for w in rest_hits)
    rest_per_500 = rest_count / chars * 500

    loss_hits = _hits(body, LOSS)

    tail = "。".join(sents[-3:])
    up_hits = _hits(tail, UPLIFT)

    argue_hits = _hits(body, ARGUE)

    dims = [
        {"key": "ledger_density", "name": "账本密度", "weight": 25,
         "raw": round(density, 2), "unit": "计量点/百字", "target": "≥ 2.4",
         "ratio": _lin(density, 2.4, 0.3),
         "say": f"计量点{cn_qty(len(measures))}个，{cn_num(chars)}字。每百字{cn_num(round(density, 2))}个，目标两点四。"},

        {"key": "brevity", "name": "句子短", "weight": 20,
         "raw": round(avg_len, 1), "unit": "字/句", "target": "≤ 16",
         "ratio": _lin(avg_len, 16, 34),
         "say": f"{cn_qty(n_sents)}句，平均一句{cn_num(round(avg_len, 1))}字。目标十六以内。"},

        {"key": "restraint", "name": "克制不评论", "weight": 20,
         "raw": round(rest_per_500, 2), "unit": "次/500字", "target": "≥ 1.5",
         "ratio": _lin(rest_per_500, 1.5, 0.0),
         "say": (f"克制动作{cn_qty(rest_count)}处：{'、'.join(rest_hits[:6])}。"
                 if rest_hits else "一处克制动作也没有。嘴一直在说话。")},

        {"key": "no_sentiment", "name": "不抒情", "weight": 15,
         "raw": round(sent_density, 2), "unit": "抒情词/百字", "target": "= 0",
         "ratio": _lin(sent_density, 0.0, 1.2),
         "say": (f"抒情词{cn_qty(sent_count)}处：{'、'.join(sent_hits[:8])}。"
                 if sent_hits else "抒情词零处。干净。")},

        {"key": "loss_items", "name": "有损耗科目", "weight": 10,
         "raw": len(loss_hits), "unit": "项", "target": "≥ 2",
         "ratio": _lin(len(loss_hits), 2, 0),
         "say": (f"损耗科目{cn_qty(len(loss_hits))}项：{'、'.join(loss_hits[:6])}。"
                 if loss_hits else "没有一项花了什么也没换来的东西。最疼的地方缺了。")},

        {"key": "no_uplift", "name": "结尾不升华", "weight": 10,
         "raw": len(up_hits) + len(argue_hits), "unit": "处", "target": "= 0",
         "ratio": 1.0 if not up_hits and not argue_hits else _lin(len(up_hits) * 2 + len(argue_hits), 0, 3),
         "say": ("结尾干净。论述腔也没有。" if not up_hits and not argue_hits else
                 "、".join([f"结尾升华「{w}」" for w in up_hits]
                          + [f"论述腔「{w}」" for w in argue_hits]) + "。")},
    ]
    for d in dims:
        d["detail"] = d["say"]

    for d in dims:
        d["score"] = round(d["weight"] * d["ratio"], 1)
    total = round(sum(d["score"] for d in dims), 1)

    if total >= 85:
        grade, verdict = "A", "孙本位。可以发。"
    elif total >= 70:
        grade, verdict = "B", "像了，但还有软的地方。看扣分项。"
    elif total >= 50:
        grade, verdict = "C", "半途而废：数字有了，嘴还在说话。"
    else:
        grade, verdict = "D", "这是散文，不是账。回去重新审计。"

    return {
        "total": total, "grade": grade, "verdict": verdict,
        "chars": int(chars), "sentences": n_sents,
        "dimensions": dims,
        "measures_sample": [g for _, _, g in measures[:20]],
    }


def format_score(rep: dict) -> str:
    """跑分也报数，不排表。"""
    L = [f"账本密度 {rep['total']} / 100。", ""]
    for d in rep["dimensions"]:
        if d["ratio"] >= 0.999:
            tail = f"{cn_num(d['weight'])}分，拿满。"
        elif d["ratio"] <= 0.001:
            tail = f"{cn_num(d['weight'])}分，扣光。"
        else:
            tail = f"{cn_num(d['weight'])}分里拿到{cn_num(d['score'])}。"
        L.append(d["say"] + tail)
    if rep["measures_sample"]:
        L.append("")
        L.append("计量点：" + "、".join(rep["measures_sample"][:12]) + "。")
    L.append("")
    L.append(rep["verdict"])
    return "\n".join(L)


# ---------------------------------------------------------------- 结账单

_CN_D = "零一二三四五六七八九"
_CN_U = ["", "十", "百", "千"]
_CN_B = ["", "万", "亿", "万亿"]


def _cn_4(n: int) -> str:
    """0..9999 → 中文。十八 不写 一十八；两千 不写 二千。"""
    digits = [int(c) for c in str(n)]
    L = len(digits)
    s = ""
    zero_pending = False
    for i, d in enumerate(digits):
        pos = L - 1 - i          # 3千 2百 1十 0个
        if d == 0:
            zero_pending = True
            continue
        if zero_pending and s:
            s += "零"
        zero_pending = False
        if d == 1 and pos == 1 and not s:
            s += "十"
        elif d == 2 and pos == 3:
            s += "两千"
        else:
            s += _CN_D[d] + _CN_U[pos]
    return s


def cn_num(x) -> str:
    """数字 → 中文。整数走位值，小数走"点"逐位。太小或太碎就退回阿拉伯数字。"""
    try:
        f = float(x)
    except (TypeError, ValueError):
        return str(x)
    if f < 0:
        return "负" + cn_num(-f)
    if f != int(f):
        head, _, tail = f"{f:.4f}".rstrip("0").partition(".")
        if len(tail) > 3 or f < 0.01:
            return f"{x}"
        return cn_num(int(head)) + "点" + "".join(_CN_D[int(c)] for c in tail)

    n = int(f)
    if n == 0:
        return "零"
    if n >= 10 ** 16:
        return f"{n:,}"
    groups = []
    while n > 0:
        groups.append(n % 10000)
        n //= 10000
    parts = []
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        seg = "两" if (g == 2 and i > 0) else _cn_4(g)
        if parts and g < 1000:
            seg = "零" + seg
        parts.append(seg + _CN_B[i])
    return "".join(parts)


def cn_qty(x) -> str:
    """量词前面的数。二口 → 两口；十二口不变。"""
    try:
        if float(x) == 2:
            return "两"
    except (TypeError, ValueError):
        pass
    return cn_num(x)


def _money_str(amount: float, currency: str) -> str:
    """带符号的西式写法。给 convert 的表头和 --json 用。"""
    cur = (currency or "CNY").upper()
    sym = {"CNY": "¥", "RMB": "¥", "USD": "$"}.get(cur, "")
    if float(amount) == int(amount):
        return f"{sym}{int(amount):,}"
    return f"{sym}{amount:,.2f}"


def cn_money(amount: float, currency: str = "CNY") -> str:
    """孙体写法：一百五十块 / 九块九 / 四块九毛五 / 三千万元 / 二十万美元。"""
    cur = (currency or "CNY").upper()
    f = float(amount)
    if cur in ("USD", "$", "US"):
        return cn_num(amount) + "美元"
    if abs(f) >= 10000:
        return cn_num(amount) + "元"
    if f == int(f):
        return cn_num(int(f)) + "块"
    # 角分：九块九 / 四块九毛五 / 四块零五分
    cents = int(round(abs(f) * 100)) % 100
    jiao, fen = divmod(cents, 10)
    head = cn_num(int(abs(f))) + "块"
    if fen == 0:
        return head + _CN_D[jiao]
    if jiao == 0:
        return head + "零" + _CN_D[fen] + "分"
    return head + _CN_D[jiao] + "毛" + _CN_D[fen]


def _item_value(it: dict) -> str:
    """孙体值。value_display 原样用（作者自己负责写成中文）。"""
    if it.get("value_display"):
        return str(it["value_display"])
    if "amount" in it:
        return cn_money(it["amount"], it.get("currency", "CNY"))
    if "qty" in it:
        return cn_qty(it["qty"]) + str(it.get("unit", ""))
    return ""


def prose_lines(ledger: dict) -> list[str]:
    """把账本摊成孙体报数。

    普通科目：  咖啡二十二块。那天没买。
    损耗科目：  还有行情软件的年费，一千零五十六块，还剩十一个月。
                （"还有…"是原文结算段的句式，本身就代表"花了，什么也没换来"）
    """
    out = []
    for it in ledger.get("items") or []:
        label = (it.get("label") or "").strip()
        val = _item_value(it)
        note = (it.get("note") or "").strip().rstrip("。")
        if it.get("loss"):
            seg = "还有" + label
            if val:
                seg += "，" + val
            if note:
                seg += "，" + note
            out.append(seg + "。")
        else:
            seg = label + val
            out.append(seg + "。" + (note + "。" if note else ""))
    return out


def render_text_card(ledger: dict, width: int = 46) -> str:
    """孙体结账单。报数，不排表。"""
    title = (ledger.get("title") or "结账").rstrip("。")
    subject = (ledger.get("subject") or "").strip().rstrip("。")
    footer = (ledger.get("footer") or "什么都没有发生").rstrip("。")

    head = title + "。" + (subject + "。" if subject else "")
    L = [head, ""]
    L += prose_lines(ledger)
    L += ["", footer + "。"]
    return "\n".join(L)


def _wrap(s: str, cols: int) -> list[str]:
    """按显示宽度折行（CJK 算 2）。"""
    lines, cur, w = [], "", 0
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if w + cw > cols and cur:
            lines.append(cur)
            cur, w = "", 0
        cur += ch
        w += cw
    if cur:
        lines.append(cur)
    return lines


_SVG_ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def _esc(s: str) -> str:
    return "".join(_SVG_ESC.get(c, c) for c in str(s))


def render_compare_svg(cmp: dict, px: int = 880, cols: int = 62, scale: float = 1.0) -> str:
    """对照图。上下两栏，上压暗下提亮。竖排是为了手机。

    scale 放大字号和行距。发社交平台时缩略图会缩到一半宽，
    行数少的图配大字才看得清，所以首图用 scale 1.4 左右、行数砍到五行以内。

    schema: {title, left:{label,lines[],verdict}, right:{label,lines[],verdict}}
    """
    def s(v):
        return round(v * scale, 1)

    title = (cmp.get("title") or "").strip()
    cols = max(12, int(cols / scale))
    pad_x = 56
    y = s(92)
    body: list[str] = []

    FONT = ("ui-monospace,'SF Mono',Menlo,Consolas,"
            "'PingFang SC','Hiragino Sans GB','Microsoft YaHei',monospace")

    if title:
        body.append(f'<text x="{pad_x}" y="{y}" class="t">{_esc(title)}</text>')
        y += s(62)

    for side, dim in (("left", True), ("right", False)):
        blk = cmp.get(side) or {}
        label = (blk.get("label") or "").strip()
        if label:
            body.append(f'<text x="{pad_x}" y="{y}" class="tag">{_esc(label)}</text>')
            y += s(34)
        cls = "dim" if dim else "ln"
        for raw in blk.get("lines") or []:
            if not raw.strip():
                y += s(14)
                continue
            for i, seg in enumerate(_wrap(raw, cols)):
                x = pad_x + (0 if i == 0 else s(22))
                body.append(f'<text x="{x}" y="{y}" class="{cls}">{_esc(seg)}</text>')
                y += s(32)
            y += s(6)
        v = (blk.get("verdict") or "").strip()
        if v:
            y += s(14)
            for seg in _wrap(v, cols):
                body.append(f'<text x="{pad_x}" y="{y}" class="verdict">{_esc(seg)}</text>')
                y += s(36)
        y += s(46)

    y += s(4)
    body.append(f'<text x="{px - pad_x}" y="{y}" class="mark" text-anchor="end">孙本位 · sun-standard</text>')
    h = int(y + s(40))

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{h}" viewBox="0 0 {px} {h}" role="img" aria-label="{_esc(title)}">
  <title>{_esc(title)}</title>
  <style>
    text {{ font-family: {FONT}; }}
    .bg      {{ fill:#0d0d0f; }}
    .t       {{ fill:#f2f2f2; font-size:{s(28)}px; }}
    .tag     {{ fill:#5f5f68; font-size:{s(14)}px; letter-spacing:.22em; }}
    .dim     {{ fill:#6a6a72; font-size:{s(19)}px; }}
    .ln      {{ fill:#dcdce1; font-size:{s(19)}px; }}
    .verdict {{ fill:#f2f2f2; font-size:{s(22)}px; }}
    .mark    {{ fill:#3d3d45; font-size:{s(12)}px; letter-spacing:.16em; }}
  </style>
  <rect class="bg" width="{px}" height="{h}"/>
  {chr(10).join("  " + b for b in body)}
</svg>
'''


def render_svg_card(ledger: dict, px: int = 880, cols: int = 64) -> str:
    """孙体结账单 SVG。深底、散文、没有一根线。cols 按显示列算（CJK 占 2）。"""
    title = (ledger.get("title") or "结账").rstrip("。")
    subject = (ledger.get("subject") or "").strip().rstrip("。")
    footer = (ledger.get("footer") or "什么都没有发生").rstrip("。")

    pad_x = 56
    line_h, gap = 36, 14
    y = 96
    body: list[str] = []

    FONT = ("ui-monospace,'SF Mono',Menlo,Consolas,"
            "'PingFang SC','Hiragino Sans GB','Microsoft YaHei',monospace")

    head = title + "。" + (subject + "。" if subject else "")
    body.append(f'<text x="{pad_x}" y="{y}" class="t">{_esc(head)}</text>')
    y += 58

    for ln in prose_lines(ledger):
        for i, seg in enumerate(_wrap(ln, cols)):
            body.append(f'<text x="{pad_x + (0 if i == 0 else 22)}" y="{y}" class="ln">{_esc(seg)}</text>')
            y += line_h
        y += gap

    y += 22
    for i, seg in enumerate(_wrap(footer + "。", cols)):
        body.append(f'<text x="{pad_x}" y="{y}" class="foot">{_esc(seg)}</text>')
        y += line_h + 4
    y += 26
    body.append(f'<text x="{px - pad_x}" y="{y}" class="mark" text-anchor="end">孙本位 · sun-standard</text>')
    h = y + 40

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{h}" viewBox="0 0 {px} {h}" role="img" aria-label="{_esc(title)} {_esc(subject)}">
  <title>{_esc(title)}{(" · " + _esc(subject)) if subject else ""}</title>
  <style>
    text {{ font-family: {FONT}; }}
    .bg   {{ fill:#0d0d0f; }}
    .t    {{ fill:#f2f2f2; font-size:28px; }}
    .ln   {{ fill:#d9d9de; font-size:20px; }}
    .foot {{ fill:#f2f2f2; font-size:22px; }}
    .mark {{ fill:#3d3d45; font-size:12px; letter-spacing:.16em; }}
  </style>
  <rect class="bg" width="{px}" height="{h}"/>
  {chr(10).join("  " + b for b in body)}
</svg>
'''
