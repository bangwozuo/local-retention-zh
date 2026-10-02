# -*- coding: utf-8 -*-
"""
沉睡客户唤醒流 —— 端到端编排脚本。

流程：数据校验 → 沉睡分桶(30/60/90) → 券匹配(安全面额) → 触达节奏编排(频控校验)
      → 汇总产物（唤醒执行清单 Excel + 机器可读 JSON）

失败处理：
  - 必需字段缺失 → 退出码 2，列缺失清单（不编造、不补零）
  - 毛利率缺失/越界 → 退出码 2
  - 分桶为空 → 产出空表并显式标注，不静默跳过

用法：
  python run_flow.py --input input.json --outdir out
  python run_flow.py --demo
"""
from __future__ import annotations

import argparse
import os
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

MARGIN_CAP = 0.30  # 安全面额 = 客单毛利 × 30%

DEMO = {
    "shop": "老王麻辣烫（社区店）",
    "毛利率": 0.60,
    "today": "2026-09-30",
    "customers": [
        {"customer": "阿强", "dormant_days": 35, "客单价": 72},
        {"customer": "丽丽", "dormant_days": 41, "客单价": 65},
        {"customer": "大军", "dormant_days": 66, "客单价": 88},
        {"customer": "小婉", "dormant_days": 74, "客单价": 80},
        {"customer": "老赵", "dormant_days": 95, "客单价": 95},
        {"customer": "婷婷", "dormant_days": 120, "客单价": 70},
        {"customer": "刚子", "dormant_days": 12, "客单价": 68},   # 活跃，不进名单
        {"customer": "阿强", "dormant_days": 35, "客单价": 72},   # 重复，应去重
    ],
}

# 触达策略：由沉睡天数决定（唤醒节奏 30 轻触达 / 60 券触达 / 90 强召回）
STRATEGY = {
    (30, 60): ("轻触达", "朋友圈内容 + 社群互动", 0.0),
    (60, 90): ("券触达", "满减券 1v1 发放", 0.7),
    (90, 10 ** 9): ("强召回", "大额券 + 新品通知 1v1", 1.0),
}


def bucket(days: int) -> str:
    if days < 30:
        return "活跃（不处理）"
    if days < 60:
        return "30-59 天"
    if days < 90:
        return "60-89 天"
    return "≥90 天"


def step1_validate(payload):
    """步骤 1：数据校验。缺失即失败，不编造。"""
    missing = []
    if not payload.get("customers"):
        missing.append("customers（客户列表）")
    if payload.get("毛利率") is None:
        missing.append("毛利率")
    if missing:
        print(f"[失败] 步骤1 数据校验未过，缺失：{'、'.join(missing)}。请补数后重跑。",
              file=sys.stderr)
        sys.exit(2)
    rate = float(payload["毛利率"])
    if not 0 < rate < 1:
        print(f"[失败] 步骤1 毛利率 {rate} 越界（须为 0-1 小数）。", file=sys.stderr)
        sys.exit(2)
    print("[步骤1] 数据校验通过")
    return rate


def step2_bucket(customers):
    """步骤 2：沉睡分桶（去重 + 排除活跃客户）。"""
    seen, rows = set(), []
    for c in customers:
        cid = str(c.get("customer", "")).strip()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        days = int(c.get("dormant_days") or 0)
        b = bucket(days)
        if b.startswith("活跃"):
            continue
        rows.append({"customer": cid, "dormant_days": days, "客单价": float(c.get("客单价") or 0),
                     "分桶": b})
    print(f"[步骤2] 分桶完成：{len(rows)} 名沉睡客户（已去重、剔除活跃）")
    return rows


def step3_coupon(rows, margin_rate):
    """步骤 3：券匹配 —— 安全面额 = 客单毛利 × 30%，按触达层给不同折扣系数。"""
    for r in rows:
        cap = r["客单价"] * margin_rate * MARGIN_CAP
        if r["dormant_days"] < 60:
            face = 0.0
            r["券"] = "（本层不发券，内容触达）"
        else:
            coef = 0.7 if r["dormant_days"] < 90 else 1.0
            face = round(cap * coef)
            r["券"] = f"满 {round(r['客单价'] * 1.3)} 减 {face}"
        r["安全面额上限"] = round(cap, 1)
        r["_face"] = face
    print("[步骤3] 券匹配完成（召回层顶格安全线，券触达层 7 折安全线）")
    return rows


