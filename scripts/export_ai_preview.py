from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from feedback_bot.ai import OpenAICompatibleClient
from feedback_bot.analysis import build_feedback
from feedback_bot.config import Settings
from feedback_bot.feishu import BitableClient


def main() -> None:
    settings = Settings.from_env()
    target_date = (datetime.now(settings.timezone) + timedelta(days=settings.date_offset_days)).date()
    bitable = BitableClient(settings.app_id, settings.app_secret, settings.app_token, settings.table_id)
    items = build_feedback(
        bitable.list_records(), target_date, settings.timezone,
        {"feedback": settings.feedback_field, "user": settings.user_field, "time": settings.time_field, "os": settings.os_field, "status": settings.status_field},
    )
    ai = OpenAICompatibleClient(settings.ai_base_url, settings.ai_api_key, settings.ai_model, settings.ai_timeout)
    output = []
    for item in items:
        analysis = ai.analyze(item)
        output.append({
            "record_id": item.record_id,
            "user": item.user,
            "time": item.timestamp.isoformat(),
            "original": item.text,
            "analysis": analysis.__dict__,
        })
        print(f"AI_OK {item.record_id} {analysis.type} {analysis.title}")
    path = Path("output") / target_date.isoformat() / "ai-analysis-preview.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PREVIEW={path} count={len(output)}")


if __name__ == "__main__":
    main()
