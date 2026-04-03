from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

from slopmeter_py.cli import app
from slopmeter_py.models import CacheTokens, DailyUsage
from slopmeter_py.providers.cursor import summarize_cursor_usage_csv_text
from slopmeter_py.render import (
    RenderSection,
    build_heatmap_scene,
    get_calendar_grid,
    get_section_layout,
    get_target_content_width,
)

runner = CliRunner()


def recent_iso(days_ago: int = 0) -> str:
    value = datetime.now() - timedelta(days=days_ago)
    return value.isoformat()


def recent_date(days_ago: int = 0) -> str:
    value = datetime.now() - timedelta(days=days_ago)
    return value.strftime("%Y-%m-%d")


def write_jsonl_file(path: Path, records: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(records) + "\n", encoding="utf-8")


def write_json_file(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def codex_turn_context(model: str = "gpt-5") -> str:
    return json.dumps(
        {
            "type": "turn_context",
            "timestamp": recent_iso(),
            "payload": {"model": model},
        }
    )


def codex_usage(**overrides) -> dict[str, int]:
    input_tokens = overrides.get("input", 10)
    cached_input = overrides.get("cachedInput", 0)
    output_tokens = overrides.get("output", 5)
    reasoning_output = overrides.get("reasoningOutput", 0)
    total_tokens = overrides.get("total", input_tokens + output_tokens)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output,
        "total_tokens": total_tokens,
    }


def codex_token_count(**options) -> str:
    model = options.get("model")
    timestamp = options.get("timestamp", recent_iso())
    input_tokens = options.get("input", 10)
    cached_input = options.get("cachedInput", 0)
    output_tokens = options.get("output", 5)
    reasoning_output = options.get("reasoningOutput", 0)
    total_tokens = options.get("total", input_tokens + output_tokens)
    last_usage = options.get(
        "lastUsage",
        codex_usage(
            input=input_tokens,
            cachedInput=cached_input,
            output=output_tokens,
            reasoningOutput=reasoning_output,
            total=total_tokens,
        ),
    )
    total_usage = options.get("totalUsage")
    payload = {
        "type": "event_msg",
        "timestamp": timestamp,
        "payload": {
            "type": "token_count",
            **({"model": model} if model else {}),
            "info": {
                **({"last_token_usage": last_usage} if last_usage is not None else {}),
                **({"total_token_usage": total_usage} if total_usage is not None else {}),
            },
        },
    }
    return json.dumps(payload)


def open_code_message(**overrides) -> str:
    input_tokens = overrides.get("input", 6)
    output_tokens = overrides.get("output", 4)
    cache_read = overrides.get("cacheRead", 0)
    cache_write = overrides.get("cacheWrite", 0)
    created = overrides.get("created", int(datetime.now().timestamp() * 1000))
    return json.dumps(
        {
            "id": overrides.get("id", "msg-1"),
            "role": overrides.get("role", "assistant"),
            "modelID": overrides.get("modelID", "gpt-5.4"),
            "providerID": "openai",
            "time": {"created": created, "completed": created + 1000},
            "tokens": {
                "total": input_tokens + output_tokens + cache_read + cache_write,
                "input": input_tokens,
                "output": output_tokens,
                "cache": {"read": cache_read, "write": cache_write},
            },
        }
    )


def invoke(args: list[str], env: dict[str, str]):
    return runner.invoke(app, args, env=env, catch_exceptions=False)


