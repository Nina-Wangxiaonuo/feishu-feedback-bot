from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any

from .analysis import Feedback


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _short(value: Any, limit: int = 120) -> str:
    text = _text(value).replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "…"


CATEGORY_ORDER = ["稳定性", "性能", "UI/UX", "功能缺陷", "新功能需求", "适配兼容", "工程/底座能力", "运维&通知"]


def _classify_issue(fields: dict[str, Any]) -> str:
    text = " ".join(_text(fields.get(key)).lower() for key in ("规范标题", "问题描述", "所属模块", "关键词"))
    issue_type = _text(fields.get("类型")).lower()
    if any(word in text for word in ("ubuntu", "windows", "macos", "linux", "兼容", "系统支持", "适配")):
        return "适配兼容"
    if any(word in text for word in ("更新日志", "版本通知", "版本推送", "消息通知")):
        return "运维&通知"
    if any(word in text for word in ("远程", "持久化", "云端接管", "子agent", "子智能体", "流水线", "记忆系统", "上下文记忆")):
        return "工程/底座能力"
    if issue_type == "feature":
        return "新功能需求"
    if any(word in text for word in ("掉线", "任务中断", "卡死", "卡住", "崩溃", "阻塞", "异常中断", "无法启动")):
        return "稳定性"
    if any(word in text for word in ("卡顿", "延迟", "响应慢", "加载慢", "性能")):
        return "性能"
    if issue_type == "ux" or any(word in text for word in ("布局", "对齐", "显示", "交互", "弹窗", "卡片展示")):
        return "UI/UX"
    return "功能缺陷"


def _priority(fields: dict[str, Any]) -> str:
    severity = _text(fields.get("严重程度")).upper()
    count = int(float(fields.get("反馈次数") or 0))
    category = _classify_issue(fields)
    text = " ".join(_text(fields.get(key)) for key in ("规范标题", "问题描述"))
    if severity == "S1" or (category == "稳定性" and any(word in text for word in ("阻断", "无法使用", "任务中断", "卡死", "无法启动")) and count >= 2):
        return "P0"
    if severity == "S2" or count >= 2 or category in {"稳定性", "性能"}:
        return "P1"
    return "P2"


def _issue_rows(issues: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    if not issues:
        return [{"tag": "div", "text": {"tag": "lark_md", "content": "暂无相关问题"}}]
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(issues[:top_n], 1):
        fields = record.get("fields", {})
        summary = _short(fields.get("问题描述"), 120)
        priority = _priority(fields)
        category = _classify_issue(fields)
        emphasis = "**" if priority in {"P0", "P1"} else ""
        count = int(float(fields.get("反馈次数") or 0))
        same_class = f"【同类反馈{count}条】" if count > 1 else ""
        content = f"{emphasis}{priority}｜{category}｜{_text(fields.get('规范标题'))}{same_class}{emphasis}\n{summary}"
        rows.append({"tag": "div", "text": {"tag": "lark_md", "content": content}})
        if index < min(len(issues), top_n):
            rows.append({"tag": "hr"})
    return rows


def build_card(
    target_date: date,
    items: list[Feedback],
    issues: list[dict[str, Any]],
    top_n: int = 8,
    image_keys: dict[str, str] | None = None,
) -> dict[str, Any]:
    image_keys = image_keys or {}
    bugs = [record for record in issues if _text(record.get("fields", {}).get("类型")).lower() == "bug"]
    features = [record for record in issues if _text(record.get("fields", {}).get("类型")).lower() == "feature"]
    other = [record for record in issues if record not in bugs and record not in features]
    ordered_issues = sorted(issues, key=lambda record: ({"P0": 0, "P1": 1, "P2": 2}[_priority(record.get("fields", {}))], -int(float(record.get("fields", {}).get("反馈次数") or 0))))
    counts = Counter(item.kind for item in items)
    users = len({item.user for item in items})

    elements: list[dict[str, Any]] = [{
        "tag": "column_set",
        "flex_mode": "none",
        "columns": [
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**{len(items)}**\n反馈总量"}}]},
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**{users}**\n反馈用户"}}]},
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**{counts['bug']}**\nBug"}}]},
            {"tag": "column", "width": "weighted", "weight": 1, "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": f"**{counts['feature']}**\nFeature"}}]},
        ],
    }]
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**{target_date.isoformat()}｜共 {len(items)} 条｜{users} 位用户｜Bug {counts['bug']}｜Feature {counts['feature']}｜UX/其他 {len(items) - counts['bug'] - counts['feature']}**"},
    })
    if image_keys.get("overview"):
        elements.extend([
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": "**反馈分布**"}},
            {"tag": "img", "img_key": image_keys["overview"], "alt": {"tag": "plain_text", "content": "反馈类型与模块分布图"}, "mode": "fit_horizontal"},
        ])

    group_titles = {"P0": "一、P0 紧急", "P1": "二、P1 重点", "P2": "三、P2 规划"}
    for group in ("P0", "P1", "P2"):
        group_issues = [record for record in ordered_issues if _priority(record.get("fields", {})) == group]
        elements.extend([
            {"tag": "hr"},
            {"tag": "div", "text": {"tag": "lark_md", "content": f"**{group_titles[group]} · {len(group_issues)} 项**"}},
        ])
        elements.extend(_issue_rows(group_issues, top_n))
    if image_keys.get("wordcloud"):
        elements.extend([
            {"tag": "div", "text": {"tag": "lark_md", "content": "**高价值反馈主题**"}},
            {"tag": "img", "img_key": image_keys["wordcloud"], "alt": {"tag": "plain_text", "content": "语义归一后的反馈主题词云"}, "mode": "fit_horizontal"},
        ])

    elements.extend([
        {
            "tag": "action",
            "actions": [{
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看完整反馈细表"},
                "type": "primary",
                "url": "https://wvixbzgc0u7.feishu.cn/base/UVjDbQbaRas8LUsp9FocdTn2nBe?table=tblcLyoYZCL1fUY2&view=vew5VBvVXK",
            }],
        },
        {
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": f"细表更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}；按反馈日期查看每日新增问题。"}],
        },
    ])
    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "Step Code 每日反馈播报"},
            "subtitle": {"tag": "plain_text", "content": target_date.isoformat()},
        },
        "elements": elements,
    }
