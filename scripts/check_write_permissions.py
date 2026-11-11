from __future__ import annotations

from feedback_bot.config import Settings
from feedback_bot.feishu import BitableClient
from feedback_bot.storage import DAILY_TABLE_NAME, ISSUE_TABLE_NAME


def main() -> None:
    settings = Settings.from_env()
    client = BitableClient(settings.app_id, settings.app_secret, settings.app_token, settings.table_id)
    tables = {table.get("name"): table.get("table_id") for table in client.list_tables()}
    for name in (DAILY_TABLE_NAME, ISSUE_TABLE_NAME):
        table_id = tables.get(name)
        if not table_id:
            print(f"{name}: MISSING")
            continue
        fields = client.list_fields(table_id)
        print(f"{name}: READ_OK table_id={table_id} fields={len(fields)}")
        primary = next((field for field in fields if field.get("is_primary")), None)
        try:
            client.update_field(table_id, primary["field_id"], primary["field_name"], int(primary.get("type") or 1))
            print(f"{name}: SCHEMA_WRITE_OK")
        except Exception as exc:
            print(f"{name}: SCHEMA_WRITE_DENIED {exc}")
        try:
            probe = client.create_record(table_id, {primary["field_name"]: "机器人写权限测试"})
            print(f"{name}: RECORD_WRITE_OK record_id={probe.get('record_id')}")
        except Exception as exc:
            print(f"{name}: RECORD_WRITE_DENIED {exc}")


if __name__ == "__main__":
    main()