def test_codex_json_export_from_cumulative_totals(tmp_path: Path):
    codex_home = tmp_path / "codex"
    output_path = tmp_path / "out.json"
    base_timestamp = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    write_jsonl_file(
        codex_home / "sessions" / "session.jsonl",
        [
            json.dumps(
                {
                    "type": "turn_context",
                    "timestamp": base_timestamp.isoformat(),
                    "payload": {"model": "gpt-5.2"},
                }
            ),
            codex_token_count(
                timestamp=(base_timestamp + timedelta(seconds=1)).isoformat(),
                input=100,
                cachedInput=20,
                output=30,
                reasoningOutput=5,
                total=130,
                totalUsage=codex_usage(
                    input=100,
                    cachedInput=20,
                    output=30,
                    reasoningOutput=5,
                    total=130,
                ),
            ),
        ],
    )

    result = invoke(
        ["--codex", "--format", "json", "--output", str(output_path)],
        {
            "HOME": str(tmp_path),
            "XDG_CONFIG_HOME": str(tmp_path / ".config"),
            "XDG_DATA_HOME": str(tmp_path / ".local" / "share"),
            "CODEX_HOME": str(codex_home),
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["providers"][0]["provider"] == "codex"
    assert payload["providers"][0]["daily"][0]["total"] == 130
    assert payload["providers"][0]["daily"][0]["breakdown"][0]["name"] == "gpt-5.2"


def test_claude_history_fallback_emits_activity_only_days(tmp_path: Path):
    claude_config = tmp_path / "claude"
    output_path = tmp_path / "out.json"

    write_json_file(
        claude_config / "history.jsonl",
        "\n".join(
            [
                json.dumps({"timestamp": f"{recent_date(6)}T08:00:00.000Z", "sessionId": "s-1"}),
                json.dumps({"timestamp": f"{recent_date(6)}T08:30:00.000Z", "sessionId": "s-1"}),
                json.dumps({"timestamp": f"{recent_date(5)}T09:00:00.000Z", "sessionId": "s-2"}),
            ]
        ),
    )

    result = invoke(
        ["--claude", "--format", "json", "--output", str(output_path)],
        {
            "HOME": str(tmp_path),
            "XDG_CONFIG_HOME": str(tmp_path / ".config"),
            "XDG_DATA_HOME": str(tmp_path / ".local" / "share"),
            "CLAUDE_CONFIG_DIR": str(claude_config),
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["providers"][0]["daily"][0]["total"] == 0
    assert payload["providers"][0]["daily"][0]["displayValue"] == 2
    assert payload["providers"][0]["daily"][1]["displayValue"] == 1


def test_opencode_reads_legacy_file_backed_message_layout(tmp_path: Path):
    open_code_dir = tmp_path / "opencode"
    output_path = tmp_path / "out.json"

    write_json_file(
        open_code_dir / "storage" / "message" / "one.json",
        open_code_message(id="msg-1", input=8, output=5, cacheRead=2),
    )

    result = invoke(
        ["--opencode", "--format", "json", "--output", str(output_path)],
        {
            "HOME": str(tmp_path),
            "XDG_CONFIG_HOME": str(tmp_path / ".config"),
            "XDG_DATA_HOME": str(tmp_path / ".local" / "share"),
            "OPENCODE_DATA_DIR": str(open_code_dir),
        },
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["providers"][0]["provider"] == "opencode"
    assert payload["providers"][0]["daily"][0]["total"] == 15


def test_cursor_csv_summary_reconstructs_cache_split():
    csv_text = "\n".join(
        [
            "Date,Model,Total Tokens,Input (w/ Cache Write),Input (w/o Cache Write),Cache Read,Output Tokens",
            f"{recent_date(0)},gpt-5.4,42,5,20,7,10",
        ]
    )
    now = datetime.now()
    summary = summarize_cursor_usage_csv_text(
        csv_text,
        start=now - timedelta(days=365),
        end=now,
    )
    assert summary.daily[0].input == 32
    assert summary.daily[0].output == 10
    assert summary.daily[0].cache.input == 7
    assert summary.daily[0].cache.output == 5
    assert summary.daily[0].total == 42


def test_html_svg_and_png_exports_are_generated(tmp_path: Path):
    codex_home = tmp_path / "codex"
    html_path = tmp_path / "heatmap.html"
    svg_path = tmp_path / "heatmap.svg"
    png_path = tmp_path / "heatmap.png"

    write_jsonl_file(
        codex_home / "sessions" / "session.jsonl",
        [
            codex_turn_context("gpt-5"),
            codex_token_count(input=12, output=8, total=20),
        ],
    )
    env = {
        "HOME": str(tmp_path),
        "XDG_CONFIG_HOME": str(tmp_path / ".config"),
        "XDG_DATA_HOME": str(tmp_path / ".local" / "share"),
        "CODEX_HOME": str(codex_home),
    }

    html_result = invoke(["--codex", "--format", "html", "--output", str(html_path)], env)
    svg_result = invoke(["--codex", "--format", "svg", "--output", str(svg_path)], env)
    png_result = invoke(["--codex", "--format", "png", "--output", str(png_path)], env)

    assert html_result.exit_code == 0, html_result.output
    assert svg_result.exit_code == 0, svg_result.output
    assert png_result.exit_code == 0, png_result.output

    html_text = html_path.read_text(encoding="utf-8")
    assert '<div id="tooltip"' in html_text
    assert "Codex" in html_text
    assert "provider-shell-wrap" in html_text
    assert "--layout-scale" in html_text
    assert "--shell-width" in html_text
    assert "function formatDateKey(value)" in html_text
    assert "current.setUTCDate(current.getUTCDate() + 1);" in html_text
    assert "toISOString().slice(0, 10)" not in html_text
    assert svg_path.read_text(encoding="utf-8").startswith("<svg")
    assert png_path.stat().st_size > 0


def test_static_header_metrics_align_to_calendar_right_edge():
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
    section = RenderSection(
        daily=daily,
        insights=None,
        title="Codex",
        colors={"light": ["#e0e7ff", "#a5b4fc", "#818cf8", "#4f46e5", "#312e81"], "dark": ["#1e1b4b", "#312e81", "#4338ca", "#818cf8", "#c7d2fe"]},
    )

    scene = build_heatmap_scene(
        start_date=now - timedelta(days=14),
        end_date=now,
        sections=[section],
        color_mode="light",
    )
    grid = get_calendar_grid(now - timedelta(days=14), now)
    layout = get_section_layout(len(grid.weeks))
    expected_right_edge = 18 + layout.left_label_width + layout.grid_width
    total_node = next(node for node in scene.nodes if getattr(node, "text", None) == "1.23K")

    assert total_node.x == expected_right_edge


def test_full_year_scene_scales_beyond_base_layout():
    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily = [
        DailyUsage(
            date=(now - timedelta(days=offset)).date(),
            input=100,
            output=25,
            cache=CacheTokens(),
            total=125,
            breakdown=[],
        )
        for offset in range(0, 42, 7)
    ]
    section = RenderSection(
        daily=daily,
        insights=None,
        title="Claude Code",
        colors={
            "light": ["#fff7ed", "#fed7aa", "#fdba74", "#f97316", "#c2410c"],
            "dark": ["#292524", "#9a3412", "#c2410c", "#f97316", "#fdba74"],
        },
    )

    scene = build_heatmap_scene(
        start_date=now - timedelta(days=365),
        end_date=now,
        sections=[section],
        color_mode="light",
    )
    grid = get_calendar_grid(now - timedelta(days=365), now)
    base_layout = get_section_layout(len(grid.weeks))
    scaled_layout = get_section_layout(
        len(grid.weeks),
        target_content_width=get_target_content_width(),
    )

    assert scene.width > (18 * 2) + base_layout.width
    assert scaled_layout.content_width <= get_target_content_width()
