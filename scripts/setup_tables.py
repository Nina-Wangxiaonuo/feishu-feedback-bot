from __future__ import annotations

import json

from feedback_bot.config import Settings
from feedback_bot.feishu import BitableClient
from feedback_bot.storage import DAILY_TABLE_NAME, ISSUE_TABLE_NAME, ensure_tables


def main() -> None:
    settings = Settings.from_env()
    client = BitableClient(settings.app_id, settings.app_secret, settings.app_token, settings.table_id)
    tables = client.list_tables()
    names = {table.get("name") for table in tables}
    missing = [name for name in (DAILY_TABLE_NAME, ISSUE_TABLE_NAME) if name not in names]
    if missing:
        raise SystemExit(
            "当前 Base 缺少数据表：" + "、".join(missing) + "。请手动创建同名空表，或授予应用创建数据表权限后重试。"
        )
    daily_id, issue_id = ensure_tables(client, settings.daily_table_id, settings.issue_table_id)
    result = {
        "daily_table": {"name": DAILY_TABLE_NAME, "table_id": daily_id, "fields": len(client.list_fields(daily_id))},
        "issue_table": {"name": ISSUE_TABLE_NAME, "table_id": issue_id, "fields": len(client.list_fields(issue_id))},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
