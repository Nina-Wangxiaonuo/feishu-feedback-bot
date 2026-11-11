import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

from feedback_bot.ai import AIAnalysis
from feedback_bot.analysis import Feedback
from feedback_bot.cache import analyze_with_cache, load_cache, save_cache


class FakeAI:
    def __init__(self):
        self.calls = 0

    def analyze(self, feedback):
        self.calls += 1
        return AIAnalysis(True, "feature", "会话", "标题", "摘要", None, None, None, ["会话"], "S4", 0.9, "中")


class CacheTests(unittest.TestCase):
    def test_analysis_reuses_cache(self):
        feedback = Feedback("rec1", "甲", "反馈", datetime.now())
        ai = FakeAI()
        cache = {}
        first = analyze_with_cache(feedback, ai, cache)
        second = analyze_with_cache(feedback, ai, cache)
        self.assertIs(first, second)
        self.assertEqual(ai.calls, 1)

    def test_cache_round_trip(self):
        value = AIAnalysis(True, "bug", "权限", "标题", "摘要", None, None, None, ["授权"], "S2", 0.8, "中")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.json"
            with patch("feedback_bot.cache.cache_path", return_value=path):
                save_cache(date(2026, 11, 10), {"rec1": value})
                loaded = load_cache(date(2026, 11, 10))
        self.assertEqual(loaded["rec1"].title, "标题")


if __name__ == "__main__":
    unittest.main()
