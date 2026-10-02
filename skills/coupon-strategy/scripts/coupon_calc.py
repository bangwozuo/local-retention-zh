# -*- coding: utf-8 -*-
"""
优惠券策略测算器 —— 面额 / 门槛 / 预算 / ROI 的确定性测算。

职责边界：本脚本只做**券面额安全边界、券成本、ROI 与敏感性的数值测算与产物生成**
（机器的强项）。策略选型（该给哪档客户发哪张券）、话术撰写由模型按 prompt.txt 完成。

核心规则（全部量化）：
  单均毛利     = 客单价 × 毛利率 − 渠道费
  安全面额上限 = 单均毛利 × 30%（面额超过此线即「卖一单亏一单」，必须标红）
  券成本       = 面额 × 核销率（历史核销率区间 20%-44%，缺省按 28% 估）
  门槛建议     = 客单价 × 1.3（提客单且不拦人，区间 1.2-1.5）
  有效期       = 到店券 7-14 天（超过 14 天核销率衰减、到期不核算流失）
  ROI          = 核销人次 × 券后单均毛利 ÷ 总券成本（增量毛利口径，ROI<1 即亏本）

用法：
  python coupon_calc.py --input input.json --outdir out
  python coupon_calc.py --demo

产物：
  out/券方案测算.xlsx   三档方案 / 敏感性分析 / 汇总
  out/券ROI对比.png     三档方案 ROI 与安全上限对照图
  out/coupon_plan.json  机器可读结果（供工作流读取）
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL_DIR))
sys.path.insert(0, os.path.join(REPO, "lib"))

try:
    import assettools as at
except ImportError:  # pragma: no cover
    print("[错误] 未找到 lib/assettools.py。请确认技能位于 <repo>/skills/<slug>/scripts/ 下，"
          "且 <repo>/lib/assettools.py 存在。", file=sys.stderr)
    sys.exit(2)

# 历史核销率经验区间：新店/泛发 20% 上下，老客精准发放可到 44%
REDEEM_RANGE = (0.20, 0.44)
REDEEM_DEFAULT = 0.28
# 安全面额占单均毛利上限：超过即亏本
MARGIN_CAP = 0.30

DEMO = {
    "shop": "老王麻辣烫（社区店）",
    "客单价": 68,          # 元
    "毛利率": 0.60,        # 食材成本 40%
    "渠道费率": 0.0,       # 自有私域发券无扣点；外卖渠道约 0.18-0.23
    "核销率": 0.28,
    "月发放量": 2000,      # 张
}


def calc_plan(客单价: float, 毛利率: float, 渠道费率: float, 面额: float, 门槛: float,
              核销率: float, 发放量: int, 有效期: int) -> dict:
    """单档方案测算。"""
    单均毛利 = 客单价 * (1 - 渠道费率) * 毛利率
    上限 = 单均毛利 * MARGIN_CAP
    券后客单 = 客单价 - 面额
    券后毛利 = 单均毛利 - 面额
    券后毛利率 = 券后毛利 / 券后客单 if 券后客单 > 0 else 0
    核销人次 = 发放量 * 核销率
    总券成本 = 面额 * 核销人次            # 让利总额 = 面额 × 实际核销张数
    增量毛利 = 券后毛利 * 核销人次
    roi = 增量毛利 / 总券成本 if 总券成本 else 0
    risk = "🔴 亏本风险：面额超过单均毛利 30% 上限" if 面额 > 上限 else "✅ 面额在安全线内"
    return {
        "方案": "",  # 由调用方填写
        "面额(元)": 面额,
        "门槛(元)": 门槛,
        "有效期(天)": 有效期,
        "面额占单均毛利": f"{面额 / 单均毛利:.0%}" if 单均毛利 else "-",
        "安全上限(元)": round(上限, 1),
        "风险判定": risk,
        "券后客单(元)": round(券后客单, 1),
        "券后单均毛利(元)": round(券后毛利, 1),
        "券后毛利率": f"{券后毛利率:.0%}",
        "预计核销人次": round(核销人次),
        "总券成本(元)": round(总券成本),
        "增量毛利(元)": round(增量毛利),
        "ROI": round(roi, 2),
    }


def build(payload, outdir):
    shop = payload.get("shop", "未命名门店")
    客单价 = float(payload.get("客单价") or 0)
    毛利率 = float(payload.get("毛利率") or 0)
    渠道费率 = float(payload.get("渠道费率") or 0)
    核销率 = float(payload.get("核销率") or REDEEM_DEFAULT)
    发放量 = int(payload.get("月发放量") or 0)
    if 客单价 <= 0 or not 0 < 毛利率 < 1:
        print("[错误] 客单价与毛利率（0-1 小数）为必填真实数据，缺失时请补数后再跑。",
              file=sys.stderr)
        sys.exit(2)
    if not REDEEM_RANGE[0] <= 核销率 <= REDEEM_RANGE[1]:
        print(f"[提示] 核销率 {核销率:.0%} 在历史经验区间 {REDEEM_RANGE[0]:.0%}-{REDEEM_RANGE[1]:.0%} 之外，"
              "请核对该店真实券码核销数据后再用。", file=sys.stderr)

    单均毛利 = 客单价 * (1 - 渠道费率) * 毛利率
    上限 = round(单均毛利 * MARGIN_CAP, 1)
    门槛 = round(客单价 * 1.3)

    # 三档策略券：引流（轻触达）/ 复购（会员日常）/ 召回（大额，顶格安全线）
    plans = [
        calc_plan(客单价, 毛利率, 渠道费率, max(3, round(上限 * 0.4)), round(客单价 * 1.1), 核销率, 发放量, 14),
        calc_plan(客单价, 毛利率, 渠道费率, round(上限 * 0.7), 门槛, 核销率, 发放量, 10),
        calc_plan(客单价, 毛利率, 渠道费率, round(上限, 0), round(客单价 * 1.5), 核销率, 发放量, 7),
    ]
    for p, name in zip(plans, ["引流券（轻触达）", "复购券（会员日常）", "召回券（沉睡强召回）"]):
        p["方案"] = name

    # 敏感性：核销率 20% / 28% / 44% 三情景（用复购券档测算）
    sens = []
    for r in (0.20, 核销率, 0.44):
        p = calc_plan(客单价, 毛利率, 渠道费率, round(上限 * 0.7), 门槛, r, 发放量, 10)
        sens.append({"情景": f"核销率 {r:.0%}", "预计核销人次": p["预计核销人次"],
                     "总券成本(元)": p["总券成本(元)"], "增量毛利(元)": p["增量毛利(元)"],
                     "ROI": p["ROI"]})

    summary = {
        "门店": shop,
        "客单价(元)": 客单价,
        "毛利率": f"{毛利率:.0%}",
        "单均毛利(元)": round(单均毛利, 1),
        "安全面额上限(元)": 上限,
        "门槛建议(元)": f"满 {门槛} 减（客单价 × 1.3）",
        "核销率假设": f"{核销率:.0%}（历史区间 20%-44%）",
        "ROI 达标线": "ROI ≥ 1.5 才建议执行；1.0-1.5 仅作测试券小量投放",
        "归因方式": "到店核销必须用券码归因，禁止按「到店就算活动带来」粗算",
        "AI 标识": "AI 生成内容",
    }

    at.ensure_outdir(outdir)
    xlsx = at.write_excel(
        os.path.join(outdir, "券方案测算.xlsx"),
        {
            "三档方案": plans,
            "敏感性分析": sens,
            "汇总": [{"项": k, "内容": str(v)} for k, v in summary.items()],
        },
        highlights={
            "三档方案": {"风险判定": "contains:亏本"},
            "敏感性分析": {"ROI": "<1.5"},
        },
        widths={"三档方案": {"风险判定": 34, "方案": 20}},
    )
    chart = at.bar_chart(
        os.path.join(outdir, "券ROI对比.png"),
        [p["方案"] for p in plans],
        [p["ROI"] for p in plans],
        title=f"三档券方案 ROI 对照（安全面额上限 {上限} 元）", ylabel="ROI（增量毛利/券成本）",
    )
    js = at.write_json({"summary": summary, "plans": plans, "sensitivity": sens,
                        "generated_at": at.stamp(),
                        "note": "数值测算结果；策略选型与话术由模型按 prompt.txt 完成"},
                       os.path.join(outdir, "coupon_plan.json"))
    return {"files": [xlsx, chart, js], "summary": summary, "plans": plans}


def main():
    ap = argparse.ArgumentParser(description="优惠券策略测算")
    ap.add_argument("--input", help="输入 JSON（客单价/毛利率/渠道费率/核销率/月发放量）")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        payload = DEMO
    elif a.input:
        payload = at.read_json(a.input)
    else:
        ap.error("需要 --input / --demo 之一")

    r = build(payload, a.outdir)
    s = r["summary"]
    print(f"{s['门店']} —— 安全面额上限 {s['安全面额上限(元)']} 元，{s['门槛建议(元)']}")
    for p in r["plans"]:
        print(f"  {p['方案']}：{p['面额(元)']} 元券，ROI {p['ROI']}，{p['风险判定']}")
    for f in r["files"]:
        print(" 产物:", f)
    at.emit(r)


if __name__ == "__main__":
    main()
