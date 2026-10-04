# 截图与录屏

> 以下素材均来自**真实执行**：`--run` 实拍终端 / 实跑产物文件，无摆拍。

## 演示视频

![演示视频](assets/demo.mp4)

*四幕流转叙事（Hyperframes 动态渲染 16s）：业务钩子 → 真实执行 → 数据管线节点动画 → 交付物*

## 执行截图

![真实执行](assets/run-terminal.png)



---

## 附录：实跑输出明细

> 本资产为纯提示词客户端资产，无界面可截图。以下为**实跑运行效果**。

## 运行效果

### 输入

```json
{
  "system": "企业微信",
  "task": "读取客户列表并发送通知"
}

```

### 输出

## 字段映射

| 业务字段 | 系统字段 | 方向 | 说明 |
|---|---|---|---|
| 客户昵称 | external_contact.name | 读 | 企微外部联系人昵称 |
| 客户头像 | external_contact.avatar | 读 | 外部联系人头像 URL |
| 客户类型 | external_contact.type | 读 | 1=微信用户，2=企业微信用户 |
| 添加时间 | follow_user.createtime | 读 | 员工添加该客户的时间戳 |
| 添加人 | follow_user.userid | 读 | 负责该客户的员工企微 ID |
| 标签列表 | follow_user.tags.tag_id | 读/写 | 客户标签，可用于分组发送 |
| 群发消息内容 | text.content | 写 | 通知文本内容 |
| 消息附件 | attachments | 写 | 图片/链接/小程序等附件 |
| 发送人 | sender | 写 | 指定发送员工 userid |
| 接收人 | external_userid | 写 | 目标客户 external_userid 列表 |

## 操作清单

1. **读取客户列表**：调用「获取客户列表」接口（GET /cgi-bin/externalcontact/list），传入员工 userid，获取 external_userid 列表。
2. **读取客户详情**：调用「获取客户详情」接口（GET /cgi-bin/externalcontact/get），传入 external_userid，获取昵称、头像、标签等字段。
3. **构建通知内容**：在业务系统内编辑文本 content 与附件 attachments。
4. **发送通知**：调用「发送企业群发消息」接口（POST /cgi-bin/externalcontact/add_msg_template），传入 sender、text、attachments 及 external_userid 列表。
5. **记录发送日志**：在业务数据库记录 msgid、发送时间、接收人数量，用于后续追踪。

## 能力边界

**本资产仅产出字段映射与操作清单，不能自动完成上述读写操作。** 实际执行需用户在企微开放平台申请相应接口权限，并在业务系统中通过官方 SDK 或连接器完成调用。

> AI 生成内容


---

*运行效果由实跑验证生成*
