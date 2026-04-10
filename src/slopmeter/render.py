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


def resolve_text_draw_origin(
    node: TextNode,
    *,
    scale: float,
    bbox: tuple[int, int, int, int],
) -> tuple[float, float]:
    left, top, right, bottom = bbox
    draw_x = node.x * scale
    draw_y = node.y * scale

    if node.anchor == "end":
        draw_x -= right
    elif node.anchor == "middle":
        draw_x -= (left + right) / 2
    else:
        draw_x -= left

    if node.baseline == "middle":
        draw_y -= (top + bottom) / 2
    else:
        draw_y -= top

    return draw_x, draw_y


def draw_text_node(draw: ImageDraw.ImageDraw, node: TextNode, scale: float) -> None:
    font_size = max(8, round(node.font_size * scale))
    font = load_font(font_size, node.font_weight >= 600)
    bbox = draw.textbbox((0, 0), node.text, font=font)
    draw_x, draw_y = resolve_text_draw_origin(node, scale=scale, bbox=bbox)
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
    from .html_document import render_html_document as _render_html_document

    return _render_html_document(payload)