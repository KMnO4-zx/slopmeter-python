from __future__ import annotations

import calendar
import html
import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from typing import Any
from xml.sax.saxutils import escape

from PIL import Image, ImageColor, ImageDraw, ImageFont

from .models import ColorMode, DailyUsage, Insights
from .utils import format_local_date


@dataclass
class HeatmapTheme:
    title: str
    colors: dict[ColorMode, list[str]]
    title_caption: str | None = None


@dataclass
class SurfacePalette:
    background: str
    text: str
    muted: str


@dataclass
class CalendarGrid:
    weeks: list[list[str | None]]
    month_labels: list[str | None]


@dataclass
class SectionLayout:
    scale: float
    type_scale: float
    width: int
    height: int
    content_width: int
    grid_top: int
    grid_width: int
    left_label_width: int
    cell_size: int
    gap: int
    right_padding: int
    content_inset: int
    day_label_inset: int
    header_caption_y: int
    header_value_y: int
    title_y: int
    month_label_y: int
    legend_y: int
    note_y: int
    footer_caption_y: int
    footer_value_y: int
    provider_title_font_size: int
    metric_caption_font_size: int
    metric_value_font_size: int
    small_font_size: int
    note_font_size: int
    cell_radius: int
    legend_label_gap: int
    legend_swatch_gap: int


@dataclass
class RenderSection:
    daily: list[DailyUsage]
    insights: Insights | None
    title: str
    colors: dict[ColorMode, list[str]]
    title_caption: str | None = None


@dataclass
class RectNode:
    x: float
    y: float
    width: float
    height: float
    fill: str
    rx: float = 0
    ry: float = 0


@dataclass
class TextNode:
    x: float
    y: float
    text: str
    fill: str
    font_size: int
    font_weight: int = 400
    anchor: str = "start"
    baseline: str = "hanging"


@dataclass
class Scene:
    width: int
    height: int
    background: str
    nodes: list[RectNode | TextNode] = field(default_factory=list)


HEATMAP_THEMES: dict[str, HeatmapTheme] = {
    "amp": HeatmapTheme(
        title="Amp",
        colors={
            "light": ["#ecfeff", "#a5f3fc", "#67e8f9", "#06b6d4", "#0e7490"],
            "dark": ["#083344", "#155e75", "#0891b2", "#22d3ee", "#a5f3fc"],
        },
    ),
    "claude": HeatmapTheme(
        title="Claude Code",
        colors={
            "light": ["#fff7ed", "#fed7aa", "#fdba74", "#f97316", "#c2410c"],
            "dark": ["#292524", "#9a3412", "#c2410c", "#f97316", "#fdba74"],
        },
    ),
    "codex": HeatmapTheme(
        title="Codex",
        colors={
            "light": ["#e0e7ff", "#a5b4fc", "#818cf8", "#4f46e5", "#312e81"],
            "dark": ["#1e1b4b", "#312e81", "#4338ca", "#818cf8", "#c7d2fe"],
        },
    ),
    "cursor": HeatmapTheme(
        title="Cursor",
        colors={
            "light": ["#fff7ed", "#fed7aa", "#fdba74", "#f97316", "#9a3412"],
            "dark": ["#431407", "#9a3412", "#c2410c", "#f97316", "#fdba74"],
        },
    ),
    "gemini": HeatmapTheme(
        title="Gemini CLI",
        colors={
            "light": ["#eff6ff", "#bfdbfe", "#93c5fd", "#3b82f6", "#1d4ed8"],
            "dark": ["#172554", "#1d4ed8", "#2563eb", "#60a5fa", "#bfdbfe"],
        },
    ),
    "opencode": HeatmapTheme(
        title="Open Code",
        colors={
            "light": ["#f5f5f5", "#d4d4d4", "#a3a3a3", "#525252", "#171717"],
            "dark": ["#262626", "#525252", "#737373", "#a3a3a3", "#fafafa"],
        },
    ),
    "pi": HeatmapTheme(
        title="Pi Coding Agent",
        colors={
            "light": ["#ecfdf5", "#a7f3d0", "#6ee7b7", "#10b981", "#047857"],
            "dark": ["#022c22", "#065f46", "#059669", "#34d399", "#a7f3d0"],
        },
    ),
    "all": HeatmapTheme(
        title="Amp / Claude Code / Codex / Cursor / Gemini CLI / Open Code / Pi Coding Agent",
        title_caption="Total usage from",
        colors={
            "light": ["#f0fdf4", "#bbf7d0", "#4ade80", "#16a34a", "#14532d"],
            "dark": ["#052e16", "#15803d", "#16a34a", "#4ade80", "#bbf7d0"],
        },
    ),
}

DAYS_OF_WEEK_MONDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FONT_FAMILY = "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
PROVIDER_TITLE_FONT_SIZE = 20
METRIC_CAPTION_FONT_SIZE = 9
METRIC_VALUE_FONT_SIZE = 14
CAPTION_VALUE_GAP = 4
HEATMAP_GAMMA = 0.7
PNG_RENDER_WIDTH = 4000
HTML_PAGE_MAX_WIDTH = 1120
HTML_PAGE_HORIZONTAL_PADDING = 20
HTML_PROVIDER_HORIZONTAL_PADDING = 18
TARGET_CONTENT_BREATHING_ROOM = 24
MAX_LAYOUT_SCALE = 1.32
SCALEABLE_WEEK_THRESHOLD = 40
TEXT_SCALE_FACTOR = 0.5

BASE_CELL_SIZE = 11
BASE_GAP = 2
BASE_LEFT_LABEL_WIDTH = 34
BASE_RIGHT_PADDING = 20
BASE_CONTENT_INSET = 8
BASE_DAY_LABEL_INSET = 6
BASE_MONTH_HEADER_HEIGHT = 20
BASE_TOP_PADDING_GAP = 20
BASE_MONTH_LABEL_OFFSET = 4
BASE_LEGEND_TOP_GAP = 28
BASE_LEGEND_LABEL_GAP = 28
BASE_LEGEND_SWATCH_GAP = 3
BASE_LEGEND_TEXT_OFFSET = 6
BASE_FOOTER_TOP_PADDING = 48
BASE_STATS_BOTTOM_PADDING = 12
BASE_NOTE_OFFSET = 14
BASE_NOTE_TEXT_OFFSET = 8
BASE_CELL_RADIUS = 3

SURFACE_PALETTES: dict[ColorMode, SurfacePalette] = {
    "light": SurfacePalette(background="#ffffff", text="#0f172a", muted="#737373"),
    "dark": SurfacePalette(background="#171717", text="#fafafa", muted="#a3a3a3"),
}

EMPTY_CELL_FILL: dict[ColorMode, str] = {
    "light": "#f5f5f5",
    "dark": "#262626",
}


def format_token_total(value: int) -> str:
    units = [
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    ]
    for size, suffix in units:
        if value >= size:
            scaled = value / size
            precision = 0 if scaled >= 100 else 1 if scaled >= 10 else 2
            compact = f"{scaled:.{precision}f}".rstrip("0").rstrip(".")
            return f"{compact}{suffix}"
    return f"{value:,}"


def truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return f"{value[: max(max_length - 3, 1)]}..."


def caption(value: str) -> str:
    return value.upper()


def get_all_days(start: date, end: date) -> list[str]:
    days: list[str] = []
    current = start
    while current <= end:
        days.append(format_local_date(current))
        current += timedelta(days=1)
    return days


def get_monday_based_weekday(date_iso: str) -> int:
    return (date.fromisoformat(date_iso).weekday()) % 7


def pad_to_week_start_monday(days: list[str]) -> list[str | None]:
    first_day = get_monday_based_weekday(days[0])
    return ([None] * first_day) + days


def chunk_by_week(days: list[str | None]) -> list[list[str | None]]:
    return [days[index : index + 7] for index in range(0, len(days), 7)]


def get_month_label(week: list[str | None]) -> str | None:
    last_day = next((day for day in reversed(week) if day), None)
    if not last_day:
        return None
    return calendar.month_abbr[date.fromisoformat(last_day).month]


def default_colour_map(value: int, max_value: int, color_count: int) -> int:
    if max_value <= 0 or value <= 0:
        return 0
    scaled = (value / max_value) ** HEATMAP_GAMMA
    index = int((scaled * (color_count - 1)) + 0.999999)
    return max(0, min(index, color_count - 1))


def format_short_date(date_iso: str) -> str:
    parsed = date.fromisoformat(date_iso)
    return f"{calendar.month_abbr[parsed.month]} {parsed.day}"


