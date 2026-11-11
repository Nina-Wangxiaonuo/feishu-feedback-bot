from __future__ import annotations

from collections import Counter
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFont

from .analysis import Feedback, keyword_ranking

W, H = 1200, 760
BG = "#F7F9FC"
INK = "#172033"
MUTED = "#667085"
GRID = "#E5EAF2"
BLUE = "#4F7DF3"
CYAN = "#51BCE1"
VIOLET = "#865BE8"
ORANGE = "#E58A3A"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc" if bold else "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=1 if bold and path.endswith(".ttc") else 0)
            except OSError:
                continue
    return ImageFont.load_default()


def _canvas(title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.text((64, 48), title, fill=INK, font=_font(36, True))
    draw.text((64, 100), subtitle, fill=MUTED, font=_font(22))
    return image, draw


def _save(image: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)
    return path


def render_overview(items: list[Feedback], path: Path) -> Path:
    counts = Counter(item.kind for item in items)
    modules = Counter(item.module for item in items)
    image, draw = _canvas("反馈结构概览", "按反馈类型与产品模块统计")

    total = max(1, len(items))
    labels = [("Bug", counts["bug"], BLUE), ("Feature", counts["feature"], CYAN), ("其他", counts["other"], VIOLET)]
    x0, y0, width, height = 70, 175, 480, 44
    cursor = x0
    for label, value, color in labels:
        segment = width * value / total
        if segment:
            draw.rounded_rectangle((cursor, y0, cursor + segment, y0 + height), radius=12, fill=color)
        cursor += segment
    draw.text((70, 245), f"共 {len(items)} 条", fill=INK, font=_font(42, True))
    legend_y = 330
    for index, (label, value, color) in enumerate(labels):
        y = legend_y + index * 72
        draw.rounded_rectangle((72, y + 9, 92, y + 29), radius=5, fill=color)
        draw.text((112, y), label, fill=INK, font=_font(25, True))
        draw.text((270, y), str(value), fill=color, font=_font(28, True))
        draw.text((340, y + 3), f"{value / total:.0%}", fill=MUTED, font=_font(22))

    draw.line((610, 170, 610, 690), fill=GRID, width=2)
    draw.text((665, 172), "模块 Top 6", fill=INK, font=_font(28, True))
    top = modules.most_common(6)
    maximum = max((value for _, value in top), default=1)
    for index, (name, value) in enumerate(top):
        y = 235 + index * 72
        draw.text((650, y), name, fill=INK, font=_font(23))
        draw.rounded_rectangle((825, y + 5, 1100, y + 30), radius=10, fill="#E9EEF8")
        draw.rounded_rectangle((825, y + 5, 825 + 275 * value / maximum, y + 30), radius=10, fill=BLUE)
        draw.text((1115, y - 1), str(value), fill=INK, font=_font(23, True))
    return _save(image, path)


def _overlaps(box: tuple[int, int, int, int], boxes: list[tuple[int, int, int, int]], padding: int = 12) -> bool:
    left, top, right, bottom = box
    return any(
        not (right + padding < other_left or left - padding > other_right or bottom + padding < other_top or top - padding > other_bottom)
        for other_left, other_top, other_right, other_bottom in boxes
    )


TOPIC_COLORS = {
    "性能与稳定性": "#D95F43",
    "会话与记忆": "#7357D9",
    "权限与安全": "#C68418",
    "Agent能力": "#3E6FD8",
    "移动端体验": "#268FA8",
    "代码与开发能力": "#4755B8",
    "产品易用性": "#52758A",
    "其他待确认": "#667085",
}


def render_semantic_wordcloud(analysis: dict, path: Path) -> Path:
    keywords = analysis.get("keywords", [])
    image = Image.new("RGB", (1600, 820), BG)
    draw = ImageDraw.Draw(image)
    draw.text((54, 28), "反馈主题词云", fill=INK, font=_font(34, True))
    draw.text((54, 76), "历史全量 · 规范短词 · 综合业务权重", fill=MUTED, font=_font(20))
    if not keywords:
        draw.text((70, 210), "暂无高置信度主题关键词", fill=MUTED, font=_font(28))
        return _save(image, path)
    weights = [float(value.get("weight", 0)) for value in keywords]
    maximum, minimum = max(weights), min(weights)
    placed: list[tuple[int, int, int, int]] = []
    canvas_w, canvas_h = image.size
    center_x, center_y = canvas_w // 2, 425
    limit = 60 if len(keywords) > 25 else 25
    for index, value in enumerate(keywords[:limit]):
        word = str(value.get("name", ""))
        weight = float(value.get("weight", 0))
        ratio = (weight - minimum) / max(0.001, maximum - minimum)
        size = int(17 + 64 * ratio)
        font = _font(size, bold=index < 8)
        bounds = draw.textbbox((0, 0), word, font=font)
        word_width, word_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        for step in range(1100):
            angle = step * 0.46
            radius = 1.55 * (step ** 0.73)
            x = int(center_x + radius * __import__("math").cos(angle) - word_width / 2)
            y = int(center_y + radius * 0.66 * __import__("math").sin(angle) - word_height / 2)
            box = (x, y, x + word_width, y + word_height)
            if x < 28 or y < 112 or box[2] > canvas_w - 28 or box[3] > canvas_h - 40 or _overlaps(box, placed, padding=2):
                continue
            color = TOPIC_COLORS.get(str(value.get("topic")), TOPIC_COLORS["其他待确认"])
            draw.text((x, y), word, fill=color, font=font)
            placed.append(box)
            break
    note = str(analysis.get("sample_note") or "")
    if note:
        draw.text((54, canvas_h - 32), note[:100], fill=MUTED, font=_font(16))
    return _save(image, path)


def render_wordcloud(items: list[Feedback], path: Path) -> Path:
    ranking = keyword_ranking(items, 28)
    image, draw = _canvas("反馈主题词云", "词语大小按独立用户数与反馈次数加权")
    if not ranking:
        draw.text((70, 210), "暂无有效关键词", fill=MUTED, font=_font(28))
        return _save(image, path)

    randomizer = random.Random(20261110)
    maximum = max(score for _, score in ranking)
    minimum = min(score for _, score in ranking)
    palette = ["#315FD5", "#4F7DF3", "#6D55D9", "#865BE8", "#398DB7", "#667085"]
    placed: list[tuple[int, int, int, int]] = []
    center_x, center_y = W // 2, 435

    for index, (word, score) in enumerate(ranking):
        ratio = (score - minimum) / max(1, maximum - minimum)
        size = int(25 + 56 * ratio)
        font = _font(size, bold=index < 8)
        bounds = draw.textbbox((0, 0), word, font=font)
        word_width, word_height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        success = False
        for step in range(900):
            angle = step * 0.48
            radius = 2.4 * (step ** 0.72)
            x = int(center_x + radius * __import__("math").cos(angle) - word_width / 2)
            y = int(center_y + radius * 0.58 * __import__("math").sin(angle) - word_height / 2)
            box = (x, y, x + word_width, y + word_height)
            if x < 55 or y < 155 or box[2] > W - 55 or box[3] > H - 45:
                continue
            if not _overlaps(box, placed):
                draw.text((x, y), word, fill=palette[(index + randomizer.randrange(3)) % len(palette)], font=font)
                placed.append(box)
                success = True
                break
        if not success:
            continue
    return _save(image, path)
