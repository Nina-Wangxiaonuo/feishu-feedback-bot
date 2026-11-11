from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any


BUG_PATTERNS = (
    "无法", "失败", "报错", "异常", "崩溃", "卡死", "卡住", "无响应", "进不去",
    "打不开", "没有反应", "丢失", "错误", "闪退", "白屏", "黑屏", "失效", "不生效",
    "重复弹", "一直转圈", "授权卡片", "没反应",
)
FEATURE_PATTERNS = (
    "希望", "建议", "增加", "添加", "能否", "能不能加", "可不可以", "可以加", "最好", "想要",
    "可考虑", "期待", "迁移", "导入", "自定义", "支持一下", "有没有", "规划并实现",
)
STOPWORDS = {
    "希望", "可以", "功能", "一个", "这个", "那个", "目前", "现在", "感觉", "还是", "进行",
    "一下", "直接", "需要", "建议", "支持", "问题", "反馈", "使用", "时候", "没有", "无法",
    "不能", "以及", "或者", "如果", "已经", "用户", "桌面端", "agent", "step", "coding",
    "一下这个", "建议将", "记录一下", "这两个点", "长期优化", "当前的位置", "任务结束后",
    "lark_emoji_glance_0", "multica", "ubuntu", "kimi", "explore",
}
SYNONYMS = {
    "卡死": "卡顿", "卡住": "卡顿", "无响应": "卡顿", "崩了": "崩溃", "闪退": "崩溃",
    "打不开": "无法打开", "进不去": "无法打开", "通知消息": "消息通知", "提醒": "消息通知",
    "win": "Windows", "windows": "Windows", "mac": "macOS", "osx": "macOS",
    "工作区": "工作区", "workspace": "工作区", "终端": "终端", "terminal": "终端",
    "会话": "会话", "session": "会话", "模型": "模型", "model": "模型",
}
MODULE_RULES = {
    "安装升级": ("安装", "升级", "更新", "版本"),
    "启动崩溃": ("启动", "闪退", "崩溃", "白屏", "黑屏", "打不开", "进不去"),
    "工作区": ("工作区", "workspace", "项目", "文件夹"),
    "终端命令": ("终端", "terminal", "命令", "shell"),
    "会话记忆": ("会话", "记忆", "上下文", "历史", "恢复"),
    "模型": ("模型", "model", "智能体", "agent"),
    "通知": ("通知", "提醒", "消息"),
    "界面体验": ("字体", "字号", "界面", "按钮", "拖拽", "布局", "快捷键"),
    "网络登录": ("登录", "网络", "代理", "连接", "超时"),
    "计费额度": ("计费", "额度", "credit", "价格", "定价", "plan"),
    "MCP与技能": ("mcp", "技能", "skill", "插件"),
    "权限审批": ("授权", "审批", "权限", "申请"),
    "远程控制": ("远程", "手机端", "接管", "控制"),
}
DOMAIN_TERMS = (
    "会话", "记忆", "上下文", "工作区", "终端", "命令执行", "MCP", "技能", "插件", "模型",
    "授权", "权限审批", "远程控制", "手机端", "持久化", "消息通知", "字体", "界面", "登录",
    "网络代理", "安装升级", "崩溃", "卡顿", "白屏", "任务规划", "子Agent", "云端会话",
    "远程", "控制", "持久化", "code",
)
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.+-]{1,20}")


@dataclass
class Feedback:
    record_id: str
    user: str
    text: str
    timestamp: datetime
    os: str = "未知"
    status: str = ""
    kind: str = "other"
    module: str = "其他"
    keywords: list[str] = field(default_factory=list)
    ai_title: str = ""


@dataclass
class Cluster:
    kind: str
    module: str
    title: str
    items: list[Feedback]
    keywords: list[str]

    @property
    def user_count(self) -> int:
        return len({item.user for item in self.items})


def plain_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("name") or item.get("value") or ""))
            else:
                parts.append(str(item))
        return " ".join(part for part in parts if part).strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("name") or value.get("value") or "").strip()
    return str(value).strip()


def parse_timestamp(value: Any, timezone) -> datetime | None:
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, timezone)
    text = plain_text(value)
    if not text:
        return None
    normalized = text.replace("/", "-").replace("T", " ").rstrip("Z")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized[:19], fmt).replace(tzinfo=timezone)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.astimezone(timezone) if parsed.tzinfo else parsed.replace(tzinfo=timezone)
    except ValueError:
        return None