def get_target_content_width() -> int:
    return max(
        (
        HTML_PAGE_MAX_WIDTH
        - (HTML_PAGE_HORIZONTAL_PADDING * 2)
        - (HTML_PROVIDER_HORIZONTAL_PADDING * 2)
        - TARGET_CONTENT_BREATHING_ROOM
        ),
        BASE_LEFT_LABEL_WIDTH + BASE_CELL_SIZE,
    )


def get_layout_scale(week_count: int, target_content_width: int | None = None) -> float:
    if target_content_width is None or week_count < SCALEABLE_WEEK_THRESHOLD:
        return 1.0
    base_grid_width = week_count * BASE_CELL_SIZE + max(week_count - 1, 0) * BASE_GAP
    base_content_width = BASE_LEFT_LABEL_WIDTH + base_grid_width
    if base_content_width <= 0:
        return 1.0
    return max(1.0, min(target_content_width / base_content_width, MAX_LAYOUT_SCALE))


def get_scaled_content_width(week_count: int, scale: float) -> int:
    cell_size = scale_spacing(BASE_CELL_SIZE, scale)
    gap = scale_spacing(BASE_GAP, scale)
    left_label_width = scale_spacing(BASE_LEFT_LABEL_WIDTH, scale)
    grid_width = week_count * cell_size + max(week_count - 1, 0) * gap
    return left_label_width + grid_width


def resolve_layout_scale(week_count: int, target_content_width: int | None = None) -> float:
    scale = get_layout_scale(week_count, target_content_width)
    if target_content_width is None or scale <= 1.0:
        return scale
    while scale > 1.0 and get_scaled_content_width(week_count, scale) > target_content_width:
        scale = max(1.0, round(scale - 0.01, 4))
    return scale


def scale_spacing(value: int, scale: float) -> int:
    return max(1, round(value * scale))


def scale_type(value: int, type_scale: float) -> int:
    return max(8, round(value * type_scale))


def get_calendar_grid(start_date: datetime, end_date: datetime) -> CalendarGrid:
    all_days = get_all_days(start_date.date(), end_date.date())
    padded_days = pad_to_week_start_monday(all_days)
    weeks = chunk_by_week(padded_days)
    month_labels: list[str | None] = []
    for index, week in enumerate(weeks):
        label = get_month_label(week)
        prev_label = get_month_label(weeks[index - 1]) if index > 0 else None
        month_labels.append(label if label != prev_label else None)
    return CalendarGrid(weeks=weeks, month_labels=month_labels)


def get_section_layout(week_count: int, *, target_content_width: int | None = None) -> SectionLayout:
    scale = resolve_layout_scale(week_count, target_content_width)
    type_scale = 1 + ((scale - 1) * TEXT_SCALE_FACTOR)
    cell_size = scale_spacing(BASE_CELL_SIZE, scale)
    gap = scale_spacing(BASE_GAP, scale)
    left_label_width = scale_spacing(BASE_LEFT_LABEL_WIDTH, scale)
    right_padding = scale_spacing(BASE_RIGHT_PADDING, scale)
    content_inset = scale_spacing(BASE_CONTENT_INSET, scale)
    day_label_inset = scale_spacing(BASE_DAY_LABEL_INSET, scale)
    metric_caption_font_size = scale_type(METRIC_CAPTION_FONT_SIZE, type_scale)
    metric_value_font_size = scale_type(METRIC_VALUE_FONT_SIZE, type_scale)
    provider_title_font_size = scale_type(PROVIDER_TITLE_FONT_SIZE, type_scale)
    small_font_size = scale_type(10, type_scale)
    note_font_size = scale_type(10, type_scale)
    cell_radius = scale_spacing(BASE_CELL_RADIUS, scale)
    legend_label_gap = scale_spacing(BASE_LEGEND_LABEL_GAP, scale)
    legend_swatch_gap = scale_spacing(BASE_LEGEND_SWATCH_GAP, scale)
    header_caption_y = 0
    header_value_y = header_caption_y + metric_caption_font_size + scale_spacing(CAPTION_VALUE_GAP, type_scale)
    top_metric_height = header_value_y + metric_value_font_size
    top_padding = max(provider_title_font_size, top_metric_height) + scale_spacing(BASE_TOP_PADDING_GAP, scale)
    month_header_height = scale_spacing(BASE_MONTH_HEADER_HEIGHT, scale)
    title_y = 0
    month_label_y = top_padding + scale_spacing(BASE_MONTH_LABEL_OFFSET, scale)
    grid_top = top_padding + month_header_height
    grid_height = 7 * cell_size + 6 * gap
    grid_width = week_count * cell_size + max(week_count - 1, 0) * gap
    legend_y = grid_top + grid_height + scale_spacing(BASE_LEGEND_TOP_GAP, scale)
    legend_bottom_y = legend_y + cell_size
    footer_top_padding = scale_spacing(BASE_FOOTER_TOP_PADDING, scale)
    footer_caption_y = legend_bottom_y + footer_top_padding
    footer_value_y = footer_caption_y + metric_caption_font_size + scale_spacing(CAPTION_VALUE_GAP, type_scale)
    stats_bottom_padding = scale_spacing(BASE_STATS_BOTTOM_PADDING, scale)
    content_width = left_label_width + grid_width
    width = content_width + right_padding
    height = footer_value_y + metric_value_font_size + stats_bottom_padding
    return SectionLayout(
        scale=scale,
        type_scale=type_scale,
        width=width,
        height=height,
        content_width=content_width,
        grid_top=grid_top,
        grid_width=grid_width,
        left_label_width=left_label_width,
        cell_size=cell_size,
        gap=gap,
        right_padding=right_padding,
        content_inset=content_inset,
        day_label_inset=day_label_inset,
        header_caption_y=header_caption_y,
        header_value_y=header_value_y,
        title_y=title_y,
        month_label_y=month_label_y,
        legend_y=legend_y,
        note_y=legend_bottom_y + scale_spacing(BASE_NOTE_OFFSET, scale),
        footer_caption_y=footer_caption_y,
        footer_value_y=footer_value_y,
        provider_title_font_size=provider_title_font_size,
        metric_caption_font_size=metric_caption_font_size,
        metric_value_font_size=metric_value_font_size,
        small_font_size=small_font_size,
        note_font_size=note_font_size,
        cell_radius=cell_radius,
        legend_label_gap=legend_label_gap,
        legend_swatch_gap=legend_swatch_gap,
    )


def add_rect(scene: Scene, **kwargs: Any) -> None:
    scene.nodes.append(RectNode(**kwargs))


def add_text(scene: Scene, **kwargs: Any) -> None:
    scene.nodes.append(TextNode(**kwargs))


def get_header_columns(
    *,
    content_left: float,
    content_right: float,
    title_caption: str | None,
) -> tuple[float, float, float, float]:
    available_width = max(content_right - content_left, 0)
    title_column_ratio = 0.42 if title_caption else 0.24
    title_column_width = available_width * title_column_ratio
    metric_column_width = max((available_width - title_column_width) / 3, 0)
    metric_left = content_left + title_column_width
    return (
        content_left,
        metric_left + metric_column_width,
        metric_left + (metric_column_width * 2),
        content_right,
    )


def get_footer_columns(
    *,
    content_left: float,
    content_right: float,
) -> tuple[float, float, float, float]:
    available_width = max(content_right - content_left, 0)
    widths = (0.31, 0.31, 0.18, 0.20)
    first = content_left
    second = content_left + available_width * widths[0]
    third = content_left + available_width * (widths[0] + widths[1])
    fourth = content_left + available_width * (widths[0] + widths[1] + widths[2])
    return first, second, third, fourth


