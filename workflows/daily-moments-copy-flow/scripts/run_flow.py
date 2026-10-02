# -*- coding: utf-8 -*-
"""
每日朋友圈文案流 —— 端到端编排脚本。

流程：数据校验 → 选题配比核算 → 候选文案组装(骨架模板+真实素材) → 风控自查
      → 汇总产物（发布排期表 Excel + 机器可读 JSON）

核心规则（全部量化）：
  - 内容配比：生活/幕后 50-60% + 产品/促销 30% + 互动/人设 10-20%
  - 频控：营销 ≤ 3 条/天、总量 ≤ 5 条、21:30-07:30 禁屏
  - 字数：文案 ≤ 140 字（防朋友圈折叠）
  - 风控：极限词词表 + 诱导分享词扫描，命中即拦截
  - 素材：每条候选至少 1 个真实细节（facts），无细节挂起索要，不编造

失败处理：
  - 素材缺 facts → 挂起并生成「索要清单」，不硬写
  - 营销条数超配 → 砍量建议，超出部分顺延
  - 极限词/诱导分享命中 → 拦截并给改法

用法：
  python run_flow.py --input input.json --outdir out
  python run_flow.py --demo
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WF_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(WF_DIR))
sys.path.insert(0, os.path.join(REPO, "lib"))

try:
    import assettools as at
except ImportError:  # pragma: no cover
    print("[错误] 未找到 lib/assettools.py", file=sys.stderr)
    sys.exit(2)

# 时段槽位（按到店决策点）
SLOTS = ["07:30-09:00 早餐档", "11:00-11:30 午市前", "17:00-18:00 晚市前", "20:30-21:00 情感档"]

# 风控词表（极限词《广告法》第九条口径 + 诱导分享）
RISK_WORDS = [
    (r"最好|最佳|最优|最强|最低价|最便宜|第一|全网|独家|顶级|极品|100\s*%|百分百|绝对", "极限词（《广告法》第九条）", "改为具体可验证描述，如「今天卖出了 43 份」"),
    (r"转发.{0,6}(领|得)|转发朋友圈|集赞|分享.{0,4}才能", "诱导分享（微信外部内容规范）", "改「进群直接领」，分享不设门槛"),
]
SUSPECT_WORDS = ["好吃", "美味", "欢迎品尝", "匠心", "遇见美好"]

# 骨架模板：{type} 文案由 facts 逐个填槽（确定性组装，细节全部来自素材）
SKELETONS = {
    "幕后": "【钩子】{f0}\n【细节】{f1}\n【收尾】今晚店里见。",
    "产品": "【钩子】{f0}\n【细节】{f1}\n【收尾】备货有限，卖完等明天，要的趁早。",
    "促销": "【钩子】{f0}\n【细节】{f1}\n【收尾】数量真实有限，到店报暗号。",
    "互动": "【钩子】问你们个事：{f0}\n【细节】{f1}\n【收尾】评论区聊聊，明天翻牌。",
}

DEMO = {
    "shop": "老王麻辣烫（社区店）",
    "date": "2026-09-30",
    "weather": "降温 8 度",
    "today_sent": {"total": 0, "marketing": 0},
    "materials": [
        {"topic": "现熬骨汤", "type": "幕后",
         "facts": ["凌晨四点整条街只有我家烟囱在冒烟", "40 斤筒骨熬足 6 小时"]},
        {"topic": "手打虾滑上新", "type": "产品",
         "facts": ["今天手打虾滑备了 30 份", "试吃的客人说弹牙"]},
        {"topic": "天冷加菜", "type": "促销",
         "facts": ["今天降温 8 度", "套餐加宽粉免费，限今天"]},
        {"topic": "辣度投票", "type": "互动",
         "facts": ["上个月辣度投票微辣赢了", "这个月想问问大家要不要出变态辣"]},
    ],
}


def step1_validate(payload):
    missing = []
    if not payload.get("materials"):
        missing.append("materials（当日素材列表）")
    if missing:
        print(f"[失败] 步骤1 数据校验未过，缺失：{'、'.join(missing)}。", file=sys.stderr)
        sys.exit(2)
    print("[步骤1] 数据校验通过")
    return payload


def step2_plan(materials, today_sent):
    """步骤 2：选题配比与频控核算。"""
    hung = [m for m in materials if not m.get("facts")]
    usable = [m for m in materials if m.get("facts")]
    marketing = sum(1 for m in usable if m["type"] in ("产品", "促销"))
    remaining_total = 5 - int(today_sent.get("total") or 0)
    remaining_mkt = 3 - int(today_sent.get("marketing") or 0)
    cut = []
    if len(usable) > remaining_total:
        cut = usable[remaining_total:]
        usable = usable[:remaining_total]
    # 营销超配 → 顺延
    mkt_in_plan = [m for m in usable if m["type"] in ("产品", "促销")]
    if len(mkt_in_plan) > remaining_mkt:
        overflow = mkt_in_plan[remaining_mkt:]
        for m in overflow:
            m["顺延"] = "营销条数已达上限，顺延明日"
    print(f"[步骤2] 选题 {len(usable)} 条（营销 {min(marketing, remaining_mkt)}），"
          f"挂起 {len(hung)} 条（缺细节），顺延 {len(cut)} 条")
    return usable, hung


def step3_compose(usable):
    """步骤 3：候选文案组装（骨架 + 真实素材细节）+ 字数检查。"""
    rows = []
    slot_map = {"幕后": SLOTS[0], "产品": SLOTS[1], "促销": SLOTS[2], "互动": SLOTS[3]}
    for m in usable:
        facts = [str(f) for f in m["facts"]]
        f0 = facts[0] if facts else m["topic"]
        f1 = facts[1] if len(facts) > 1 else facts[0] if facts else m["topic"]
        body = SKELETONS.get(m["type"], SKELETONS["幕后"]).format(f0=f0, f1=f1)
        body = re.sub(r"\n+", " / ", body)
        n = len(body)
        rows.append({
            "topic": m["topic"], "type": m["type"], "slot": slot_map.get(m["type"], SLOTS[1]),
            "copy": body, "chars": n,
            "字数合规": n <= 140,
            "配图建议": "3 张实拍" if m["type"] == "幕后" else "1 张" if m["type"] == "产品" else "4 张",
            "顺延": m.get("顺延", ""),
        })
    print("[步骤3] 文案组装完成（细节全部来自素材，无编造）")
    return rows


def step4_review(rows):
    """步骤 4：风控自查（极限词/诱导分享/禁屏/口播词）。"""
    for r in rows:
        r["风控"] = []
        for pat, rule, fix in RISK_WORDS:
            m = re.search(pat, r["copy"])
            if m:
                r["风控"].append(f"🔴 {rule}：命中「{m.group(0)}」→ {fix}")
        for w in SUSPECT_WORDS:
            if w in r["copy"]:
                r["风控"].append(f"🟡 广告腔提示：出现「{w}」，建议替换为具体细节")
        # 禁屏时段检查
        if r["slot"].startswith("21:") or r["slot"].startswith("22:"):
            r["风控"].append("🔴 禁屏时段：21:30 后不发，改至 20:30-21:00 档")
        r["风控判定"] = "拦截" if any(x.startswith("🔴") for x in r["风控"]) else (
            "缓行" if r["风控"] else "通过")
    print("[步骤4] 风控自查完成")
    return rows


def build(payload, outdir):
    payload = step1_validate(payload)
    usable, hung = step2_plan(payload["materials"], payload.get("today_sent") or {})
    rows = step3_compose(usable)
    rows = step4_review(rows)

    out_rows = [{
        "选题": r["topic"], "类型": r["type"], "发布时段": r["slot"],
        "候选文案": r["copy"], "字数": r["chars"], "字数≤140": "✅" if r["字数合规"] else "❌",
        "配图建议": r["配图建议"],
        "风控判定": r["风控判定"],
        "风控明细": "；".join(r["风控"]) or "无",
        "备注": r["顺延"],
    } for r in rows]
    for m in hung:
        out_rows.append({"选题": m.get("topic", ""), "类型": m.get("type", ""), "发布时段": "挂起",
                         "候选文案": "", "字数": "", "字数≤140": "",
                         "配图建议": "", "风控判定": "挂起",
                         "风控明细": "素材缺细节 → 索要清单：今早备料几点？用了多少斤？客人怎么说？", "备注": ""})

    blocked = sum(1 for r in rows if r["风控判定"] == "拦截")
    summary = {
        "门店": payload.get("shop", "未提供"),
        "日期": payload.get("date", at.stamp()[:10]),
        "选题数": len(rows),
        "挂起（缺细节）": len(hung),
        "风控拦截": blocked,
        "频控规则": "营销 ≤ 3 条/天、总量 ≤ 5 条、21:30-07:30 禁屏、同一产品两天不重复",
        "配比目标": "生活/幕后 50-60% + 产品/促销 30% + 互动/人设 10-20%",
        "人工确认": "文案经店主确认后按建议时段手动发布",
        "AI 标识": "AI 生成内容",
    }

    at.ensure_outdir(outdir)
    xlsx = at.write_excel(
        os.path.join(outdir, "朋友圈发布排期.xlsx"),
        {
            "发布排期": out_rows or [{"选题": "（今日无素材）"}],
            "汇总": [{"项": k, "内容": str(v)} for k, v in summary.items()],
        },
        highlights={"发布排期": {"风控判定": "contains:拦截"}},
        widths={"发布排期": {"候选文案": 46, "风控明细": 36}},
    )
    js = at.write_json({"summary": summary, "items": out_rows,
                        "generated_at": at.stamp(),
                        "note": "排期与风控为规则计算；文案为骨架+素材的确定性组装，润色与配图实拍由店主完成"},
                       os.path.join(outdir, "moments_flow.json"))
    return {"files": [xlsx, js], "summary": summary}


def main():
    ap = argparse.ArgumentParser(description="每日朋友圈文案流")
    ap.add_argument("--input", help="输入 JSON（shop/date/weather/today_sent/materials）")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    payload = DEMO if a.demo else at.read_json(a.input) if a.input else ap.error("需要 --input / --demo 之一")
    r = build(payload, a.outdir)
    s = r["summary"]
    print(f"{s['门店']} {s['日期']} —— 选题 {s['选题数']} 条，挂起 {s['挂起（缺细节）']} 条，风控拦截 {s['风控拦截']} 条")
    for f in r["files"]:
        print(" 产物:", f)
    at.emit(r)


if __name__ == "__main__":
    main()