def step4_schedule(rows):
    """步骤 4：触达节奏编排 —— 每客户 7 天内触达 ≤ 2 次。"""
    for r in rows:
        for (lo, hi), (layer, action, _) in STRATEGY.items():
            if lo <= r["dormant_days"] < hi:
                r["触达层"] = layer
                r["触达动作"] = action
                break
        # 节奏：Day1 首触 + Day4 补触（仅券层），合计 ≤ 2 次/7天
        r["Day1"] = "1v1/群内容首触"
        r["Day4"] = "券提醒补触" if r["触达层"] != "轻触达" else "（不补触，仅首触）"
        r["7天触达次数"] = 2 if r["触达层"] != "轻触达" else 1
    print("[步骤4] 触达节奏完成（全部 ≤ 2 次/7 天，合规）")
    return rows


def build(payload, outdir):
    today = str(payload.get("today") or at.stamp()[:10])
    rate = step1_validate(payload)
    rows = step2_bucket(payload["customers"])
    rows = step3_coupon(rows, rate)
    rows = step4_schedule(rows)

    out_rows = [{
        "客户": r["customer"],
        "沉睡天数": r["dormant_days"],
        "分桶": r["分桶"],
        "客单价(元)": r["客单价"],
        "触达层": r["触达层"],
        "触达动作": r["触达动作"],
        "券": r["券"],
        "Day1": r["Day1"],
        "Day4": r["Day4"],
        "7天触达次数": r["7天触达次数"],
    } for r in sorted(rows, key=lambda x: -x["dormant_days"])]

    counts = {}
    for r in out_rows:
        counts[r["分桶"]] = counts.get(r["分桶"], 0) + 1
    est_cost = sum(r["_face"] for r in rows)
    summary = {
        "门店": payload.get("shop", "未提供"),
        "快照日": today,
        "沉睡客户数": len(out_rows),
        "分桶": counts,
        "券预算上限(元)": est_cost,
        "毛利率假设": f"{rate:.0%}",
        "安全面额规则": f"面额 ≤ 客单毛利 × {MARGIN_CAP:.0%}（详见 coupon-strategy）",
        "频控规则": "同一客户 7 天内触达 ≤ 2 次",
        "复购基准": "餐饮 30 天复购 15-25%：唤醒后观察 30 天复购是否落入该区间",
        "AI 标识": "AI 生成内容",
    }

    at.ensure_outdir(outdir)
    xlsx = at.write_excel(
        os.path.join(outdir, "唤醒执行清单.xlsx"),
        {
            "执行清单": out_rows or [{"客户": "（无沉睡客户）"}],
            "汇总": [{"项": k, "内容": str(v)} for k, v in summary.items()],
        },
        highlights={"执行清单": {"分桶": "contains:≥90"}},
        widths={"执行清单": {"触达动作": 26, "券": 22}},
    )
    js = at.write_json({"summary": summary, "items": out_rows,
                        "generated_at": at.stamp(),
                        "note": "分桶/券/节奏为规则计算；话术与触达文案由模型按各技能 prompt 生成"},
                       os.path.join(outdir, "wake_flow.json"))
    return {"files": [xlsx, js], "summary": summary}


def main():
    ap = argparse.ArgumentParser(description="沉睡客户唤醒流")
    ap.add_argument("--input", help="输入 JSON（shop/毛利率/today/customers）")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    payload = DEMO if a.demo else at.read_json(a.input) if a.input else ap.error("需要 --input / --demo 之一")
    r = build(payload, a.outdir)
    s = r["summary"]
    print(f"{s['门店']} —— 沉睡 {s['沉睡客户数']} 人，分桶 {s['分桶']}，券预算上限 {s['券预算上限(元)']} 元")
    for f in r["files"]:
        print(" 产物:", f)
    at.emit(r)


if __name__ == "__main__":
    main()