def draw_heatmap_section(
    scene: Scene,
    *,
    x: int,
    y: int,
    grid: CalendarGrid,
    layout: SectionLayout,
    daily: list[DailyUsage],
    insights: Insights | None,
    title: str,
    title_caption: str | None,
    colors: dict[ColorMode, list[str]],
    color_mode: ColorMode,
    palette: SurfacePalette,
) -> None:
    colors_for_mode = colors[color_mode]
    legend_colors = [EMPTY_CELL_FILL[color_mode], *colors_for_mode[1:]]
    value_by_date: dict[str, int] = {}
    right_edge = x + layout.content_width
    left_column_x = x + layout.content_inset
    (
        _,
        header_input_x,
        header_output_x,
        _,
    ) = get_header_columns(
        content_left=left_column_x,
        content_right=right_edge,
        title_caption=title_caption,
    )
    footer_left_x, footer_secondary_x, footer_third_x, footer_fourth_x = get_footer_columns(
        content_left=left_column_x,
        content_right=right_edge,
    )
    max_value = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    first_activity_only_date: str | None = None
    first_measured_date: str | None = None

    for row in daily:
        date_key = format_local_date(row.date)
        display_value = row.display_value or row.total
        value_by_date[date_key] = display_value
        max_value = max(max_value, display_value)
        if row.total <= 0 and display_value > 0:
            if first_activity_only_date is None or date_key < first_activity_only_date:
                first_activity_only_date = date_key
        elif row.total > 0 and (first_measured_date is None or date_key < first_measured_date):
            first_measured_date = date_key
        total_input_tokens += row.input
        total_output_tokens += row.output
        total_tokens += row.total

    longest_streak = insights.streaks.longest if insights else 0
    current_streak = insights.streaks.current if insights else 0

    if title_caption:
        add_text(
            scene,
            x=left_column_x,
            y=y + layout.header_caption_y,
            text=caption(title_caption),
            fill=palette.muted,
            font_size=layout.metric_caption_font_size,
            font_weight=600,
        )
        add_text(
            scene,
            x=left_column_x,
            y=y + layout.header_value_y,
            text=title,
            fill=palette.text,
            font_size=layout.metric_value_font_size,
            font_weight=600,
        )
    else:
        add_text(
            scene,
            x=left_column_x,
            y=y + layout.title_y,
            text=title,
            fill=palette.text,
            font_size=layout.provider_title_font_size,
            font_weight=600,
        )

    for item_x, label, value in (
        (header_input_x, "Input tokens", format_token_total(total_input_tokens)),
        (header_output_x, "Output tokens", format_token_total(total_output_tokens)),
        (right_edge, "Total tokens", format_token_total(total_tokens)),
    ):
        add_text(
            scene,
            x=item_x,
            y=y + layout.header_caption_y,
            text=caption(label),
            fill=palette.muted,
            font_size=layout.metric_caption_font_size,
            font_weight=600,
            anchor="end",
        )
        add_text(
            scene,
            x=item_x,
            y=y + layout.header_value_y,
            text=value,
            fill=palette.text,
            font_size=layout.metric_value_font_size,
            font_weight=600,
            anchor="end",
        )

    for index in range(7):
        day_y = y + layout.grid_top + index * (layout.cell_size + layout.gap) + layout.cell_size / 2
        day_label = DAYS_OF_WEEK_MONDAY[index] if index in (0, 6) else ""
        if day_label:
            add_text(
                scene,
                x=x + layout.left_label_width - layout.day_label_inset,
                y=day_y,
                text=day_label,
                fill=palette.muted,
                font_size=layout.small_font_size,
                anchor="end",
                baseline="middle",
            )

    for week_index, week in enumerate(grid.weeks):
        month_label = grid.month_labels[week_index]
        if month_label:
            month_x = x + layout.left_label_width + week_index * (layout.cell_size + layout.gap)
            add_text(
                scene,
                x=month_x,
                y=y + layout.month_label_y,
                text=month_label,
                fill=palette.muted,
                font_size=layout.small_font_size,
            )

        for day_index, day_value in enumerate(week):
            if not day_value:
                continue
            value = value_by_date.get(day_value, 0)
            color_index = default_colour_map(value, max_value, len(colors_for_mode))
            fill = EMPTY_CELL_FILL[color_mode] if value <= 0 else colors_for_mode[color_index]
            day_x = x + layout.left_label_width + week_index * (layout.cell_size + layout.gap)
            day_y = y + layout.grid_top + day_index * (layout.cell_size + layout.gap)
            add_rect(
                scene,
                x=day_x,
                y=day_y,
                width=layout.cell_size,
                height=layout.cell_size,
                rx=layout.cell_radius,
                ry=layout.cell_radius,
                fill=fill,
            )

    legend_start_x = x + layout.left_label_width
    legend_y = y + layout.legend_y
    add_text(
        scene,
        x=legend_start_x,
        y=legend_y + layout.small_font_size,
        text=caption("Less"),
        fill=palette.muted,
        font_size=layout.small_font_size,
        font_weight=600,
    )
    for index, legend_color in enumerate(legend_colors):
        legend_x = legend_start_x + layout.legend_label_gap + index * (
            layout.cell_size + layout.legend_swatch_gap
        )
        add_rect(
            scene,
            x=legend_x,
            y=legend_y,
            width=layout.cell_size,
            height=layout.cell_size,
            rx=layout.cell_radius,
            ry=layout.cell_radius,
            fill=legend_color,
        )
    add_text(
        scene,
        x=legend_start_x
        + layout.legend_label_gap
        + len(legend_colors) * (layout.cell_size + layout.legend_swatch_gap)
        + scale_spacing(BASE_LEGEND_TEXT_OFFSET, layout.scale),
        y=legend_y + layout.small_font_size,
        text=caption("More"),
        fill=palette.muted,
        font_size=layout.small_font_size,
        font_weight=600,
    )

    if first_activity_only_date and first_measured_date:
        note_x = x + (layout.content_width / 2)
        note_y = y + layout.grid_top + 7 * layout.cell_size + 6 * layout.gap + scale_spacing(
            BASE_NOTE_TEXT_OFFSET, layout.scale
        )
        add_text(
            scene,
            x=note_x,
            y=note_y,
            text=(
                "Claude started logging full token telemetry on "
                f"{format_short_date(first_measured_date)}; earlier activity may be undercounted."
            ),
            fill=palette.muted,
            font_size=layout.note_font_size,
            anchor="middle",
        )

    left_rows: list[tuple[str, Any]] = []
    if insights and insights.most_used_model:
        left_rows.append(("Most used model", insights.most_used_model))
    if insights and insights.recent_most_used_model:
        left_rows.append(("Recent use (last 30 days)", insights.recent_most_used_model))

    for index, (row_caption, row_data) in enumerate(left_rows):
        model_name = truncate_text(row_data.name, 20)
        model_x = footer_left_x if index == 0 else footer_secondary_x
        add_text(
            scene,
            x=model_x,
            y=y + layout.footer_caption_y,
            text=caption(row_caption),
            fill=palette.muted,
            font_size=layout.metric_caption_font_size,
            font_weight=600,
        )
        add_text(
            scene,
            x=model_x,
            y=y + layout.footer_value_y,
            text=f"{model_name} ({format_token_total(row_data.tokens.total)})",
            fill=palette.text,
            font_size=layout.metric_value_font_size,
            font_weight=600,
        )

    for item_x, label, value in (
        (footer_third_x, "Longest streak", f"{longest_streak:,} days"),
        (footer_fourth_x, "Current streak", f"{current_streak:,} days"),
    ):
        add_text(
            scene,
            x=item_x,
            y=y + layout.footer_caption_y,
            text=caption(label),
            fill=palette.muted,
            font_size=layout.metric_caption_font_size,
            font_weight=600,
        )
        add_text(
            scene,
            x=item_x,
            y=y + layout.footer_value_y,
            text=value,
            fill=palette.text,
            font_size=layout.metric_value_font_size,
            font_weight=600,
        )


def build_heatmap_scene(
    *,
    start_date: datetime,
    end_date: datetime,
    sections: list[RenderSection],
    color_mode: ColorMode,
) -> Scene:
    grid = get_calendar_grid(start_date, end_date)
    layout = get_section_layout(
        len(grid.weeks),
        target_content_width=get_target_content_width(),
    )
    palette = SURFACE_PALETTES[color_mode]
    horizontal_padding = 18
    top_padding = 30
    bottom_padding = 18
    section_gap = 40
    width = horizontal_padding * 2 + layout.width
    height = (
        top_padding
        + bottom_padding
        + len(sections) * layout.height
        + max(len(sections) - 1, 0) * section_gap
    )
    scene = Scene(width=width, height=height, background=palette.background)
    add_rect(scene, x=-2, y=-2, width=width + 4, height=height + 4, fill=palette.background)

    for index, section in enumerate(sections):
        section_y = top_padding + index * (layout.height + section_gap)
        draw_heatmap_section(
            scene,
            x=horizontal_padding,
            y=section_y,
            grid=grid,
            layout=layout,
            daily=section.daily,
            insights=section.insights,
            title=section.title,
            title_caption=section.title_caption,
            colors=section.colors,
            color_mode=color_mode,
            palette=palette,
        )

    return scene


