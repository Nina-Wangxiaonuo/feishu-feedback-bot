from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from .ai import AIAnalysis
from .analysis import Feedback


def cache_path(target_date: date) -> Path:
    return Path("output") / target_date.isoformat() / "ai-analysis-cache.json"


def load_cache(target_date: date) -> dict[str, AIAnalysis]:
    path = cache_path(target_date)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {record_id: AIAnalysis(**analysis) for record_id, analysis in data.items()}


def save_cache(target_date: date, values: dict[str, AIAnalysis]) -> Path:
    path = cache_path(target_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: asdict(value) for key, value in values.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def analyze_with_cache(feedback: Feedback, ai, cache: dict[str, AIAnalysis]) -> AIAnalysis:
    if feedback.record_id in cache:
        return cache[feedback.record_id]
    result = ai.analyze(feedback)
    cache[feedback.record_id] = result
    return result
