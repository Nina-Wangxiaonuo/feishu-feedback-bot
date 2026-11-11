from __future__ import annotations

import json
import sys

from feedback_bot.config import Settings
from feedback_bot.feishu import BitableClient
from feedback_bot.storage import DAILY_TABLE_NAME, ISSUE_TABLE_NAME


def main() -> int:
    settings = Settings.from_env()
    client = BitableClient(settings.app_id, settings.app_secret, settings.app_token, settings.table_id)
    result = {
        "ai": {
            "enabled": settings.ai_enabled,
            "base_url_set": bool(settings.ai_base_url),
            "api_key_set": bool(settings.ai_api_key),
            "model": settings.ai_model,
        },
        "feishu": {"source_readable": False, "tables": {}, "ready": False},
    }
    try:
        source_records = client.list_records(page_size=1)
        result["feishu"]["source_readable"] = True
        result["feishu"]["source_probe_count"] = len(source_records)
        tables = client.list_tables()
        result["feishu"]["tables"] = {table.get("name"): table.get("table_id") for table in tables}
        result["feishu"]["ready"] = DAILY_TABLE_NAME in result["feishu"]["tables"] and ISSUE_TABLE_NAME in result["feishu"]["tables"]
    except Exception as exc:
        result["feishu"]["error"] = str(exc)
    result["ready"] = all((
        result["ai"]["enabled"], result["ai"]["base_url_set"], result["ai"]["api_key_set"],
        result["feishu"]["source_readable"], result["feishu"]["ready"],
    ))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