def scene_to_svg(scene: Scene) -> str:
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{scene.width}" height="{scene.height}" '
        f'viewBox="0 0 {scene.width} {scene.height}">'
    ]
    for node in scene.nodes:
        if isinstance(node, RectNode):
            lines.append(
                f'<rect x="{node.x}" y="{node.y}" width="{node.width}" height="{node.height}" '
                f'rx="{node.rx}" ry="{node.ry}" fill="{escape(node.fill)}" />'
            )
            continue
        lines.append(
            "<text "
            f'x="{node.x}" y="{node.y}" fill="{escape(node.fill)}" '
            f'font-size="{node.font_size}" font-weight="{node.font_weight}" '
            f'font-family="{escape(FONT_FAMILY)}" text-anchor="{node.anchor}" '
            f'dominant-baseline="{node.baseline}">{escape(node.text)}</text>'
        )
    lines.append("</svg>")
    return "".join(lines)


@lru_cache(maxsize=128)
def load_font(size: int, bold: bool) -> ImageFont.ImageFont:
    candidates = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
        "LiberationSans-Bold.ttf" if bold else "LiberationSans-Regular.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_node(draw: ImageDraw.ImageDraw, node: TextNode, scale: float) -> None:
    font_size = max(8, round(node.font_size * scale))
    font = load_font(font_size, node.font_weight >= 600)
    width, height = measure_text(draw, node.text, font)
    draw_x = node.x * scale
    draw_y = node.y * scale

    if node.anchor == "end":
        draw_x -= width
    elif node.anchor == "middle":
        draw_x -= width / 2

    if node.baseline == "middle":
        draw_y -= height / 2

    draw.text((draw_x, draw_y), node.text, fill=node.fill, font=font)


def scene_to_png(scene: Scene) -> bytes:
    scale = PNG_RENDER_WIDTH / scene.width
    image = Image.new(
        "RGBA",
        (round(scene.width * scale), round(scene.height * scale)),
        ImageColor.getrgb(scene.background),
    )
    draw = ImageDraw.Draw(image)
    for node in scene.nodes:
        if isinstance(node, RectNode):
            draw.rounded_rectangle(
                (
                    node.x * scale,
                    node.y * scale,
                    (node.x + node.width) * scale,
                    (node.y + node.height) * scale,
                ),
                radius=node.rx * scale,
                fill=ImageColor.getrgb(node.fill),
            )
        else:
            draw_text_node(draw, node, scale)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def render_usage_heatmaps_svg(
    *,
    start_date: datetime,
    end_date: datetime,
    sections: list[RenderSection],
    color_mode: ColorMode,
) -> str:
    scene = build_heatmap_scene(
        start_date=start_date,
        end_date=end_date,
        sections=sections,
        color_mode=color_mode,
    )
    return scene_to_svg(scene)


def render_usage_heatmaps_png(
    *,
    start_date: datetime,
    end_date: datetime,
    sections: list[RenderSection],
    color_mode: ColorMode,
) -> bytes:
    scene = build_heatmap_scene(
        start_date=start_date,
        end_date=end_date,
        sections=sections,
        color_mode=color_mode,
    )
    return scene_to_png(scene)


