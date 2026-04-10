from datetime import datetime, timedelta

from slopmeter.models import CacheTokens, DailyUsage
from slopmeter.render import (
    RenderSection,
    TextNode,
    build_heatmap_scene,
    resolve_text_draw_origin,
)


def test_resolve_text_draw_origin_uses_bbox_edges_for_end_alignment():
    node = TextNode(
        x=500,
        y=100,
        text="640M",
        fill="#000000",
        font_size=14,
        anchor="end",
    )

    draw_x, draw_y = resolve_text_draw_origin(
        node,
        scale=1.0,
        bbox=(4, 10, 104, 40),
    )

    assert draw_x == 396
    assert draw_y == 90


def test_resolve_text_draw_origin_uses_bbox_center_for_middle_alignment():
    node = TextNode(
        x=500,
        y=100,
        text="640M",
        fill="#000000",
        font_size=14,
        anchor="middle",
        baseline="middle",
    )

    draw_x, draw_y = resolve_text_draw_origin(
        node,
        scale=2.0,
        bbox=(4, 10, 104, 40),
    )

    assert draw_x == 946
    assert draw_y == 175


def _build_section(*, total_cost_label=None, pricing_model_name=None) -> RenderSection:
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily = [
        DailyUsage(
            date=now.date(),
            input=1000,
            output=234,
            cache=CacheTokens(),
            total=1234,
            breakdown=[],
        )
    ]
    return RenderSection(
        daily=daily,
        insights=None,
        title="Codex",
        colors={
            "light": ["#e0e7ff", "#a5b4fc", "#818cf8", "#4f46e5", "#312e81"],
            "dark": ["#1e1b4b", "#312e81", "#4338ca", "#818cf8", "#c7d2fe"],
        },
        total_cost_label=total_cost_label,
        pricing_model_name=pricing_model_name,
    )


def test_scene_includes_cost_line_when_label_set():
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    section = _build_section(total_cost_label="$10", pricing_model_name="gpt-5.4")

    scene = build_heatmap_scene(
        start_date=now - timedelta(days=14),
        end_date=now,
        sections=[section],
        color_mode="light",
    )

    cost_nodes = [
        node
        for node in scene.nodes
        if isinstance(node, TextNode)
        and "Estimated cost (priced as gpt-5.4): $10" in node.text
    ]
    assert len(cost_nodes) == 1


def test_scene_omits_cost_line_when_label_none():
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    section = _build_section(total_cost_label=None, pricing_model_name=None)

    scene = build_heatmap_scene(
        start_date=now - timedelta(days=14),
        end_date=now,
        sections=[section],
        color_mode="light",
    )

    assert not any(
        isinstance(node, TextNode) and "Estimated cost" in node.text for node in scene.nodes
    )


def test_cost_line_requires_both_label_and_model_name():
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    section = _build_section(total_cost_label="$10", pricing_model_name=None)

    scene = build_heatmap_scene(
        start_date=now - timedelta(days=14),
        end_date=now,
        sections=[section],
        color_mode="light",
    )

    assert not any(
        isinstance(node, TextNode) and "Estimated cost" in node.text for node in scene.nodes
    )
