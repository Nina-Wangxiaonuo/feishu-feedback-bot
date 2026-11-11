from __future__ import annotations

from datetime import datetime
from pathlib import Path

from feedback_bot.ai import OpenAICompatibleClient
from feedback_bot.analysis import Feedback, parse_timestamp, plain_text
from feedback_bot.charts import render_semantic_wordcloud
from feedback_bot.config import Settings
from feedback_bot.feishu import BitableClient
from feedback_bot.topic_analysis import analyze_topics


def main() -> None:
    settings = Settings.from_env()
    client = BitableClient(settings.app_id, settings.app_secret, settings.app_token, settings.table_id)
    records = client.list_records()
    fields = {"feedback": settings.feedback_field, "user": settings.user_field, "time": settings.time_field, "os": settings.os_field, "status": settings.status_field}
    items = []
    for record in records:
        values = record.get("fields", {})
        timestamp = parse_timestamp(values.get(fields["time"]), settings.timezone)
        text = plain_text(values.get(fields["feedback"]))
        if timestamp and text:
            items.append(Feedback(record.get("record_id", ""), plain_text(values.get(fields["user"])) or "匿名用户", text, timestamp, plain_text(values.get(fields["os"])) or "未知", plain_text(values.get(fields["status"]))))
    ai = OpenAICompatibleClient(settings.ai_base_url, settings.ai_api_key, settings.ai_model, settings.ai_timeout)
    analysis = analyze_topics(ai, items, "historical", cache_name="historical-topic-analysis.json")
    output = render_semantic_wordcloud(analysis, Path("output") / "historical" / "historical-semantic-wordcloud.png")
    print(f"HISTORICAL_FEEDBACKS={len(items)}")
    print(f"HISTORICAL_KEYWORDS={len(analysis.get('keywords', []))}")
    print(f"WORDCLOUD={output}")
    print(f"MANUAL_REVIEW={len(analysis.get('manual_review', []))}")


if __name__ == "__main__":
    main()
