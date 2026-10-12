# 复购管家

> **让 80% 沉睡私域重新到店的"AI 店长助理"**

![复购管家 · 动态演示](docs/assets/hero.gif)

*▲ 真实执行录播（自动循环播放）· [▶ 观看完整版合集视频](docs/demo.mp4)*

*上方演示视频由 5 个代表资产的真实执行截图串联（优惠券策略测算 / 入群欢迎与打标 / 每日朋友圈文案 / 沉睡客户唤醒 / 社群活动 SOP），每张 4 秒，全部来自脚本实跑与 AI 实跑产物。*

[![Stage](https://img.shields.io/badge/stage-P0-orange)](https://github.com/bangwozuo)
[![Asset](https://img.shields.io/badge/asset-5%20skills%20%2B%205%20workflows-blueviolet)](#技能清单)
[![NoKey](https://img.shields.io/badge/API%20Key-not%20required-success)](#资产形态)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)

---

## 数字员工总览

| 字段 | 内容 |
|------|------|
| 名称 / 定位 | **复购管家** —— 让 80% 沉睡私域重新到店的"AI 店长助理" |
| 目标客群 | 本地生活商家：已沉淀微信私域但不会运营的门店（68% 运营能力断层，据 R4 调研） |
| 做什么 | 入群欢迎与打标、朋友圈/社群内容日更、优惠券测算与触达、沉睡客户唤醒、到店核销引导 |
| 不做什么 | 不自动加好友、不群发轰炸（防封号红线）、不承诺转化率、不碰非官方自动化工具 |
| KPI | 私域内容日更率 100%；沉睡客户唤醒到店率 ≥5%；社群月均活动 ≥4 次 |
| 旧名存档 | `私域复购管家` |

---

## 资产形态

**提示词为主 + 确定性脚本为辅**：

| 特性 | 说明 |
|------|------|
| ✅ 无需 API Key | 一个 Key 都不需要 |
| ✅ 提示词资产 | 4 个技能即拷即用，粘贴到任何 AI 工具 |
| ✅ 脚本资产 | 优惠券测算 + 5 条工作流带 `scripts/`，`--demo` 即可真实跑通，产物落盘 Excel/PNG/JSON |
| ✅ 平台无关 | Coze / WorkBuddy / Dify / Claude / ChatGPT 均可 |
| ✅ 用户自备算力 | 模型来自你自己的订阅 |

---

## 快速开始

```text
1. 打开 skills/wecom-customer-sync/prompt.txt
2. 全文复制
3. 粘贴到你常用的 AI 工具（Coze / WorkBuddy / Dify / Claude / ChatGPT）
4. 按 SKILL.md 的输入规格提供数据
```

脚本类资产一条命令跑通（无需密钥）：

```bash
python skills/coupon-strategy/scripts/coupon_calc.py --demo
python workflows/group-welcome-tag-flow/scripts/run_flow.py --demo
```

完整指引见 [使用手册](docs/04-usage.md)。

---

## 仓库结构

```text
local-retention-zh/
├── README.md / employee.md / package.yaml     # 入口与 12 字段定义卡
├── docs/demo.mp4                              # 5 资产真实执行演示视频
├── docs/01~07                                 # 员工级文档（架构/流程/场景/手册/示例/录像/测试）
├── skills/                                    # 5 个原子技能
│   └── <skill>/
│       ├── README.md  SKILL.md  prompt.txt  schema.json  examples/
│       ├── scripts/                           # 优惠券策略带测算脚本
│       └── docs/                              # 该技能自己的 10 项文档 + 截图
├── workflows/                                 # 5 条工作流（复合技能）
│   └── <workflow>/
│       ├── README.md  SKILL.md  prompt.txt  schema.json  examples/
│       ├── scripts/run_flow.py                # 端到端编排脚本（--demo 真实跑通）
│       └── docs/                              # 该工作流自己的 10 项文档 + 截图
├── knowledge/                                 # RAG wiki 知识库
├── connectors/                                # 连接器说明 + 合规红线
├── quality/                                   # 效果基线与追踪日志
└── tests/                                     # 资产校验测试（离线，无需密钥）
```

### 每个技能 / 工作流自带的 docs

| 文档 | 内容 |
|------|------|
| `README.md` | 资产速览（真实执行截图 + 能力规则表 + 流水线图） |
| `docs/01-usage-manual.md` | 安装使用手册 |
| `docs/02-architecture.md` | 业务架构图 |
| `docs/03-flow.md` | 流程图（Mermaid + 配图） |
| `docs/04-examples.md` | 使用示例 |
| `docs/05-media.md` | 截图和录屏（清单 + 分镜脚本） |
| `docs/06-scenarios.md` | 使用场景（适用 / 不适用） |
| `docs/07-audience.md` | 用户群体 |
| `docs/08-value.md` | 解决问题与价值 |
| `docs/09-test-report.md` | 测试报告 |
| `docs/assets/run-terminal.png` | 真实执行 / 实跑产物终端截图 |

---

## 交付物导航

| 文档 | 内容 |
|------|------|
| [业务架构](docs/01-architecture.md) | 四层架构 + 数据流 + 能力边界 |
| [工作流流程](docs/02-workflow.md) | 5 条工作流的 DAG 可视化 |
| [使用场景](docs/03-scenarios.md) | 3 个真实场景（含前后对比） |
| [使用手册](docs/04-usage.md) | 各平台导入指引 + 常见问题 |
| [示例库](docs/05-examples.md) | 5 组输入输出示例 |
| [录像脚本](docs/06-recording-script.md) | 7 镜头分镜 + 旁白稿 |
| [校验报告](docs/07-test-report.md) | 资产质量校验结果 |

---

## 技能清单（5 个）

| # | 技能 | 能力族 | 复杂度 | 提示词 | 文档 |
|---|------|--------|--------|--------|------|
| 1 | 企微客户对接 | 连接器数据读写 | `M` | [prompt.txt](skills/wecom-customer-sync/prompt.txt) | [docs](skills/wecom-customer-sync/docs/) |
| 2 | 朋友圈文案生成 | 文案撰写 | `S` | [prompt.txt](skills/moments-copy-generate/prompt.txt) | [docs](skills/moments-copy-generate/docs/) |
| 3 | 社群 SOP 模板库 | 流程与方案设计 | `S` | [prompt.txt](skills/community-sop-library/prompt.txt) | [docs](skills/community-sop-library/docs/) |
| 4 | 优惠券策略 | 测算与评估 | `S` | [prompt.txt](skills/coupon-strategy/prompt.txt) | [docs](skills/coupon-strategy/docs/) |
| 5 | 封号合规风控 | 合规校验 | `S` | [prompt.txt](skills/account-ban-risk-control/prompt.txt) | [docs](skills/account-ban-risk-control/docs/) |

## 工作流清单（5 条）

| # | 工作流 | 阶段 | 复杂度 | 触发 | 定义 | 文档 |
|---|--------|------|--------|------|------|------|
| 1 | 入群欢迎与打标 | `P0` | `M` | 事件（客户扫码入群） | [SKILL.md](workflows/group-welcome-tag-flow/SKILL.md) | [docs](workflows/group-welcome-tag-flow/docs/) |
| 2 | 每日朋友圈文案 | `P0` | `S` | 定时（每日 7:30 推送 3 条候选） | [SKILL.md](workflows/daily-moments-copy-flow/SKILL.md) | [docs](workflows/daily-moments-copy-flow/docs/) |
| 3 | 社群活动 SOP | `P0` | `S` | 定时（每周一推送本周 SOP） | [SKILL.md](workflows/community-activity-sop-flow/SKILL.md) | [docs](workflows/community-activity-sop-flow/docs/) |
| 4 | 沉睡客户唤醒 | `P1` | `M` | 定时（每周扫描） | [SKILL.md](workflows/dormant-customer-wake-flow/SKILL.md) | [docs](workflows/dormant-customer-wake-flow/docs/) |
| 5 | 到店核销引导 | `P1` | `M` | 事件（领券后 48h 未到店） | [SKILL.md](workflows/instore-redemption-guide-flow/SKILL.md) | [docs](workflows/instore-redemption-guide-flow/docs/) |

---

## 知识库与连接器

| 目录 | 说明 |
|------|------|
| [`knowledge/`](knowledge/README.md) | RAG wiki 知识库：填入业务信息可显著提升输出质量 |
| [`connectors/`](connectors/README.md) | 连接器说明：数据从哪来、怎么合规地来 |

---

## 资产校验

```bash
pip install -r requirements.txt
pytest tests/ -v
```

校验技能完整性、提示词结构、契约一致性、工作流 DAG、技能级与工作流级 docs 完整性、知识库 wiki 与连接器结构。
**不需要任何 API Key。**

---

## 合规声明

- ✅ 所有输出为 **AI 辅助生成**，交付前须人工审核
- ✅ 提示词内置**违禁词禁止清单**，符合《广告法》要求
- ✅ 遵循《人工智能生成合成内容标识办法》
- ✅ 连接器只走**官方 API** 或**用户导出数据**
- ✅ 所有对外发布动作**保留人工确认环节**

---

## 许可

[Apache-2.0](LICENSE) — 可自由使用、修改、商用

---

*由 bangwozuo 业务库自动生成 · 2026-09-29*

*本仓库遵循 [bangwozuo 数字员工资产规范](https://github.com/bangwozuo/digital-employee-spec) v3.0 ｜ [总入口](https://github.com/bangwozuo/digital-employees-hub-zh)*
