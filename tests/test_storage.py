import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from feedback_bot.ai import AIAnalysis
from feedback_bot.analysis import Feedback
from feedback_bot.storage import daily_record_fields


class StorageTests(unittest.TestCase):
    def test_daily_fields_include_primary_and_source_id(self):
        timezone = ZoneInfo("Asia/Shanghai")
        feedback = Feedback("rec_abcdef123456", "用户甲", "无法登录", datetime(2026, 11, 10, 9, tzinfo=timezone), "Windows")
        analysis = AIAnalysis(True, "bug", "网络登录", "登录失败", "无法登录桌面端", "登录", "成功", "失败", ["登录失败"], "S2", 0.9, "中")
        fields = daily_record_fields(feedback, analysis, "BUG-0001", "v1", datetime(2026, 11, 10, 10, tzinfo=timezone))
        self.assertEqual(fields["原始记录 ID"], feedback.record_id)
        self.assertTrue(fields["分析记录 ID"].startswith("FB-20261110-"))
        self.assertEqual(fields["聚合问题 ID"], "BUG-0001")


if __name__ == "__main__":
    unittest.main()
