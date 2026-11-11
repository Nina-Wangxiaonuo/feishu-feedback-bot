from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


def load_dotenv(path: str = ".env") -> None:
    file = Path(path)
    if not file.exists():
        return
    for raw_line in file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    app_id: str
    app_secret: str
    app_token: str
    table_id: str
    chat_id: str
    webhook_url: str
    webhook_secret: str | None
    timezone: ZoneInfo
    feedback_field: str
    user_field: str
    time_field: str
    os_field: str
    status_field: str
    unprocessed_value: str
    date_offset_days: int
    top_n: int
    dry_run: bool
    ai_enabled: bool
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    ai_timeout: int
    ai_analysis_version: str
    daily_table_id: str
    issue_table_id: str

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        required = {
            "FEISHU_APP_ID": os.getenv("FEISHU_APP_ID", ""),
            "FEISHU_APP_SECRET": os.getenv("FEISHU_APP_SECRET", ""),
            "FEISHU_APP_TOKEN": os.getenv("FEISHU_APP_TOKEN", ""),
            "FEISHU_TABLE_ID": os.getenv("FEISHU_TABLE_ID", ""),
        }
        dry_run = os.getenv("DRY_RUN", "false").lower() in {"1", "true", "yes"}
        chat_id = os.getenv("FEISHU_CHAT_ID", "")
        webhook = os.getenv("FEISHU_WEBHOOK_URL", "")
        if not dry_run and not (chat_id or webhook):
            required["FEISHU_CHAT_ID 或 FEISHU_WEBHOOK_URL"] = ""
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ValueError("缺少配置：" + ", ".join(missing))

        return cls(
            app_id=required["FEISHU_APP_ID"],
            app_secret=required["FEISHU_APP_SECRET"],
            app_token=required["FEISHU_APP_TOKEN"],
            table_id=required["FEISHU_TABLE_ID"],
            chat_id=chat_id,
            webhook_url=webhook,
            webhook_secret=os.getenv("FEISHU_WEBHOOK_SECRET") or None,
            timezone=ZoneInfo(os.getenv("TIMEZONE", "Asia/Shanghai")),
            feedback_field=os.getenv("FIELD_FEEDBACK", "功能描述"),
            user_field=os.getenv("FIELD_USER", "反馈人员"),
            time_field=os.getenv("FIELD_TIME", "反馈时间"),
            os_field=os.getenv("FIELD_OS", "操作系统"),
            status_field=os.getenv("FIELD_STATUS", "处理状态"),
            unprocessed_value=os.getenv("UNPROCESSED_VALUE", "未处理"),
            date_offset_days=int(os.getenv("DATE_OFFSET_DAYS", "-1")),
            top_n=int(os.getenv("TOP_N", "8")),
            dry_run=dry_run,
            ai_enabled=os.getenv("AI_ENABLED", "false").lower() in {"1", "true", "yes"},
            ai_base_url=os.getenv("AI_BASE_URL", "").rstrip("/"),
            ai_api_key=os.getenv("AI_API_KEY", ""),
            ai_model=os.getenv("AI_MODEL", "gpt-5.6-sol"),
            ai_timeout=int(os.getenv("AI_TIMEOUT", "90")),
            ai_analysis_version=os.getenv("AI_ANALYSIS_VERSION", "v1"),
            daily_table_id=os.getenv("FEISHU_DAILY_TABLE_ID", ""),
            issue_table_id=os.getenv("FEISHU_ISSUE_TABLE_ID", ""),
        )
