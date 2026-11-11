import unittest
from datetime import date
from zoneinfo import ZoneInfo

from feedback_bot.analysis import build_feedback, classify, cluster_feedback, detect_module


class AnalysisTests(unittest.TestCase):
    def test_classify_and_module(self):
        self.assertEqual(classify("Windows 登录后直接白屏，无法进入"), "bug")
        self.assertEqual(classify("希望增加会话云端恢复功能"), "feature")
        self.assertEqual(classify("能不能加个记忆系统或者自定义提示词？"), "feature")
        self.assertEqual(classify("建议规划并实现手机端控制能力"), "feature")
        self.assertEqual(classify("授权卡片会卡住，第二个无法点击"), "bug")
        self.assertEqual(detect_module("希望会话可以云端恢复并保留上下文"), "会话记忆")

    def test_build_and_cluster(self):
        timezone = ZoneInfo("Asia/Shanghai")
        timestamps = [
            int(__import__("datetime").datetime(2026, 11, 9, 9, 0, tzinfo=timezone).timestamp() * 1000),
            int(__import__("datetime").datetime(2026, 11, 9, 10, 0, tzinfo=timezone).timestamp() * 1000),
            int(__import__("datetime").datetime(2026, 11, 9, 11, 0, tzinfo=timezone).timestamp() * 1000),
        ]
        records = [
            {"record_id": "1", "fields": {"反馈人员": [{"name": "甲"}], "功能描述": "Windows 启动后白屏，无法进入", "反馈时间": timestamps[0], "操作系统": "Windows", "处理状态": "未处理"}},
            {"record_id": "2", "fields": {"反馈人员": [{"name": "乙"}], "功能描述": "Windows 打开应用以后白屏，进不去", "反馈时间": timestamps[1], "操作系统": "Windows", "处理状态": "未处理"}},
            {"record_id": "3", "fields": {"反馈人员": [{"name": "丙"}], "功能描述": "希望支持会话云端恢复", "反馈时间": timestamps[2], "操作系统": "macOS", "处理状态": "未处理"}},
        ]
        fields = {"user": "反馈人员", "feedback": "功能描述", "time": "反馈时间", "os": "操作系统", "status": "处理状态"}
        items = build_feedback(records, date(2026, 11, 9), timezone, fields)
        self.assertEqual(len(items), 3)
        clusters = cluster_feedback(items, threshold=0.25)
        self.assertEqual(sum(len(cluster.items) for cluster in clusters), 3)
        self.assertTrue(any(cluster.kind == "feature" for cluster in clusters))


if __name__ == "__main__":
    unittest.main()
