from __future__ import annotations

import json
from pathlib import Path

from feedback_bot.ai import OpenAICompatibleClient
from feedback_bot.config import Settings


PROMPT = """你是产品反馈术语标准化专家。请把输入的历史反馈关键词压缩成适合高密度词云的规范主题词。
规则：
1. 每个 compact_name 优先 2-6 个汉字，最长 8 个汉字；英文技术术语例外。
2. 必须保留原词的核心功能、对象或问题，不得改变含义。
3. 例：频繁掉线导致任务中断→任务掉线；指令审批后仍卡住→审批卡死；手机远程控制桌面端→手机远控；客户端频繁崩溃→客户端崩溃。
4. 不得输出单字、残词、泛化词。
5. 相同含义可压缩成相同规范词，后续会合并权重和证据。
只返回合法 JSON：{"mapping":[{"original":"","compact_name":""}]}"""


def main() -> None:
    source = Path("output/historical/historical-topic-analysis.json")
    data = json.loads(source.read_text(encoding="utf-8"))
    settings = Settings.from_env()
    ai = OpenAICompatibleClient(settings.ai_base_url, settings.ai_api_key, settings.ai_model, 180)
    names = [value["name"] for value in data.get("keywords", [])]
    result = ai._post("/chat/completions", {
        "model": ai.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": json.dumps(names, ensure_ascii=False)}],
    })
    mapping_data = ai._parse_json(result["choices"][0]["message"]["content"])
    mapping = {item["original"]: item["compact_name"] for item in mapping_data.get("mapping", [])}
    grouped = {}
    for keyword in data.get("keywords", []):
        compact = mapping.get(keyword["name"], keyword["name"])
        if len(compact) > 12 or len(compact) < 2:
            compact = keyword["name"][:8]
        key = (keyword["topic"], compact.lower())
        if key not in grouped:
            current = dict(keyword)
            current["raw_names"] = [keyword["name"]]
            current["name"] = compact
            grouped[key] = current
        else:
            current = grouped[key]
            current["raw_names"].append(keyword["name"])
            current["comment_ids"] = list(dict.fromkeys(current["comment_ids"] + keyword["comment_ids"]))
            current["document_count"] = len(current["comment_ids"])
            current["weight"] = min(1.0, max(current["weight"], keyword["weight"]) + 0.04)
            current["confidence"] = max(current["confidence"], keyword["confidence"])
    data["keywords"] = sorted(grouped.values(), key=lambda value: (value["weight"], value["document_count"]), reverse=True)
    data["sample_note"] = "历史全量反馈 · 规范短词 · 综合业务权重；颜色代表一级主题。"
    target = Path("output/historical/historical-topic-analysis-compact.json")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"COMPACT_KEYWORDS={len(data['keywords'])}")
    print(f"OUTPUT={target}")


if __name__ == "__main__": main()