def classify(text: str) -> str:
    lowered = text.lower()
    bug = sum(1 for marker in BUG_PATTERNS if marker.lower() in lowered)
    feature = sum(1 for marker in FEATURE_PATTERNS if marker.lower() in lowered)
    # 明确的需求句优先作为 Feature；“不能/需要”单独出现不足以证明已有能力故障。
    if feature and not any(marker.lower() in lowered for marker in ("报错", "崩溃", "卡死", "卡住", "白屏", "闪退")):
        return "feature"
    if bug:
        return "bug"
    return "other"


def detect_module(text: str) -> str:
    lowered = text.lower()
    scores = {
        module: sum(1 for keyword in keywords if keyword.lower() in lowered)
        for module, keywords in MODULE_RULES.items()
    }
    module, score = max(scores.items(), key=lambda item: item[1])
    return module if score else "其他"


def extract_keywords(text: str, limit: int = 6) -> list[str]:
    normalized = text.lower()
    candidates: Counter[str] = Counter()
    for term in DOMAIN_TERMS:
        if term.lower() in normalized:
            candidates[term] += 3
    for raw in TOKEN_RE.findall(normalized):
        token = SYNONYMS.get(raw, raw)
        if token in STOPWORDS or len(token) < 2 or token.isdigit() or token.startswith("lark_emoji_"):
            continue
        candidates[token] += 1
    for raw, canonical in SYNONYMS.items():
        if raw.lower() in normalized:
            candidates[canonical] += 2
    return [word for word, _ in candidates.most_common(limit)]


def build_feedback(
    records: list[dict[str, Any]], target_date: date, timezone, fields: dict[str, str]
) -> list[Feedback]:
    items: list[Feedback] = []
    for record in records:
        values = record.get("fields", {})
        timestamp = parse_timestamp(values.get(fields["time"]), timezone)
        text = plain_text(values.get(fields["feedback"]))
        if not timestamp or timestamp.date() != target_date or not text:
            continue
        item = Feedback(
            record_id=record.get("record_id", ""),
            user=plain_text(values.get(fields["user"])) or "匿名用户",
            text=text,
            timestamp=timestamp,
            os=plain_text(values.get(fields["os"])) or "未知",
            status=plain_text(values.get(fields["status"])),
        )
        item.kind = classify(text)
        item.module = detect_module(text)
        item.keywords = extract_keywords(text)
        items.append(item)
    return sorted(items, key=lambda item: item.timestamp)


def _similarity(left: Feedback, right: Feedback) -> float:
    left_words, right_words = set(left.keywords), set(right.keywords)
    union = left_words | right_words
    jaccard = len(left_words & right_words) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, left.text[:120], right.text[:120]).ratio()
    module_bonus = 0.18 if left.module == right.module else 0.0
    return jaccard * 0.62 + sequence * 0.20 + module_bonus


def cluster_feedback(items: list[Feedback], threshold: float = 0.42) -> list[Cluster]:
    groups: list[list[Feedback]] = []
    for item in [entry for entry in items if entry.kind in {"bug", "feature"}]:
        best_index, best_score = -1, 0.0
        for index, group in enumerate(groups):
            if group[0].kind != item.kind:
                continue
            score = max(_similarity(item, member) for member in group)
            if score > best_score:
                best_index, best_score = index, score
        if best_index >= 0 and best_score >= threshold:
            groups[best_index].append(item)
        else:
            groups.append([item])

    clusters: list[Cluster] = []
    for group in groups:
        keywords = [word for word, _ in Counter(word for item in group for word in item.keywords).most_common(5)]
        representative = max(group, key=lambda item: (len(set(item.keywords) & set(keywords)), -len(item.text)))
        title = representative.ai_title or representative.text.replace("\n", " ").strip()
        if len(title) > 30:
            title = title[:30] + "…"
        clusters.append(Cluster(group[0].kind, group[0].module, title, group, keywords))
    return sorted(clusters, key=lambda cluster: (len(cluster.items), cluster.user_count), reverse=True)


def keyword_ranking(items: list[Feedback], limit: int = 15) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    users: defaultdict[str, set[str]] = defaultdict(set)
    for item in items:
        for keyword in set(item.keywords):
            counts[keyword] += 1
            users[keyword].add(item.user)
    scores = {word: counts[word] + len(users[word]) * 2 for word in counts}
    return sorted(scores.items(), key=lambda pair: (pair[1], counts[pair[0]]), reverse=True)[:limit]
