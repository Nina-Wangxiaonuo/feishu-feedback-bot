import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from feedback_bot.analysis import Feedback
from feedback_bot.topic_analysis import analyze_topics


class FakeAI:
    model = "test"
    def _post(self, path, payload):
        content = {"sample_note": "小样本", "keywords": [
            {"name": "移动端远程控制", "topic": "移动端体验", "weight": 0.9, "confidence": 0.95, "sentiment": "neutral", "comment_ids": ["r1"]},
            {"name": "程", "topic": "其他待确认", "weight": 0.8, "confidence": 0.9, "sentiment": "unknown", "comment_ids": ["r1"]},
            {"name": "无证据词", "topic": "其他待确认", "weight": 0.8, "confidence": 0.9, "sentiment": "unknown", "comment_ids": ["missing"]},
        ], "manual_review": []}
        return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}]}
    @staticmethod
    def _parse_json(content): return json.loads(content)


class TopicAnalysisTests(unittest.TestCase):
    def test_filters_fragments_and_untraceable_terms(self):
        item = Feedback("r1", "甲", "希望手机远程控制", datetime.now())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "topic.json"
            with patch("feedback_bot.topic_analysis.Path", return_value=path):
                result = analyze_topics(FakeAI(), [item], "2026-11-11")
        self.assertEqual([value["name"] for value in result["keywords"]], ["移动端远程控制"])


if __name__ == "__main__": unittest.main()
