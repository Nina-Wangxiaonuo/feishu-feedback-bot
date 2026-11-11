from __future__ import annotations

from datetime import datetime
from typing import Any

from .ai import AIAnalysis, OpenAICompatibleClient
from .analysis import Feedback
from .cache import analyze_with_cache, load_cache, save_cache
from .feishu import BitableClient
from .storage import daily_record_fields


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _category(analysis: AIAnalysis) -> str:
    text = f"{analysis.title} {analysis.summary} {analysis.module}".lower()
    if analysis.type == "feature":
        if any(word in text for word in ("ubuntu", "windows", "macos", "linux", "兼容", "适配")):
            return "适配兼容"
        if any(word in text for word in ("更新日志", "版本通知", "版本推送")):
            return "运维&通知"
        if any(word in text for word in ("远程", "持久化", "云端", "agent", "流水线", "记忆")):
            return "工程/底座能力"
        return "新功能需求"
    if any(word in text for word in ("掉线", "中断", "卡死", "卡住", "崩溃", "无法启动")):
        return "稳定性"
    if any(word in text for word in ("卡顿", "延迟", "响应慢", "加载慢")):
        return "性能"
    if analysis.type == "ux":
        return "UI/UX"
    return "功能缺陷"


def _priority(analysis: AIAnalysis) -> str:
    if analysis.severity == "S1":
        return "P0"
    if analysis.severity == "S2" or _category(analysis) in {"稳定性", "性能"}:
        return "P1"
    return "P2"


def issue_record_fields(analysis: AIAnalysis, feedback: Feedback, now: datetime) -> dict[str, Any]:
    timestamp = int(feedback.timestamp.timestamp() * 1000)
    return {
        "问题 ID": f"ITEM-{feedback.timestamp.strftime('%Y%m%d')}-{feedback.record_id[-6:]}",
        "反馈日期": int(feedback.timestamp.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000),
        "反馈时间": timestamp,
        "类型": analysis.type,
        "分类": _category(analysis),
        "优先级": _priority(analysis),
        "规范标题": analysis.title,
        "问题描述": analysis.summary,
        "反馈人员": feedback.user,
        "操作系统": feedback.os,
        "原始记录 ID": feedback.record_id,
        "AI 置信度": analysis.confidence,
        "分析时间": int(now.timestamp() * 1000),
    }


def process_ai_feedback(
    feedback_items: list[Feedback], *, ai: OpenAICompatibleClient, bitable: BitableClient,
    daily_table_id: str, issue_table_id: str, analysis_version: str, now: datetime,
) -> list[tuple[Feedback, AIAnalysis, str]]:
    existing_daily = bitable.list_records(table_id=daily_table_id)
    processed_ids = {_text(record.get("fields", {}).get("原始记录 ID")) for record in existing_daily}
    existing_issues = bitable.list_records(table_id=issue_table_id)
    issue_source_ids = {_text(record.get("fields", {}).get("原始记录 ID")) for record in existing_issues}
    target_date = feedback_items[0].timestamp.date() if feedback_items else None
    cache = load_cache(target_date) if target_date else {}
    results: list[tuple[Feedback, AIAnalysis, str]] = []

    for feedback in feedback_items:
        try:
            analysis = analyze_with_cache(feedback, ai, cache)
            if target_date:
                save_cache(target_date, cache)
        except Exception as exc:
            print(f"AI_ANALYSIS_ERROR record_id={feedback.record_id}: {exc}")
            continue
        item_id = f"ITEM-{feedback.timestamp.strftime('%Y%m%d')}-{feedback.record_id[-6:]}"
        if feedback.record_id not in issue_source_ids:
            bitable.create_record(issue_table_id, issue_record_fields(analysis, feedback, now))
            issue_source_ids.add(feedback.record_id)
        if feedback.record_id not in processed_ids:
            bitable.create_record(daily_table_id, daily_record_fields(feedback, analysis, item_id, analysis_version, now))
            processed_ids.add(feedback.record_id)
        results.append((feedback, analysis, item_id))
    return results
