from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from .ai import OpenAICompatibleClient
from .analysis import build_feedback
from .charts import render_overview, render_semantic_wordcloud
from .config import Settings
from .feishu import AppBotClient, BitableClient, WebhookClient
from .pipeline import process_ai_feedback
from .report import build_card
from .storage import ensure_tables
from .topic_analysis import analyze_topics


def run(output: str | None = None, send_report: bool = True) -> dict:
    settings = Settings.from_env()
    target_date = (datetime.now(settings.timezone) + timedelta(days=settings.date_offset_days)).date()
    client = BitableClient(settings.app_id, settings.app_secret, settings.app_token, settings.table_id)
    records = client.list_records()
    fields = {
        "feedback": settings.feedback_field,
        "user": settings.user_field,
        "time": settings.time_field,
        "os": settings.os_field,
        "status": settings.status_field,
    }
    feedback = build_feedback(records, target_date, settings.timezone, fields)
    history_feedback = []
    for record in records:
        values = record.get("fields", {})
        from .analysis import parse_timestamp, plain_text, Feedback
        timestamp = parse_timestamp(values.get(fields["time"]), settings.timezone)
        text = plain_text(values.get(fields["feedback"]))
        if not timestamp or not text:
            continue
        history_feedback.append(Feedback(
            record_id=record.get("record_id", ""),
            user=plain_text(values.get(fields["user"])) or "匿名用户",
            text=text,
            timestamp=timestamp,
            os=plain_text(values.get(fields["os"])) or "未知",
            status=plain_text(values.get(fields["status"])),
        ))
    if settings.ai_enabled:
        if not settings.ai_base_url or not settings.ai_api_key:
            raise ValueError("AI_ENABLED=true 时必须配置 AI_BASE_URL 和 AI_API_KEY")
        daily_table_id, issue_table_id = ensure_tables(client, settings.daily_table_id, settings.issue_table_id)
        ai = OpenAICompatibleClient(settings.ai_base_url, settings.ai_api_key, settings.ai_model, settings.ai_timeout)
        ai_results = process_ai_feedback(
            feedback,
            ai=ai,
            bitable=client,
            daily_table_id=daily_table_id,
            issue_table_id=issue_table_id,
            analysis_version=settings.ai_analysis_version,
            now=datetime.now(settings.timezone),
        )
        for item, analysis, _ in ai_results:
            item.kind = analysis.type if analysis.type in {"bug", "feature"} else "other"
            item.module = analysis.module
            item.keywords = analysis.keywords
            item.ai_title = analysis.title
    issues = client.list_records(table_id=issue_table_id) if settings.ai_enabled else []
    chart_dir = Path("output") / target_date.isoformat()
    overview_path = render_overview(feedback, chart_dir / "feedback-overview.png")
    compact_history_path = Path("output/historical/historical-topic-analysis-compact.json")
    if settings.ai_enabled and compact_history_path.exists():
        topic_data = json.loads(compact_history_path.read_text(encoding="utf-8"))
    else:
        topic_data = analyze_topics(
            ai,
            history_feedback,
            "historical",
            cache_name="historical-topic-analysis.json",
        ) if settings.ai_enabled else {"keywords": []}
    wordcloud_path = render_semantic_wordcloud(topic_data, chart_dir / "semantic-wordcloud.png")
    image_keys: dict[str, str] = {}
    bot_client = None
    if not settings.dry_run and settings.chat_id:
        bot_client = AppBotClient(settings.app_id, settings.app_secret, settings.chat_id)
        image_keys = {
            "overview": bot_client.upload_image(str(overview_path)),
            "wordcloud": bot_client.upload_image(str(wordcloud_path)),
        }
    card = build_card(target_date, feedback, issues, settings.top_n, image_keys)

    if output:
        Path(output).write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    if settings.dry_run or not send_report:
        print(json.dumps(card, ensure_ascii=False, indent=2))
    elif settings.chat_id:
        assert bot_client is not None
        bot_client.send_card(card)
        print(f"已发送 {target_date} 日报：{len(feedback)} 条反馈，{len(issues)} 个细表问题")
    else:
        WebhookClient(settings.webhook_url, settings.webhook_secret).send_card(card)
        print(f"已发送 {target_date} 日报：{len(feedback)} 条反馈，{len(issues)} 个细表问题")
    return card


def main() -> None:
    parser = argparse.ArgumentParser(description="飞书反馈日报机器人")
    parser.add_argument("--output", help="将生成的飞书卡片 JSON 写入文件")
    parser.add_argument("--no-send", action="store_true", help="执行分析和写表，但不发送群日报")
    args = parser.parse_args()
    run(args.output, send_report=not args.no_send)


if __name__ == "__main__":
    main()
