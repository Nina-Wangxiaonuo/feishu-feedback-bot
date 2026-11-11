from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .ai import OpenAICompatibleClient
from .analysis import Feedback


@dataclass
class TopicKeyword:
    name: str
    topic: str
    weight: float
    confidence: float
    document_count: int
    sentiment: str
    comment_ids: list[str]


BATCH_PROMPT = """你是 Step Code 桌面端的资深用户研究与 NLP 分析专家。请根据提供的脱敏反馈，生成可用于主题分析和词云可视化的严格 JSON。
规则：
1. 每个关键词必须能回溯到 comment_ids，不得虚构。
2. 关键词必须是可独立理解的完整业务短语，优先输出完整功能、问题、需求、场景，推荐 2-12 个汉字；英文技术术语可例外。
3. 禁止单字、残缺词、用户名、日期、IP、URL、表情编码、泛化词。疑似残词不得进入 keywords。
4. 合并同义表达但不过度合并；保留否定和修饰关系。
5. 每个一级主题最多 10 个关键词，总关键词 10-25 个；低置信度词不输出。
6. 样本少于 30 条时 sample_note 必须说明小样本限制。
7. weight 综合评论覆盖率、主题代表性、需求强度、情绪强度和业务价值，取 0-1；不使用趋势数据。
8. topic 只能选：性能与稳定性、会话与记忆、权限与安全、Agent能力、移动端体验、代码与开发能力、产品易用性、其他待确认。
9. sentiment 只能选 positive/neutral/negative/mixed/unknown。
10. confidence >= 0.80 才能进入 keywords。
11. name 必须压缩成 2-8 个汉字的规范主题词，技术术语可稍长；例如“频繁掉线导致任务中断”压缩为“任务掉线”，“指令审批后仍卡住”压缩为“审批卡死”，“手机远程控制桌面端”压缩为“手机远控”。不得因压缩损失核心问题。
只返回合法 JSON：
{"sample_note":"","keywords":[{"name":"","topic":"","weight":0,"confidence":0,"document_count":0,"sentiment":"negative","comment_ids":[]}],"manual_review":[{"term":"","reason":"","comment_ids":[]}]}
"""


def _merge_topic_analyses(partials: list[dict[str, Any]], path: Path) -> dict[str, Any]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    reviews = []
    for partial in partials:
        reviews.extend(partial.get("manual_review", []))
        for keyword in partial.get("keywords", []):
            key = (keyword["topic"], keyword["name"].lower())
            if key not in grouped:
                grouped[key] = dict(keyword)
                continue
            current = grouped[key]
            current["comment_ids"] = list(dict.fromkeys(current["comment_ids"] + keyword["comment_ids"]))
            current["document_count"] = len(current["comment_ids"])
            current["weight"] = min(1.0, max(current["weight"], keyword["weight"]) + 0.03)
            current["confidence"] = max(current["confidence"], keyword["confidence"])
    keywords = sorted(grouped.values(), key=lambda value: (value["weight"], value["document_count"]), reverse=True)[:60]
    output = {
        "sample_note": "历史全量反馈语义分析；关键词由分批结果归并，权重综合覆盖率、主题代表性、需求与情绪强度。",
        "keywords": keywords,
        "manual_review": reviews,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def analyze_topics(ai: OpenAICompatibleClient, items: list[Feedback], target_date: str, cache_name: str = "topic-analysis.json") -> dict[str, Any]:
    path = Path("output") / target_date / cache_name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if len(items) > 35:
        chunks = [items[index:index + 15] for index in range(0, len(items), 15)]
        partials = [analyze_topics(ai, chunk, target_date, cache_name=f"chunk-{index}.json") for index, chunk in enumerate(chunks)]
        return _merge_topic_analyses(partials, path)
    feedbacks = [
        {"id": item.record_id, "time": item.timestamp.isoformat(), "text": item.text}
        for item in items
    ]
    result = ai._post("/chat/completions", {
        "model": ai.model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": BATCH_PROMPT},
            {"role": "user", "content": json.dumps({"product": "Step Code 桌面端", "comments": feedbacks}, ensure_ascii=False)},
        ],
    })
    data = ai._parse_json(result["choices"][0]["message"]["content"])
    valid_ids = {item.record_id for item in items}
    cleaned = []
    for raw in data.get("keywords", []):
        name = str(raw.get("name", "")).strip()
        confidence = float(raw.get("confidence", 0))
        comment_ids = [value for value in raw.get("comment_ids", []) if value in valid_ids]
        if not (2 <= len(name) <= 24) or confidence < 0.8 or not comment_ids:
            continue
        cleaned.append({
            "name": name,
            "topic": str(raw.get("topic") or "其他待确认"),
            "weight": max(0.0, min(1.0, float(raw.get("weight", 0)))),
            "confidence": confidence,
            "document_count": len(set(comment_ids)),
            "sentiment": str(raw.get("sentiment") or "unknown"),
            "comment_ids": list(dict.fromkeys(comment_ids)),
        })
    cleaned.sort(key=lambda value: (value["weight"], value["document_count"]), reverse=True)
    output = {
        "sample_note": str(data.get("sample_note") or ""),
        "keywords": cleaned[:60] if target_date == "historical" else cleaned[:25],
        "manual_review": data.get("manual_review", []),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return output
