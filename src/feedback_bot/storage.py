from __future__ import annotations

from datetime import datetime
from typing import Any

from .ai import AIAnalysis
from .analysis import Feedback
from .feishu import BitableClient


DAILY_TABLE_NAME = "AI-每日反馈粗表"
ISSUE_TABLE_NAME = "AI-问题聚合细表"

# 飞书字段类型：1 文本，2 数字，3 单选，5 日期，7 复选框
DAILY_FIELDS = [
    ("原始记录 ID", 1), ("反馈日期", 5), ("反馈时间", 5), ("反馈人员", 1), ("原始反馈", 1),
    ("操作系统", 1), ("有效反馈", 7), ("反馈类型", 1), ("所属模块", 1), ("规范标题", 1),
    ("问题摘要", 1), ("用户目标", 1), ("预期结果", 1), ("实际结果", 1), ("关键词", 1),
    ("严重程度", 1), ("AI 置信度", 2), ("信息完整度", 1), ("聚合问题 ID", 1),
    ("分析版本", 1), ("分析时间", 5),
]
ISSUE_FIELDS = [
    ("反馈日期", 5), ("反馈时间", 5), ("类型", 1), ("分类", 1), ("优先级", 1),
    ("规范标题", 1), ("问题描述", 1), ("反馈人员", 1), ("操作系统", 1), ("原始记录 ID", 1),
    ("AI 置信度", 2), ("分析时间", 5),
]


def ensure_tables(client: BitableClient, daily_table_id: str = "", issue_table_id: str = "") -> tuple[str, str]:
    tables = client.list_tables()
    by_name = {table.get("name"): table.get("table_id") for table in tables}
    daily_id = daily_table_id or by_name.get(DAILY_TABLE_NAME) or client.create_table(DAILY_TABLE_NAME).get("table_id")
    issue_id = issue_table_id or by_name.get(ISSUE_TABLE_NAME) or client.create_table(ISSUE_TABLE_NAME).get("table_id")
    if not daily_id or not issue_id:
        raise RuntimeError("无法创建或定位分析数据表")
    _ensure_primary_field(client, daily_id, "分析记录 ID")
    _ensure_primary_field(client, issue_id, "问题 ID")
    _ensure_fields(client, daily_id, DAILY_FIELDS)
    _ensure_fields(client, issue_id, ISSUE_FIELDS)
    return daily_id, issue_id


def _ensure_primary_field(client: BitableClient, table_id: str, expected_name: str) -> None:
    fields = client.list_fields(table_id)
    if any(field.get("field_name") == expected_name for field in fields):
        return
    primary = next((field for field in fields if field.get("is_primary")), None)
    if primary:
        client.update_field(table_id, primary["field_id"], expected_name, 1)


def _ensure_fields(client: BitableClient, table_id: str, specifications: list[tuple[str, int]]) -> None:
    existing = {field.get("field_name") for field in client.list_fields(table_id)}
    for name, field_type in specifications:
        if name not in existing:
            client.create_field(table_id, name, field_type)


def _timestamp(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def daily_record_fields(feedback: Feedback, analysis: AIAnalysis, issue_id: str, version: str, now: datetime) -> dict[str, Any]:
    return {
        "分析记录 ID": f"FB-{feedback.timestamp.strftime('%Y%m%d')}-{feedback.record_id[-6:]}",
        "原始记录 ID": feedback.record_id,
        "反馈日期": _timestamp(feedback.timestamp.replace(hour=0, minute=0, second=0, microsecond=0)),
        "反馈时间": _timestamp(feedback.timestamp),
        "反馈人员": feedback.user,
        "原始反馈": feedback.text,
        "操作系统": feedback.os,
        "有效反馈": analysis.is_valid_feedback,
        "反馈类型": analysis.type,
        "所属模块": analysis.module,
        "规范标题": analysis.title,
        "问题摘要": analysis.summary,
        "用户目标": analysis.user_goal or "",
        "预期结果": analysis.expected_behavior or "",
        "实际结果": analysis.actual_behavior or "",
        "关键词": "、".join(analysis.keywords),
        "严重程度": analysis.severity,
        "AI 置信度": analysis.confidence,
        "信息完整度": analysis.information_completeness,
        "聚合问题 ID": issue_id,
        "分析版本": version,
        "分析时间": _timestamp(now),
    }
