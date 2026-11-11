# 飞书反馈日报机器人

每天全量读取现有飞书多维表格中的反馈，以**规则分类 + 关键词相似度聚类**完成基础分析，并向指定飞书群发送一张日报卡片。

第一版严格按照需求实现：

1. 拉取指定日期的全部反馈并形成内存粗表；
2. 生成反馈热词“文字词云”和权重榜；
3. 合并同类反馈，分别输出 Bug 与 Feature 精细聚类；
4. 仅向群内发送卡片，不修改原收集表；
5. 不使用大模型，不产生模型调用成本。

## 项目结构

```text
src/feedback_bot/
  config.py    环境配置
  feishu.py    飞书鉴权、多维表读取、Webhook 发卡片
  analysis.py  字段清洗、分类、关键词、聚类
  report.py    飞书日报卡片
  main.py      定时任务入口
```

## 一、飞书配置

### 1. 创建自建应用

在飞书开放平台创建企业自建应用，为应用开通并发布以下权限：

- `bitable:app:readonly`（查看多维表格）；
- `im:message:send_as_bot`（以应用机器人身份发消息）。

然后在现有 Base 中通过“协作者”或“高级权限”把该应用加入，并授予收集表读取权限。仅开 API 权限但没有 Base 数据权限时，接口仍会返回无权访问。

### 2. 将应用机器人加入目标群

当前默认使用企业自建应用机器人直接向群 `chat_id` 发送消息：

1. 在应用的“应用能力”中启用机器人；
2. 开通 `im:message:send_as_bot`（以应用身份发消息）权限；
3. 发布一个包含上述权限的新版本；
4. 将应用机器人加入日报接收群；
5. 将群 `chat_id` 填入 `FEISHU_CHAT_ID`。

也可以使用群自定义机器人 Webhook 作为备用方式；只有未配置 `FEISHU_CHAT_ID` 时，程序才会使用 `FEISHU_WEBHOOK_URL`。

### 3. 复制配置

```bash
cp .env.example .env
```

填入 `.env`。已有收集表的参数已经预填：

```text
FEISHU_APP_TOKEN=UVjDbQbaRas8LUsp9FocdTn2nBe
FEISHU_TABLE_ID=tblqJKetf1zkkSKU
```

密钥不要提交到 Git，也不要发送到聊天中。

截图识别出的默认字段为：

```text
反馈人员
功能描述
反馈时间
操作系统
处理状态
```

如实际字段有空格或改名，请同步调整 `.env`。字段名称必须完全一致。

## 二、本地运行

项目仅使用 Python 标准库，无需安装第三方依赖。

```bash
PYTHONPATH=src python3 -m feedback_bot.main
```

首次建议设置：

```text
DRY_RUN=true
DATE_OFFSET_DAYS=0
```

此时只在终端打印卡片 JSON，不向群里发送。确认正确后将 `DRY_RUN=false`。

也可以保存卡片 JSON：

```bash
PYTHONPATH=src python3 -m feedback_bot.main --output report-card.json
```

## 三、定时执行

机器人本身是一个一次性任务，推荐由服务器的定时器每天调用。比如每天 10:00 生成昨天日报：

```cron
0 10 * * * cd /path/to/feishu-feedback-bot && /usr/bin/env PYTHONPATH=src /usr/bin/python3 -m feedback_bot.main >> bot.log 2>&1
```

服务器时区应设为 `Asia/Shanghai`；程序内部也会按 `.env` 的 `TIMEZONE` 筛选反馈日期。

如果要生成当天实时汇总，将：

```text
DATE_OFFSET_DAYS=0
```

## 四、分类与聚类规则

- 包含“无法、失败、报错、崩溃、卡住、白屏”等异常表达时倾向归为 Bug；
- 包含“希望、建议、增加、支持、能否、自定义”等意愿表达时倾向归为 Feature；
- 依据工作区、终端、会话、模型、通知、UI、网络等关键词识别模块；
- 先限定相同反馈类型，再综合关键词交集、文本相似度和模块一致性聚类；
- 报告中同时展示反馈条数和独立用户数。

这是无需模型的 MVP，优势是便宜、稳定、可解释；不足是无法理解复杂语义。后续如果聚类误差明显，可以在不改飞书接入层的前提下替换 `analysis.py`。

## 五、AI 智能分析与同 Base 细表

开通飞书 `bitable:app` 权限，并在当前 Base 的协作者或高级权限中授予应用“可编辑/可管理”后，配置：

```dotenv
AI_ENABLED=true
AI_BASE_URL=https://mp.z01.normandyfunc.com/v1
AI_API_KEY="仅保存在本地的密钥"
AI_MODEL=gpt-5.6-sol
AI_TIMEOUT=90
AI_ANALYSIS_VERSION=v1
FEISHU_DAILY_TABLE_ID=
FEISHU_ISSUE_TABLE_ID=
```

首次运行会在当前 Base 自动创建：

- `AI-每日反馈粗表`：每条原始反馈对应一条 AI 结构化记录；
- `AI-问题聚合细表`：同类问题跨天持续合并，保存累计次数、影响用户、首次和最近出现时间。

如果 Base 的高级权限禁止应用创建数据表，请由 Base 管理员手动新建上述两张空表。表名必须完全一致，字段无需手工创建，程序会自动补齐。可以先运行配置检查：

```bash
PYTHONPATH=src python3 scripts/check_setup.py
```

输出中的 `ready: true` 表示 AI 配置、原表读取和两张目标表都已就绪。两张空表创建后，可单独初始化字段：

```bash
PYTHONPATH=src python3 scripts/setup_tables.py
```

该命令会检查表名、重命名主字段、补齐字段，并输出两个 table ID 和字段数量。

完整流程可按以下顺序验证：

```bash
# 1. 检查 AI、原表和目标表
PYTHONPATH=src python3 scripts/check_setup.py

# 2. 初始化两张分析表的字段
PYTHONPATH=src python3 scripts/setup_tables.py

# 3. 执行 AI 分析并写表，但不发送群日报
PYTHONPATH=src python3 -m feedback_bot.main --no-send

# 4. 检查粗表和细表记录后，再正式发送
PYTHONPATH=src python3 -m feedback_bot.main
```

AI 分析结果会按日期缓存在 `output/<日期>/ai-analysis-cache.json`。相同原始记录不会重复调用模型；写表失败后重试也会复用缓存。

程序以原始记录 ID 幂等去重，不会重复分析已写入粗表的反馈。合并置信度达到 0.85 时自动更新已有问题，否则创建新问题。

建议在飞书中为粗表建立“今日反馈、近 7 日、Bug、Feature、低置信度”视图，为细表建立“Bug 看板、Feature 看板、今日新增、S1/S2、待确认、处理中”视图。

## 六、测试

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## 常见问题

### 返回 403 或无权限

检查自建应用是否已发布、是否开通多维表只读权限，以及应用是否被加入对应 Base 的协作者。

### 日报显示 0 条

检查：

- `FIELD_TIME` 是否与表中字段完全一致；
- `DATE_OFFSET_DAYS` 是否正确；
- 飞书日期字段是否确实为日期类型；
- 服务器和 `TIMEZONE` 是否一致。

### Webhook 发送失败

检查 Webhook 是否属于目标群；如果机器人启用了签名校验，必须填写 `FEISHU_WEBHOOK_SECRET`。
