# -*- coding: utf-8 -*-
"""
社群活动 SOP 流 —— 端到端编排脚本。

流程：数据校验 → 健康度诊断(基线对照) → 活动模板匹配(行业×目标) → 周排期与验收
      → 汇总产物（SOP 报告 Word + 排期 Excel + 机器可读 JSON）

健康度基线（全部量化）：
  - 群规模 150-300 人（> 400 建议拆群）
  - 7 日发言人数占比 ≥ 15%（< 8% 判沉默群，先重启再排常规活动）
  - 广告消息占比 ≤ 30%（> 50% 判劣化群）
  - 入群 72h 首单转化 ≥ 20%；月退群率 ≤ 5%

活动模板库：餐饮 / 零售 / 美业 × 目标（拉新 / 复购 / 清库存 / 会员日），
每个动作带时段、验收标准；触达频控 7 天内 ≤ 2 次/客户。

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

DEMO = {
    "shop": "老王麻辣烫（社区店）",
    "industry": "餐饮",
    "week_goal": "会员日预热",
    "staff": "店长兼职管群，1 名店员协助",
    "groups": [
        {"name": "老王麻辣烫·街坊群", "members": 260, "weekly_speakers": 42, "daily_msgs": 68, "ad_ratio": 0.2},
        {"name": "老王麻辣烫·外卖客群", "members": 455, "weekly_speakers": 9, "daily_msgs": 12, "ad_ratio": 0.6},
    ],
}

# 行业 × 目标 → 活动模板（动作, 时段, 验收标准, 触达层级）
ACTIVITY_LIBRARY = {
    ("餐饮", "会员日预热"): [
        ("D-3 新品投票 + 会员日规则预告", "周一 11:00", "投票 ≥ 群人数 12%"),
        ("D-2 晒后厨/备料信任内容", "周三 17:30", "当日消息 ≥ 40 条"),
        ("D-1 高价值老客 1v1 定向提醒", "周五 18:00", "提醒名单店长过目"),
        ("当天 会员日开启（双倍积分+专属价）", "活动日 10:00", "核销 ≥ 上月会员日均值"),
        ("次日 真实战报（脱敏公示）", "次日 12:00", "战报数据以收银台账为准"),
    ],
    ("餐饮", "拉新"): [
        ("到店立牌 + 结账口播扫码入群", "全周", "日新增 ≥ 10 人"),
        ("老带新双向奖励（双方各得 15 元券）", "全周", "周新增 ≥ 30 人"),
        ("首单钩子：入群领 5 元无门槛券", "全周", "72h 首单转化 ≥ 20%"),
    ],
    ("零售", "清库存"): [
        ("临期清单盘点 + 定价", "周一", "清库存毛利 ≥ 0"),
        ("群内秒杀（限 30 份，晚 8 点）", "周三 20:00", "2 小时售罄率 ≥ 80%"),
        ("秒杀连带满额赠正价小样", "周三 20:00", "连带率 ≥ 30%"),
    ],
    ("美业", "空位变现"): [
        ("作品日：本周作品 5-8 张", "周二 14:00", "消息 ≥ 30 条"),
        ("空位闪订：次日空位 5 折限 2 个", "周四 20:00", "闪订成功率 ≥ 50%"),
        ("客户返图日", "周六", "返图 ≥ 3 张"),
    ],
}
FALLBACK = [
    ("晒单/作品/菜单投票（行业通选）", "周三 17:30", "消息 ≥ 30 条"),
    ("群内专属价接龙", "周五 10:00", "接龙 ≥ 10 单"),
    ("周末抽奖（小额高频）", "周日 20:00", "参与 ≥ 30 人"),
]


def step1_validate(payload):
    missing = []
    if not payload.get("groups"):
        missing.append("groups（群列表与近况）")
    if payload.get("industry") is None:
        missing.append("industry（行业）")
    if missing:
        print(f"[失败] 步骤1 数据校验未过，缺失：{'、'.join(missing)}。", file=sys.stderr)
        sys.exit(2)
    print("[步骤1] 数据校验通过")
    return payload


def step2_diagnose(groups):
    """步骤 2：健康度诊断（基线对照）。"""
    rows = []
    for g in groups:
        members = int(g.get("members") or 0)
        speakers = int(g.get("weekly_speakers") or 0)
        msgs = int(g.get("daily_msgs") or 0)
        ad = float(g.get("ad_ratio") or 0)
        speak_rate = speakers / members if members else 0
        notes = []
        if members > 400:
            notes.append("规模超 400，建议拆群分层")
        if speak_rate < 0.08:
            verdict = "沉默群"
            notes.append("先做问卷重启，再排常规活动")
        elif speak_rate < 0.15:
            verdict = "待激活"
            notes.append("发言率未达 15% 健康线，活动加密一档")
        else:
            verdict = "健康"
        if ad > 0.5:
            verdict = "劣化群"
            notes.append("广告占比 > 50%，先停硬广一周")
        elif ad > 0.3:
            notes.append("广告占比贴线，营销内容减量")
        rows.append({"name": g.get("name", ""), "members": members,
                     "speak_rate": speak_rate, "msgs": msgs, "ad": ad,
                     "verdict": verdict, "notes": "；".join(notes) or "指标正常"})
    print(f"[步骤2] 诊断完成：{[r['verdict'] for r in rows]}")
    return rows


def step3_match(industry, goal):
    """步骤 3：活动模板匹配（行业×目标；无匹配用通选模板）。"""
    key = (industry, goal)
    acts = ACTIVITY_LIBRARY.get(key)
    source = "行业×目标精确匹配"
    if not acts:
        acts, source = FALLBACK, "无精确匹配，使用行业通选模板"
    print(f"[步骤3] 活动匹配：{source}（{len(acts)} 个动作）")
    return acts, source


def step4_schedule(acts, diagnoses):
    """步骤 4：周排期 + 验收标准 + 频控检查。"""
    rows = []
    touch_count = 0
    for action, slot, acceptance in acts:
        if action.startswith(("D-3", "D-2", "D-1", "当天")):
            touch_count += 1
        for d in diagnoses:
            if d["verdict"] == "沉默群":
                acceptance += "（沉默群先问卷重启，本周不强制达标）"
            if d["verdict"] == "劣化群":
                acceptance += "（劣化群先停硬广，营销类动作暂缓）"
        rows.append({"动作": action, "时段": slot, "验收标准": acceptance})
    freq_note = f"会员日预热触达点位 {touch_count} 次；同一客户 7 天内活动触达 ≤ 2 次（1v1 定向仅高价值层）"
    print(f"[步骤4] 排期完成：{len(rows)} 个动作")
    return rows, freq_note


def build(payload, outdir):
    payload = step1_validate(payload)
    diagnoses = step2_diagnose(payload["groups"])
    acts, source = step3_match(payload["industry"], payload.get("week_goal") or "常规运营")
    schedule, freq_note = step4_schedule(acts, diagnoses)

    diag_rows = [{
        "群名": d["name"], "人数": d["members"],
        "7日发言率": f"{d['speak_rate']:.0%}", "日均消息": d["msgs"],
        "广告占比": f"{d['ad']:.0%}", "判定": d["verdict"], "诊断说明": d["notes"],
    } for d in diagnoses]

    summary = {
        "门店": payload.get("shop", "未提供"),
        "行业 / 本周目标": f"{payload['industry']} / {payload.get('week_goal', '常规运营')}",
        "活动匹配来源": source,
        "群况判定": {d["name"]: d["verdict"] for d in diagnoses},
        "人力": payload.get("staff", "未提供"),
        "健康度基线": "发言率 ≥15% / 广告 ≤30% / 72h首单 ≥20% / 月退群 ≤5% / 群规模 150-300",
        "频控": freq_note,
        "AI 标识": "AI 生成内容",
    }

    at.ensure_outdir(outdir)
    xlsx = at.write_excel(
        os.path.join(outdir, "社群活动排期.xlsx"),
        {
            "群况诊断": diag_rows,
            "周排期": schedule,
            "汇总": [{"项": k, "内容": str(v)} for k, v in summary.items()],
        },
        highlights={
            "群况诊断": {"判定": "contains:沉默"},
            "群况诊断": {"判定": "contains:劣化"},
        },
        widths={"周排期": {"动作": 40, "验收标准": 44}},
    )
    img = at.bar_chart(
        os.path.join(outdir, "群健康度.png"),
        [d["name"] for d in diagnoses],
        [round(d["speak_rate"] * 100, 1) for d in diagnoses],
        title="各群 7 日发言率（%）对照健康线 15%", ylabel="发言率 %",
    )
    docx = at.write_docx(
        os.path.join(outdir, "本周社群活动SOP.docx"),
        f"{summary['门店']} · 本周社群活动 SOP",
        [
            {"heading": "一、群况诊断",
             "paras": [f"行业：{payload['industry']}；本周目标：{payload.get('week_goal', '常规运营')}；人力：{payload.get('staff', '未提供')}"],
             "table": {"cols": list(diag_rows[0].keys()) if diag_rows else ["群名"],
                       "rows": [[r[c] for c in (list(diag_rows[0].keys()) if diag_rows else ["群名"])] for r in diag_rows]}},
            {"heading": "二、健康度基线与判定",
             "bullets": [f"{d['name']}：{d['verdict']} —— {d['notes']}" for d in diagnoses],
             "image": img},
            {"heading": "三、本周排期（活动模板：" + source + "）",
             "table": {"cols": ["动作", "时段", "验收标准"],
                       "rows": [[r["动作"], r["时段"], r["验收标准"]] for r in schedule]}},
            {"heading": "四、频控与合规",
             "bullets": [freq_note,
                         "迎新：入群 5 分钟内 @欢迎；禁屏时段 22:30-9:00 不发营销",
                         "禁止转发门槛裂变；老带新用双向奖励；投诉 30 分钟内响应不删评"]},
            {"heading": "五、人工确认点",
             "bullets": ["活动价格与会员专属价成本由店主确认",
                         "1v1 定向提醒名单由店长过目",
                         "战报数据以收银台账为准，公示脱敏"]},
        ],
        subtitle=f"生成时间 {at.stamp()} · AI 生成内容",
    )
    js = at.write_json({"summary": summary, "diagnosis": diag_rows, "schedule": schedule,
                        "generated_at": at.stamp(),
                        "note": "诊断与排期为规则计算；话术与物料文案由模型按社区 SOP 模板库生成"},
                       os.path.join(outdir, "activity_flow.json"))
    return {"files": [docx, xlsx, img, js], "summary": summary}


def main():
    ap = argparse.ArgumentParser(description="社群活动 SOP 流")
    ap.add_argument("--input", help="输入 JSON（shop/industry/week_goal/staff/groups）")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    payload = DEMO if a.demo else at.read_json(a.input) if a.input else ap.error("需要 --input / --demo 之一")
    r = build(payload, a.outdir)
    s = r["summary"]
    print(f"{s['门店']} —— 群况 {s['群况判定']}，目标「{s['行业 / 本周目标'].split(' / ')[1]}」")
    for f in r["files"]:
        print(" 产物:", f)
    at.emit(r)


if __name__ == "__main__":
    main()
