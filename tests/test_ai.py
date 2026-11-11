import unittest

from feedback_bot.ai import OpenAICompatibleClient


class AIValidationTests(unittest.TestCase):
    def test_validate_analysis(self):
        result = OpenAICompatibleClient._validate({
            "is_valid_feedback": True,
            "type": "BUG",
            "module": "权限审批",
            "title": "连续授权时第二张卡片无法操作并且标题过长需要截断",
            "summary": "摘要",
            "keywords": ["连续授权", "授权卡片", "无法操作"],
            "severity": "s2",
            "confidence": 1.5,
            "information_completeness": "中",
        })
        self.assertEqual(result.type, "bug")
        self.assertEqual(result.severity, "S2")
        self.assertLessEqual(len(result.title), 24)
        self.assertEqual(result.confidence, 1.0)

    def test_parse_fenced_json(self):
        parsed = OpenAICompatibleClient._parse_json('```json\n{"decision":"create"}\n```')
        self.assertEqual(parsed["decision"], "create")


if __name__ == "__main__":
    unittest.main()
