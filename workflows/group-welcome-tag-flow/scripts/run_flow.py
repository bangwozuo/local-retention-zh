# -*- coding: utf-8 -*-
"""
入群欢迎与打标流 —— 端到端编排脚本。

流程：数据校验 → 来源打标 → 欢迎与 72h 转化排期 → 汇总产物
      （迎新执行清单 Excel + 机器可读 JSON）

核心规则：
  - 新成员入群 5 分钟内 @欢迎 + 群公告引导（首单券入口）
  - 打标三件套：来源渠道标签 + 入群日期 + 偏好标签（问卷回收后补）
  - 72h 首单转化：入群 72h 内首单转化健康线 ≥ 20%
  - 频控：迎新期（D1-D3）对同一新客触达 ≤ 2 次（欢迎语 + 1 次首单钩子）

失败处理：
  - 必需字段缺失 → 退出码 2 列清单
  - 来源未知 → 打标「来源-待确认」，不许猜
  - 重复入群记录 → 去重标注

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

# 来源渠道 → 标签（真实门店获客渠道口径）
SOURCE_TAGS = {
    "到店扫码": "来源-到店扫码",
    "收银台立牌": "来源-到店扫码",
    "外卖包裹卡": "来源-外卖包裹卡",
    "老带新": "来源-老带新",
    "朋友圈广告": "来源-投放",
    "团购核销": "来源-团购",
}

DEMO = {
    "shop": "老王麻辣烫（社区店）",
    "today": "2026-09-30",
    "new_members": [
        {"name": "阿俊", "source": "到店扫码", "added_at": "2026-09-30 12:03", "group": "老王麻辣烫·街坊群"},
        {"name": "小鹿", "source": "外卖包裹卡", "added_at": "2026-09-30 12:41", "group": "老王麻辣烫·街坊群"},
        {"name": "老猫", "source": "老带新", "added_at": "2026-09-29 18:55", "group": "老王麻辣烫·街坊群",
         "inviter": "大军"},
        {"name": "Fiona", "source": " unknown", "added_at": "2026-09-29 20:10", "group": "老王麻辣烫·街坊群"},
        {"name": "阿俊", "source": "到店扫码", "added_at": "2026-09-30 12:03", "group": "老王麻辣烫·街坊群"},
    ],
}


def step1_validate(payload):
    missing = []
    if not payload.get("new_members"):
        missing.append("new_members（新入群成员列表）")
    if missing:
        print(f"[失败] 步骤1 数据校验未过，缺失：{'、'.join(missing)}。", file=sys.stderr)
        sys.exit(2)
    print("[步骤1] 数据校验通过")
    return str(payload.get("today") or at.stamp()[:10])


def step2_tag(members):
    """步骤 2：来源打标。来源未知 → 待确认，不许猜。"""
    seen, rows = set(), []
    for m in members:
        name = str(m.get("name", "")).strip()
        key = (name, str(m.get("added_at", "")))
        if not name or key in seen:
            continue
        seen.add(key)
        src = str(m.get("source", "")).strip()
        rows.append({**m, "name": name, "source": src,
                     "标签": SOURCE_TAGS.get(src, "来源-待确认")})
    unknown = sum(1 for r in rows if r["标签"] == "来源-待确认")
    print(f"[步骤2] 打标完成：{len(rows)} 人，其中 {unknown} 人来源待确认")
    return rows


def step3_schedule(rows, today):
    """步骤 3：欢迎与 72h 转化排期（迎新期触达 ≤ 2 次）。"""
    for r in rows:
        if r["标签"] == "来源-老带新" and r.get("inviter"):
            r["欢迎语要点"] = f"@{r['name']} 欢迎！{r['inviter']} 推荐的老友，双方的 15 元券已安排"
        elif r["标签"] == "来源-待确认":
            r["欢迎语要点"] = f"@{r['name']} 欢迎进群！怎么找到我们店的呀？（顺带确认来源）"
        else:
            r["欢迎语要点"] = f"@{r['name']} 欢迎进群！群公告里有 {r.get('group', '本店')} 首单券入口"
        # 频控：D1 欢迎语 1 条 + D2 首单钩子 1 次 = 2 次，D3 只观察不触达
        r["D1"] = "5 分钟内 @欢迎 + 公告引导（触达1/2）"
        r["D2"] = "未下单→1v1 首单钩子（触达2/2）"
        r["D3"] = "只观察：下单则打「已首单」；不下单不追发"
        r["72h转化观察"] = "健康线 ≥ 20%"
    print("[步骤3] 迎新排期完成（迎新期每人 ≤ 2 次触达）")
    return rows


def build(payload, outdir):
    today = step1_validate(payload)
    rows = step2_tag(payload["new_members"])
    rows = step3_schedule(rows, today)

    out_rows = [{
        "成员": r["name"],
        "来源": r["source"],
        "建议标签": r["标签"],
        "入群时间": r.get("added_at", ""),
        "所属群": r.get("group", ""),
        "邀请人": r.get("inviter", "-"),
        "欢迎语要点": r["欢迎语要点"],
        "D1": r["D1"],
        "D2": r["D2"],
        "D3": r["D3"],
    } for r in sorted(rows, key=lambda x: x.get("added_at", ""))]

    tag_counts = {}
    for r in rows:
        tag_counts[r["标签"]] = tag_counts.get(r["标签"], 0) + 1
    summary = {
        "门店": payload.get("shop", "未提供"),
        "快照日": today,
        "新成员数": len(out_rows),
        "标签分布": tag_counts,
        "待确认来源数": tag_counts.get("来源-待确认", 0),
        "迎新SOP": "入群 5 分钟内 @欢迎；D2 首单钩子；迎新期触达 ≤ 2 次",
        "72h首单转化健康线": "≥ 20%（入群 72h 内完成首单的人数占比）",
        "老带新机制": "双向奖励（邀请人与新客各得券），不设转发门槛",
        "AI 标识": "AI 生成内容",
    }

    at.ensure_outdir(outdir)
    xlsx = at.write_excel(
        os.path.join(outdir, "迎新打标执行清单.xlsx"),
        {
            "迎新清单": out_rows or [{"成员": "（今日无新成员）"}],
            "标签台账": [{"标签": k, "人数": v} for k, v in tag_counts.items()],
            "汇总": [{"项": k, "内容": str(v)} for k, v in summary.items()],
        },
        highlights={"迎新清单": {"建议标签": "contains:待确认"}},
        widths={"迎新清单": {"欢迎语要点": 40}},
    )
    js = at.write_json({"summary": summary, "items": out_rows,
                        "generated_at": at.stamp(),
                        "note": "打标与排期为规则计算；欢迎语成文由模型按 prompt 润色"},
                       os.path.join(outdir, "welcome_flow.json"))
    return {"files": [xlsx, js], "summary": summary}


def main():
    ap = argparse.ArgumentParser(description="入群欢迎与打标流")
    ap.add_argument("--input", help="输入 JSON（shop/today/new_members）")
    ap.add_argument("--outdir", default="out")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    payload = DEMO if a.demo else at.read_json(a.input) if a.input else ap.error("需要 --input / --demo 之一")
    r = build(payload, a.outdir)
    s = r["summary"]
    print(f"{s['门店']} —— 新成员 {s['新成员数']} 人，待确认来源 {s['待确认来源数']} 人")
    for f in r["files"]:
        print(" 产物:", f)
    at.emit(r)


if __name__ == "__main__":
    main()