def render_html_document(payload: dict[str, Any]) -> str:
    embedded = json.dumps(payload, separators=(",", ":"))
    title = "slopmeter"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>{html.escape(title)}</title>
    <style>
      :root {{
        color-scheme: {'dark' if payload.get('colorMode') == 'dark' else 'light'};
        --bg: {'#171717' if payload.get('colorMode') == 'dark' else '#ffffff'};
        --text: {'#fafafa' if payload.get('colorMode') == 'dark' else '#0f172a'};
        --muted: {'#a3a3a3' if payload.get('colorMode') == 'dark' else '#737373'};
        --empty: {'#262626' if payload.get('colorMode') == 'dark' else '#f5f5f5'};
        --surface: {'#202020' if payload.get('colorMode') == 'dark' else '#fafafa'};
        --tooltip-bg: {'rgba(23,23,23,0.98)' if payload.get('colorMode') == 'dark' else 'rgba(15,23,42,0.97)'};
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
        background: var(--bg);
        color: var(--text);
      }}
      .page {{
        max-width: 1120px;
        margin: 0 auto;
        padding: 32px 20px 48px;
      }}
      .page-header {{
        margin-bottom: 24px;
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 16px;
        flex-wrap: wrap;
      }}
      .page-actions {{
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 10px;
      }}
      .range {{
        color: var(--muted);
        font-size: 13px;
      }}
      .toolbar {{
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }}
      .toolbar-button {{
        border: 0;
        border-radius: 999px;
        padding: 10px 16px;
        background: var(--text);
        color: var(--bg);
        font-size: 13px;
        font-weight: 700;
        cursor: pointer;
      }}
      .toolbar-button[disabled] {{
        opacity: 0.45;
        cursor: not-allowed;
      }}
      .toolbar-hint {{
        color: var(--muted);
        font-size: 13px;
        text-align: right;
        min-height: 20px;
      }}
      .toolbar-hint.is-error {{
        color: #dc2626;
      }}
      body.is-sorting-providers {{
        user-select: none;
      }}
      .provider {{
        background: var(--surface);
        border-radius: 18px;
        padding: 20px 16px 20px;
        margin-bottom: 24px;
        border: 1px solid rgba(127,127,127,0.12);
        transition: opacity 120ms ease, border-color 120ms ease, box-shadow 120ms ease, transform 160ms ease;
        will-change: transform;
      }}
      .provider[data-export-selected="false"] {{
        opacity: 0.72;
      }}
      .provider.is-pointer-dragging {{
        position: fixed;
        z-index: 40;
        margin: 0;
        opacity: 0.98;
        pointer-events: none;
        box-shadow: 0 28px 80px rgba(15,23,42,0.18);
        transform: scale(1.01);
        transform-origin: center top;
      }}
      .provider-placeholder {{
        height: 0;
        margin-bottom: 24px;
        border-radius: 18px;
        border: 1px dashed rgba(127,127,127,0.2);
        background: rgba(127,127,127,0.04);
      }}
      .provider-topline {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 14px;
        flex-wrap: wrap;
      }}
      .provider-badge {{
        color: var(--muted);
        text-transform: uppercase;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
      }}
      .provider-controls {{
        display: flex;
        align-items: center;
        gap: 12px;
        flex-wrap: wrap;
      }}
      .provider-toggle {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        color: var(--text);
        font-size: 13px;
        font-weight: 600;
        cursor: pointer;
      }}
      .provider-toggle input {{
        margin: 0;
      }}
      .drag-handle {{
        border: 1px solid rgba(127,127,127,0.22);
        border-radius: 999px;
        padding: 8px 12px;
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        cursor: grab;
        touch-action: none;
        user-select: none;
      }}
      .drag-handle:active {{
        cursor: grabbing;
      }}
      .provider-header {{
        display: grid;
        grid-template-columns: minmax(0, 1.12fr) repeat(3, minmax(0, 0.88fr));
        column-gap: calc(24px * var(--layout-scale, 1));
        align-items: flex-start;
        margin-bottom: calc(16px * var(--layout-scale, 1));
      }}
      .provider-header.is-aggregate {{
        grid-template-columns: minmax(0, 1.42fr) repeat(3, minmax(0, 0.74fr));
      }}
      .provider-shell-wrap {{
        overflow-x: auto;
        padding-bottom: 6px;
      }}
      .provider-shell {{
        width: var(--shell-width);
        min-width: var(--shell-width);
      }}
      .provider-heading {{
        min-width: 0;
      }}
      .provider-title {{
        font-size: var(--provider-title-font, 22px);
        font-weight: 700;
        line-height: 1.2;
      }}
      .provider-title.is-aggregate-title {{
        font-size: var(--aggregate-title-font, 16px);
        line-height: 1.08;
        letter-spacing: -0.02em;
        white-space: nowrap;
      }}
      .provider-caption {{
        color: var(--muted);
        text-transform: uppercase;
        font-size: var(--metric-label-font, 11px);
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-bottom: calc(4px * var(--type-scale, 1));
      }}
      .metrics {{
        display: contents;
      }}
      .metric {{
        text-align: right;
        min-width: 0;
      }}
      .metric-label {{
        color: var(--muted);
        text-transform: uppercase;
        font-size: var(--metric-label-font, 11px);
        font-weight: 700;
        letter-spacing: 0.08em;
      }}
      .metric-value {{
        font-size: var(--metric-value-font, 16px);
        font-weight: 700;
        margin-top: calc(4px * var(--type-scale, 1));
      }}
      .calendar-wrap {{
        padding-bottom: 6px;
      }}
      .calendar {{
        display: grid;
        gap: var(--cell-gap, 2px);
        width: var(--calendar-width);
        min-width: var(--calendar-width);
        align-items: center;
      }}
      .month-label {{
        color: var(--muted);
        font-size: var(--small-font, 11px);
      }}
      .day-label {{
        color: var(--muted);
        font-size: var(--small-font, 11px);
        justify-self: end;
        padding-right: calc(6px * var(--layout-scale, 1));
      }}
      .cell {{
        width: var(--cell-size, 11px);
        height: var(--cell-size, 11px);
        border: 0;
        border-radius: calc(3px * var(--layout-scale, 1));
        padding: 0;
        cursor: default;
      }}
      .legend {{
        margin-top: calc(12px * var(--layout-scale, 1));
        display: flex;
        align-items: center;
        gap: calc(8px * var(--layout-scale, 1));
        color: var(--muted);
        text-transform: uppercase;
        font-size: var(--metric-label-font, 11px);
        font-weight: 700;
        letter-spacing: 0.08em;
      }}
      .legend-swatch {{
        width: var(--cell-size, 11px);
        height: var(--cell-size, 11px);
        border-radius: calc(3px * var(--layout-scale, 1));
      }}
      .footer {{
        display: grid;
        grid-template-columns: minmax(0, 1.25fr) minmax(0, 1.25fr) minmax(0, 0.72fr) minmax(0, 0.78fr);
        gap: calc(16px * var(--layout-scale, 1));
        margin-top: calc(16px * var(--layout-scale, 1));
      }}
      .footer-item-title {{
        color: var(--muted);
        text-transform: uppercase;
        font-size: var(--metric-label-font, 11px);
        font-weight: 700;
        letter-spacing: 0.08em;
      }}
      .footer-item-value {{
        margin-top: calc(4px * var(--type-scale, 1));
        font-size: var(--metric-value-font, 16px);
        font-weight: 700;
        line-height: 1.25;
      }}
      .note {{
        margin-top: calc(10px * var(--layout-scale, 1));
        color: var(--muted);
        font-size: var(--note-font, 12px);
      }}
      .tooltip {{
        position: fixed;
        z-index: 20;
        pointer-events: none;
        min-width: 200px;
        max-width: 280px;
        background: var(--tooltip-bg);
        color: #fff;
        border-radius: 10px;
        padding: 10px 12px;
        box-shadow: 0 16px 48px rgba(0,0,0,0.24);
        font-size: 11px;
        line-height: 1.5;
        opacity: 0;
        transform: translateY(4px);
        transition: opacity 120ms ease, transform 120ms ease;
      }}
      .tooltip.is-visible {{
        opacity: 1;
        transform: translateY(0);
      }}
      .tooltip-title {{
        font-weight: 700;
        margin-bottom: 4px;
      }}
      .tooltip-line {{
        color: rgba(255,255,255,0.84);
      }}
      @media (max-width: 820px) {{
        .provider-header {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .footer {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
      }}
      @media (max-width: 560px) {{
        .provider-header {{
          grid-template-columns: 1fr;
        }}
        .footer {{
          grid-template-columns: 1fr;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="page">
      <div class="page-header">
        <div>
          <h1 style="margin:0 0 4px;font-size:26px;">slopmeter</h1>
          <div class="range" id="range"></div>
        </div>
        <div class="page-actions">
          <div class="toolbar" id="toolbar">
            <button id="export-button" class="toolbar-button" type="button">Export PNG</button>
          </div>
          <div id="toolbar-hint" class="toolbar-hint"></div>
        </div>
      </div>
      <div id="providers"></div>
    </div>
    <div id="tooltip" class="tooltip" role="tooltip"></div>
    <script>
      const payload = {embedded};
      const providersRoot = document.getElementById("providers");
      const tooltip = document.getElementById("tooltip");
      const toolbar = document.getElementById("toolbar");
      const toolbarHint = document.getElementById("toolbar-hint");
      const exportButton = document.getElementById("export-button");
      const emptyCellColor = getComputedStyle(document.documentElement).getPropertyValue("--empty").trim();
      const ui = payload.ui || {{}};
      const exportConfig = ui.export || null;
      const storageKey = ui.storageKey || "slopmeter.provider-state";
      const providerMap = new Map((payload.providers || []).map((provider) => [provider.id, provider]));
      const defaultOrder = (payload.providers || []).map((provider) => provider.id);
      const state = createInitialState();
      let dragState = null;
      let toolbarStatus = null;
      document.getElementById("range").textContent = `${{payload.start}} to ${{payload.end}}`;
      const BASE_CELL_SIZE = {BASE_CELL_SIZE};
      const BASE_GAP = {BASE_GAP};
      const BASE_LEFT_LABEL_WIDTH = {BASE_LEFT_LABEL_WIDTH};
      const BASE_MONTH_ROW_HEIGHT = {BASE_MONTH_HEADER_HEIGHT};
      const TARGET_CONTENT_BREATHING_ROOM = {TARGET_CONTENT_BREATHING_ROOM};
      const MAX_LAYOUT_SCALE = {MAX_LAYOUT_SCALE};
      const SCALEABLE_WEEK_THRESHOLD = {SCALEABLE_WEEK_THRESHOLD};
      const TEXT_SCALE_FACTOR = {TEXT_SCALE_FACTOR};
      const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const WEEKDAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

      function scaleSpacing(value, scale) {{
        return Math.max(1, Math.round(value * scale));
      }}

      function scaleType(value, typeScale) {{
        return Math.max(8, Math.round(value * typeScale));
      }}

      function getScaledContentWidth(weekCount, scale) {{
        const cellSize = scaleSpacing(BASE_CELL_SIZE, scale);
        const gap = scaleSpacing(BASE_GAP, scale);
        const leftLabelWidth = scaleSpacing(BASE_LEFT_LABEL_WIDTH, scale);
        return leftLabelWidth + (weekCount * cellSize) + (Math.max(weekCount - 1, 0) * gap);
      }}

      function getLayoutMetrics(weekCount, availableContentWidth) {{
        const targetContentWidth = Math.max(availableContentWidth - TARGET_CONTENT_BREATHING_ROOM, BASE_LEFT_LABEL_WIDTH + BASE_CELL_SIZE);
        const baseGridWidth = (weekCount * BASE_CELL_SIZE) + (Math.max(weekCount - 1, 0) * BASE_GAP);
        const baseContentWidth = BASE_LEFT_LABEL_WIDTH + baseGridWidth;
        const rawScale = baseContentWidth > 0 ? (targetContentWidth / baseContentWidth) : 1;
        const scale = weekCount < SCALEABLE_WEEK_THRESHOLD ? 1 : Math.min(MAX_LAYOUT_SCALE, Math.max(1, rawScale));
        let resolvedScale = scale;
        while (resolvedScale > 1 && getScaledContentWidth(weekCount, resolvedScale) > targetContentWidth) {{
          resolvedScale = Math.max(1, Number((resolvedScale - 0.01).toFixed(4)));
        }}
        const typeScale = 1 + ((resolvedScale - 1) * TEXT_SCALE_FACTOR);
        const cellSize = scaleSpacing(BASE_CELL_SIZE, resolvedScale);
        const gap = scaleSpacing(BASE_GAP, resolvedScale);
        const leftLabelWidth = scaleSpacing(BASE_LEFT_LABEL_WIDTH, resolvedScale);
        const monthRowHeight = scaleSpacing(BASE_MONTH_ROW_HEIGHT, resolvedScale);
        const gridWidth = (weekCount * cellSize) + (Math.max(weekCount - 1, 0) * gap);
        const calendarWidth = leftLabelWidth + gridWidth;
        return {{
          scale: resolvedScale,
          typeScale,
          cellSize,
          gap,
          leftLabelWidth,
          monthRowHeight,
          gridWidth,
          calendarWidth,
          providerTitleFont: scaleType({PROVIDER_TITLE_FONT_SIZE}, typeScale),
          metricLabelFont: scaleType({METRIC_CAPTION_FONT_SIZE}, typeScale),
          metricValueFont: scaleType({METRIC_VALUE_FONT_SIZE}, typeScale),
          smallFont: scaleType(10, typeScale),
          noteFont: scaleType(11, typeScale),
        }};
      }}

      function formatTokenTotal(value) {{
        const units = [
          [1_000_000_000_000, "T"],
          [1_000_000_000, "B"],
          [1_000_000, "M"],
          [1_000, "K"],
        ];
        for (const [size, suffix] of units) {{
          if (value >= size) {{
            const scaled = value / size;
            const precision = scaled >= 100 ? 0 : scaled >= 10 ? 1 : 2;
            return scaled.toFixed(precision).replace(/\\.0+$/, "").replace(/(\\.\\d*[1-9])0+$/, "$1") + suffix;
          }}
        }}
        return new Intl.NumberFormat("en-US").format(value);
      }}

      function parseDateKey(value) {{
        const [year, month, day] = value.split("-").map(Number);
        return new Date(Date.UTC(year, month - 1, day));
      }}

      function formatDateKey(value) {{
        const year = value.getUTCFullYear();
        const month = String(value.getUTCMonth() + 1).padStart(2, "0");
        const day = String(value.getUTCDate()).padStart(2, "0");
        return `${{year}}-${{month}}-${{day}}`;
      }}

      function formatTooltipDate(value) {{
        const parsed = parseDateKey(value);
        const weekday = WEEKDAY_NAMES[parsed.getUTCDay()];
        const month = MONTH_NAMES[parsed.getUTCMonth()];
        const day = String(parsed.getUTCDate()).padStart(2, "0");
        return `${{weekday}} ${{month}} ${{day}} ${{parsed.getUTCFullYear()}}`;
      }}

      function formatShortMonthDay(value) {{
        const parsed = parseDateKey(value);
        return `${{MONTH_NAMES[parsed.getUTCMonth()]}} ${{parsed.getUTCDate()}}`;
      }}

      function getAllDays(start, end) {{
        const days = [];
        const current = parseDateKey(start);
        const endDate = parseDateKey(end);
        while (current <= endDate) {{
          days.push(formatDateKey(current));
          current.setUTCDate(current.getUTCDate() + 1);
        }}
        return days;
      }}

      function padToWeekStartMonday(days) {{
        const weekday = (parseDateKey(days[0]).getUTCDay() + 6) % 7;
        return [...Array(weekday).fill(null), ...days];
      }}

      function chunkByWeek(days) {{
        const weeks = [];
        for (let i = 0; i < days.length; i += 7) {{
          weeks.push(days.slice(i, i + 7));
        }}
        return weeks;
      }}

      function getMonthLabel(week) {{
        const lastDay = [...week].reverse().find(Boolean);
        if (!lastDay) return null;
        return MONTH_NAMES[parseDateKey(lastDay).getUTCMonth()];
      }}

      function buildMonthLabels(weeks) {{
        return weeks.map((week, index) => {{
          const label = getMonthLabel(week);
          const prev = index > 0 ? getMonthLabel(weeks[index - 1]) : null;
          return label !== prev ? label : null;
        }});
      }}

      function defaultColourMap(value, maxValue, colorCount) {{
        if (maxValue <= 0 || value <= 0) return 0;
        const scaled = Math.pow(value / maxValue, 0.7);
        return Math.min(Math.max(Math.ceil(scaled * (colorCount - 1)), 0), colorCount - 1);
      }}

      function showTooltip(event, day, row) {{
        const breakdown = (row.breakdown || []).slice(0, 3).map((item) =>
          `<div class="tooltip-line">${{item.name}}: ${{formatTokenTotal(item.tokens.total)}}</div>`
        ).join("");
        tooltip.innerHTML = `
          <div class="tooltip-title">${{formatTooltipDate(day)}}</div>
          <div class="tooltip-line">${{formatTokenTotal(row.total)}} total tokens</div>
          <div class="tooltip-line">In: ${{formatTokenTotal(row.input)}} | Out: ${{formatTokenTotal(row.output)}}</div>
          <div class="tooltip-line">Cache In: ${{formatTokenTotal(row.cache.input)}} | Cache Out: ${{formatTokenTotal(row.cache.output)}}</div>
          ${{breakdown || '<div class="tooltip-line">No model breakdown</div>'}}
        `;
        tooltip.classList.add("is-visible");
        moveTooltip(event);
      }}

      function hideTooltip() {{
        tooltip.classList.remove("is-visible");
      }}

      function moveTooltip(event) {{
        const offset = 14;
        tooltip.style.left = `${{Math.min(window.innerWidth - tooltip.offsetWidth - 16, event.clientX + offset)}}px`;
        tooltip.style.top = `${{Math.min(window.innerHeight - tooltip.offsetHeight - 16, event.clientY + offset)}}px`;
      }}

      function readStoredState() {{
        try {{
          const raw = window.localStorage.getItem(storageKey);
          return raw ? JSON.parse(raw) : null;
        }} catch (_error) {{
          return null;
        }}
      }}

      function createInitialState() {{
        const stored = readStoredState() || {{}};
        const savedOrder = Array.isArray(stored.order)
          ? stored.order.filter((providerId) => providerMap.has(providerId))
          : [];
        const order = [...savedOrder, ...defaultOrder.filter((providerId) => !savedOrder.includes(providerId))];
        const selectedIds = Array.isArray(stored.selected)
          ? stored.selected.filter((providerId) => providerMap.has(providerId))
          : [...defaultOrder];
        return {{
          order,
          selected: new Set(selectedIds),
        }};
      }}

      function saveState() {{
        try {{
          window.localStorage.setItem(
            storageKey,
            JSON.stringify({{
              order: state.order,
              selected: state.order.filter((providerId) => state.selected.has(providerId)),
            }})
          );
        }} catch (_error) {{
          return;
        }}
      }}

      function getSelectedProviderIds() {{
        return state.order.filter((providerId) => state.selected.has(providerId));
      }}

      function getDefaultToolbarMessage() {{
        const selectedCount = getSelectedProviderIds().length;
        if (!state.order.length) return "No provider cards are available.";
        if (exportConfig) {{
          return `${{selectedCount}} of ${{state.order.length}} providers selected. Drag cards to reorder, then export PNG.`;
        }}
        return "Drag cards to reorder.";
      }}

      function updateToolbarStatus(message = null, isError = false) {{
        toolbarStatus = message ? {{ message, isError }} : null;
        const resolved = toolbarStatus ? toolbarStatus.message : getDefaultToolbarMessage();
        toolbarHint.textContent = resolved;
        toolbarHint.classList.toggle("is-error", toolbarStatus ? toolbarStatus.isError : false);
        if (exportButton) {{
          exportButton.hidden = !exportConfig;
          exportButton.disabled = !exportConfig || getSelectedProviderIds().length === 0;
        }}
        if (toolbar) {{
          toolbar.hidden = !exportConfig;
        }}
      }}

      function getRenderedProviderCards() {{
        return [...providersRoot.children].filter((element) => element.classList?.contains("provider"));
      }}

      function getRenderedProviderOrder() {{
        return getRenderedProviderCards()
          .map((element) => element.dataset.providerId)
          .filter(Boolean);
      }}

      function captureProviderPositions() {{
        const positions = new Map();
        getRenderedProviderCards().forEach((element) => {{
          positions.set(element.dataset.providerId, element.getBoundingClientRect());
        }});
        return positions;
      }}

      function animateProviderReflow(beforePositions) {{
        getRenderedProviderCards().forEach((element) => {{
          const before = beforePositions.get(element.dataset.providerId);
          if (!before) return;
          const after = element.getBoundingClientRect();
          const deltaX = before.left - after.left;
          const deltaY = before.top - after.top;
          if (Math.abs(deltaX) < 1 && Math.abs(deltaY) < 1) return;

          element.style.transition = "none";
          element.style.transform = `translate(${{deltaX}}px, ${{deltaY}}px)`;
          requestAnimationFrame(() => {{
            element.style.transition = "transform 160ms ease";
            element.style.transform = "";
            window.setTimeout(() => {{
              if (element.style.transform === "") {{
                element.style.transition = "";
              }}
            }}, 180);
          }});
        }});
      }}

      function removeDragListeners() {{
        window.removeEventListener("pointermove", handleProviderDragMove);
        window.removeEventListener("pointerup", handleProviderDragEnd);
        window.removeEventListener("pointercancel", handleProviderDragCancel);
        window.removeEventListener("resize", handleProviderDragCancel);
      }}

      function clearDraggedSectionStyles(section) {{
        section.classList.remove("is-pointer-dragging");
        section.style.left = "";
        section.style.top = "";
        section.style.width = "";
        section.style.height = "";
      }}

      function createProviderPlaceholder(section) {{
        const placeholder = document.createElement("div");
        placeholder.className = "provider-placeholder";
        placeholder.style.height = `${{section.getBoundingClientRect().height}}px`;
        return placeholder;
      }}

      function positionDraggedSection(clientY) {{
        if (!dragState) return;
        dragState.section.style.left = `${{dragState.left}}px`;
        dragState.section.style.top = `${{clientY - dragState.pointerOffsetY}}px`;
      }}

      function movePlaceholderToPointer(clientY) {{
        if (!dragState) return;

        const draggedTop = clientY - dragState.pointerOffsetY;
        const draggedCenterY = draggedTop + (dragState.height / 2);
        const cards = getRenderedProviderCards().filter(
          (element) => element.dataset.providerId !== dragState.providerId
        );

        let targetElement = null;
        for (const element of cards) {{
          const rect = element.getBoundingClientRect();
          if (draggedCenterY < rect.top + (rect.height / 2)) {{
            targetElement = element;
            break;
          }}
        }}

        const placeholder = dragState.placeholder;
        const alreadyInPlace = targetElement
          ? placeholder.nextElementSibling === targetElement
          : placeholder === providersRoot.lastElementChild;
        if (alreadyInPlace) return;

        const beforePositions = captureProviderPositions();
        if (targetElement) {{
          providersRoot.insertBefore(placeholder, targetElement);
        }} else {{
          providersRoot.appendChild(placeholder);
        }}
        animateProviderReflow(beforePositions);
      }}

      function commitProviderDrag() {{
        if (!dragState) return;
        const activeState = dragState;
        dragState = null;
        removeDragListeners();
        document.body.classList.remove("is-sorting-providers");
        hideTooltip();

        if (activeState.handle?.releasePointerCapture) {{
          try {{
            activeState.handle.releasePointerCapture(activeState.pointerId);
          }} catch (_error) {{
            // Pointer capture can already be released by the browser.
          }}
        }}

        providersRoot.insertBefore(activeState.section, activeState.placeholder);
        clearDraggedSectionStyles(activeState.section);
        activeState.placeholder.remove();
        state.order = getRenderedProviderOrder();
        saveState();
        updateToolbarStatus();
      }}

      function cancelProviderDrag() {{
        if (!dragState) return;
        const activeState = dragState;
        dragState = null;
        removeDragListeners();
        document.body.classList.remove("is-sorting-providers");
        hideTooltip();

        if (activeState.handle?.releasePointerCapture) {{
          try {{
            activeState.handle.releasePointerCapture(activeState.pointerId);
          }} catch (_error) {{
            // Pointer capture can already be released by the browser.
          }}
        }}

        activeState.section.remove();
        activeState.placeholder.remove();
        state.order = activeState.originalOrder.slice();
        renderProviders();
      }}

      function handleProviderDragMove(event) {{
        if (!dragState || event.pointerId !== dragState.pointerId) return;
        event.preventDefault();
        positionDraggedSection(event.clientY);
        movePlaceholderToPointer(event.clientY);
      }}

      function handleProviderDragEnd(event) {{
        if (!dragState || event.pointerId !== dragState.pointerId) return;
        commitProviderDrag();
      }}

      function handleProviderDragCancel(event) {{
        if (!dragState) return;
        if (event?.type !== "resize" && event?.pointerId !== dragState.pointerId) return;
        cancelProviderDrag();
      }}

      function startProviderDrag(event, providerId, section) {{
        if (dragState) return;
        if (event.pointerType === "mouse" && event.button !== 0) return;

        event.preventDefault();
        hideTooltip();

        const rect = section.getBoundingClientRect();
        const placeholder = createProviderPlaceholder(section);
        providersRoot.insertBefore(placeholder, section);
        document.body.appendChild(section);

        section.classList.add("is-pointer-dragging");
        section.style.width = `${{rect.width}}px`;
        section.style.height = `${{rect.height}}px`;
        section.style.left = `${{rect.left}}px`;
        section.style.top = `${{rect.top}}px`;

        dragState = {{
          pointerId: event.pointerId,
          providerId,
          section,
          placeholder,
          handle: event.currentTarget,
          left: rect.left,
          height: rect.height,
          pointerOffsetY: event.clientY - rect.top,
          originalOrder: state.order.slice(),
        }};

        document.body.classList.add("is-sorting-providers");

        if (event.currentTarget?.setPointerCapture) {{
          try {{
            event.currentTarget.setPointerCapture(event.pointerId);
          }} catch (_error) {{
            // Pointer capture is optional on some platforms.
          }}
        }}

        window.addEventListener("pointermove", handleProviderDragMove, {{ passive: false }});
        window.addEventListener("pointerup", handleProviderDragEnd);
        window.addEventListener("pointercancel", handleProviderDragCancel);
        window.addEventListener("resize", handleProviderDragCancel);
      }}

      function applyProviderSelectionState(providerId) {{
        const section = providersRoot.querySelector(`[data-provider-id="${{providerId}}"]`);
        if (!section) return;
        section.dataset.exportSelected = state.selected.has(providerId) ? "true" : "false";
      }}

      function toggleProviderSelection(providerId, isSelected) {{
        if (isSelected) {{
          state.selected.add(providerId);
        }} else {{
          state.selected.delete(providerId);
        }}
        saveState();
        applyProviderSelectionState(providerId);
        hideTooltip();
        updateToolbarStatus();
      }}

      async function exportSelection() {{
        if (!exportConfig) return;
        const providerIds = getSelectedProviderIds();
        if (!providerIds.length) {{
          updateToolbarStatus("Select at least one provider to export.", true);
          return;
        }}

        exportButton.disabled = true;
        updateToolbarStatus("Exporting PNG...");

        try {{
          const response = await fetch(exportConfig.endpoint, {{
            method: "POST",
            headers: {{
              "Content-Type": "application/json",
            }},
            body: JSON.stringify({{ providerIds }}),
          }});

          if (!response.ok) {{
            let errorMessage = `Export failed (${{response.status}})`;
            try {{
              const errorPayload = await response.json();
              if (errorPayload && typeof errorPayload.error === "string" && errorPayload.error) {{
                errorMessage = errorPayload.error;
              }}
            }} catch (_error) {{
              // Keep the fallback message when the error body is not JSON.
            }}
            throw new Error(errorMessage);
          }}

          const blob = await response.blob();
          const filename = getFilenameFromHeader(response.headers.get("Content-Disposition"))
            || `slopmeter_${{providerIds.join("_")}}.png`;
          downloadBlob(blob, filename);
          updateToolbarStatus(`Exported ${{providerIds.length}} provider${{providerIds.length === 1 ? "" : "s"}} to ${{filename}}.`);
        }} catch (error) {{
          updateToolbarStatus(error instanceof Error ? error.message : "Export failed.", true);
        }} finally {{
          if (exportButton) {{
            exportButton.disabled = !exportConfig || getSelectedProviderIds().length === 0;
          }}
        }}
      }}

      function getFilenameFromHeader(value) {{
        if (!value) return null;
        const match = value.match(/filename="?([^"]+)"?/i);
        return match ? match[1] : null;
      }}

      function downloadBlob(blob, filename) {{
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      }}

      function renderProvider(provider) {{
        const section = document.createElement("section");
        section.className = "provider";
        section.dataset.providerId = provider.id;
        section.dataset.exportSelected = state.selected.has(provider.id) ? "true" : "false";

        const allDays = getAllDays(payload.start, payload.end);
        const paddedDays = padToWeekStartMonday(allDays);
        const weeks = chunkByWeek(paddedDays);
        const monthLabels = buildMonthLabels(weeks);
        const valueByDate = new Map();
        const rowByDate = new Map();
        let maxValue = 0;
        let totalInput = 0;
        let totalOutput = 0;
        let totalTokens = 0;
        let firstActivityOnlyDate = null;
        let firstMeasuredDate = null;
        const availableContentWidth = Math.max(providersRoot.clientWidth - ({HTML_PROVIDER_HORIZONTAL_PADDING} * 2), 0);
        const layout = getLayoutMetrics(weeks.length, availableContentWidth);

        for (const row of provider.daily) {{
          const displayValue = row.displayValue ?? row.total;
          valueByDate.set(row.date, displayValue);
          rowByDate.set(row.date, row);
          maxValue = Math.max(maxValue, displayValue);
          if (row.total <= 0 && displayValue > 0) {{
            if (!firstActivityOnlyDate || row.date < firstActivityOnlyDate) firstActivityOnlyDate = row.date;
          }} else if (row.total > 0) {{
            if (!firstMeasuredDate || row.date < firstMeasuredDate) firstMeasuredDate = row.date;
          }}
          totalInput += row.input;
          totalOutput += row.output;
          totalTokens += row.total;
        }}

        const topLine = document.createElement("div");
        topLine.className = "provider-topline";

        const badge = document.createElement("div");
        badge.className = "provider-badge";
        badge.textContent = provider.id === "all" ? "Aggregate" : "Provider";
        topLine.appendChild(badge);

        const controls = document.createElement("div");
        controls.className = "provider-controls";

        const toggle = document.createElement("label");
        toggle.className = "provider-toggle";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = state.selected.has(provider.id);
        checkbox.addEventListener("change", () => toggleProviderSelection(provider.id, checkbox.checked));
        toggle.appendChild(checkbox);
        toggle.appendChild(document.createTextNode("Include in export"));
        controls.appendChild(toggle);

        const dragHandle = document.createElement("div");
        dragHandle.className = "drag-handle";
        dragHandle.textContent = "Drag";
        dragHandle.title = "Drag to reorder";
        dragHandle.addEventListener("pointerdown", (event) => startProviderDrag(event, provider.id, section));
        controls.appendChild(dragHandle);

        topLine.appendChild(controls);
        section.appendChild(topLine);

        const shellWrap = document.createElement("div");
        shellWrap.className = "provider-shell-wrap";
        const shell = document.createElement("div");
        shell.className = "provider-shell";
        shell.style.setProperty("--layout-scale", String(layout.scale));
        shell.style.setProperty("--type-scale", String(layout.typeScale));
        shell.style.setProperty("--shell-width", `${{layout.calendarWidth}}px`);
        shell.style.setProperty("--calendar-width", `${{layout.calendarWidth}}px`);
        shell.style.setProperty("--cell-size", `${{layout.cellSize}}px`);
        shell.style.setProperty("--cell-gap", `${{layout.gap}}px`);
        shell.style.setProperty("--provider-title-font", `${{layout.providerTitleFont}}px`);
        shell.style.setProperty(
          "--aggregate-title-font",
          `${{Math.max(layout.metricValueFont, Math.round(layout.providerTitleFont * 0.74))}}px`
        );
        shell.style.setProperty("--metric-label-font", `${{layout.metricLabelFont}}px`);
        shell.style.setProperty("--metric-value-font", `${{layout.metricValueFont}}px`);
        shell.style.setProperty("--small-font", `${{layout.smallFont}}px`);
        shell.style.setProperty("--note-font", `${{layout.noteFont}}px`);

        const header = document.createElement("div");
        header.className = "provider-header";
        if (provider.id === "all") {{
          header.classList.add("is-aggregate");
        }}
        header.innerHTML = `
          <div class="provider-heading">
            <div class="provider-caption">${{provider.id === "all" ? "Total usage from" : "Provider"}}</div>
            <div class="provider-title${{provider.id === "all" ? " is-aggregate-title" : ""}}">${{provider.title}}</div>
          </div>
          <div class="metrics">
            <div class="metric"><div class="metric-label">Input tokens</div><div class="metric-value">${{formatTokenTotal(totalInput)}}</div></div>
            <div class="metric"><div class="metric-label">Output tokens</div><div class="metric-value">${{formatTokenTotal(totalOutput)}}</div></div>
            <div class="metric"><div class="metric-label">Total tokens</div><div class="metric-value">${{formatTokenTotal(totalTokens)}}</div></div>
          </div>
        `;
        shell.appendChild(header);

        const calendarWrap = document.createElement("div");
        calendarWrap.className = "calendar-wrap";
        const calendarGrid = document.createElement("div");
        calendarGrid.className = "calendar";
        calendarGrid.style.gridTemplateColumns = `${{layout.leftLabelWidth}}px repeat(${{weeks.length}}, ${{layout.cellSize}}px)`;
        calendarGrid.style.gridTemplateRows = `${{layout.monthRowHeight}}px repeat(7, ${{layout.cellSize}}px)`;

        monthLabels.forEach((label, weekIndex) => {{
          if (!label) return;
          const monthLabel = document.createElement("div");
          monthLabel.className = "month-label";
          monthLabel.textContent = label;
          monthLabel.style.gridColumn = String(weekIndex + 2);
          monthLabel.style.gridRow = "1";
          calendarGrid.appendChild(monthLabel);
        }});

        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].forEach((label, index) => {{
          if (![0, 6].includes(index)) return;
          const dayLabel = document.createElement("div");
          dayLabel.className = "day-label";
          dayLabel.textContent = label;
          dayLabel.style.gridColumn = "1";
          dayLabel.style.gridRow = String(index + 2);
          calendarGrid.appendChild(dayLabel);
        }});

        weeks.forEach((week, weekIndex) => {{
          week.forEach((day, dayIndex) => {{
            if (!day) return;
            const row = rowByDate.get(day) || {{
              date: day,
              input: 0,
              output: 0,
              cache: {{ input: 0, output: 0 }},
              total: 0,
              breakdown: [],
            }};
            const value = valueByDate.get(day) || 0;
            const colorIndex = defaultColourMap(value, maxValue, provider.colors.length);
            const fill = value <= 0 ? emptyCellColor : provider.colors[colorIndex];
            const button = document.createElement("button");
            button.type = "button";
            button.className = "cell";
            button.style.gridColumn = String(weekIndex + 2);
            button.style.gridRow = String(dayIndex + 2);
            button.style.background = fill;
            button.setAttribute("aria-label", `${{day}}: ${{row.total}} total tokens`);
            button.addEventListener("mouseenter", (event) => showTooltip(event, day, row));
            button.addEventListener("mousemove", moveTooltip);
            button.addEventListener("mouseleave", hideTooltip);
            calendarGrid.appendChild(button);
          }});
        }});

        calendarWrap.appendChild(calendarGrid);
        shell.appendChild(calendarWrap);

        const legend = document.createElement("div");
        legend.className = "legend";
        legend.innerHTML = `<span>Less</span>`;
        [emptyCellColor, ...provider.colors.slice(1)].forEach((color) => {{
          const swatch = document.createElement("span");
          swatch.className = "legend-swatch";
          swatch.style.background = color;
          legend.appendChild(swatch);
        }});
        const more = document.createElement("span");
        more.textContent = "More";
        legend.appendChild(more);
        shell.appendChild(legend);

        if (firstActivityOnlyDate && firstMeasuredDate) {{
          const note = document.createElement("div");
          note.className = "note";
          note.textContent = `Claude started logging full token telemetry on ${{formatShortMonthDay(firstMeasuredDate)}}; earlier activity may be undercounted.`;
          shell.appendChild(note);
        }}

        const footer = document.createElement("div");
        footer.className = "footer";
        const footerItems = [
          ["Most used model", provider.insights?.mostUsedModel ? `${{provider.insights.mostUsedModel.name}} (${{formatTokenTotal(provider.insights.mostUsedModel.tokens.total)}})` : ""],
          ["Recent use (last 30 days)", provider.insights?.recentMostUsedModel ? `${{provider.insights.recentMostUsedModel.name}} (${{formatTokenTotal(provider.insights.recentMostUsedModel.tokens.total)}})` : ""],
          ["Longest streak", `${{provider.insights?.streaks?.longest ?? 0}} days`],
          ["Current streak", `${{provider.insights?.streaks?.current ?? 0}} days`],
        ];
        footerItems.forEach(([label, value]) => {{
          const item = document.createElement("div");
          item.innerHTML = `<div class="footer-item-title">${{label}}</div><div class="footer-item-value">${{value || "—"}}</div>`;
          footer.appendChild(item);
        }});
        shell.appendChild(footer);
        shellWrap.appendChild(shell);
        section.appendChild(shellWrap);

        providersRoot.appendChild(section);
      }}

      function renderProviders() {{
        providersRoot.innerHTML = "";
        state.order.forEach((providerId) => {{
          const provider = providerMap.get(providerId);
          if (provider) renderProvider(provider);
        }});
        updateToolbarStatus();
      }}

      if (exportButton) {{
        exportButton.addEventListener("click", exportSelection);
      }}

      renderProviders();
    </script>
  </body>
</html>
"""
