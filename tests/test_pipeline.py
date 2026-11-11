import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from feedback_bot.ai import AIAnalysis
from feedback_bot.analysis import Feedback
from feedback_bot.pipeline import _category, _priority, issue_record_fields


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.feedback = Feedback("rec_abcdef123456", "用户甲", "反馈", datetime(2026, 11, 10, 10, tzinfo=ZoneInfo("Asia/Shanghai")), "Windows")

    def test_category_and_priority(self):
        bug = AIAnalysis(True, "bug", "任务执行", "任务执行中掉线并自动中断", "任务中途掉线并终止", None, None, None, ["任务掉线"], "S2", 0.9, "中")
        self.assertEqual(_category(bug), "稳定性")
        self.assertEqual(_priority(bug), "P1")
        feature = AIAnalysis(True, "feature", "平台兼容", "支持Ubuntu桌面端运行", "希望支持Ubuntu", None, None, None, ["Ubuntu支持"], "S4", 0.9, "中")
        self.assertEqual(_category(feature), "适配兼容")
        self.assertEqual(_priority(feature), "P2")

    def test_issue_record_has_single_date(self):
        analysis = AIAnalysis(True, "ux", "UI交互", "摘要开启后权限卡片未对齐", "卡片未随对话区域调整", None, None, None, ["卡片对齐"], "S4", 0.9, "高")
        fields = issue_record_fields(analysis, self.feedback, datetime.now(ZoneInfo("Asia/Shanghai")))
        self.assertIn("反馈日期", fields)
        self.assertIn("反馈时间", fields)
        self.assertNotIn("首次出现", fields)
        self.assertNotIn("最近出现", fields)


if __name__ == "__main__": unittest.main()
