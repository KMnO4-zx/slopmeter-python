#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from slopmeter.cli import get_date_window
from slopmeter.providers.claude import (
    create_claude_token_totals,
    create_stats_cache_token_totals,
    create_unique_hash,
    get_claude_files,
    get_claude_stats_cache_files,
    parse_claude_log_entry,
)
from slopmeter.utils import format_local_date, parse_datetime, read_json_document, read_json_lines


@dataclass
class SourceScan:
    daily: dict[str, int]
    file_count: int
    duplicate_entries: int = 0
    duplicate_tokens: int = 0

    @property
    def total(self) -> int:
        return sum(self.daily.values())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare Claude projects/*.jsonl totals against stats-cache.json totals.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        help="Number of overlapping-date diffs to print. Default: 15.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Trailing day window to inspect. Default: 365.",
    )
    return parser.parse_args()


def resolve_window(days: int) -> tuple[datetime, datetime]:
    if days == 365:
        return get_date_window()

    end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999000)
    start = (end - timedelta(days=max(days - 1, 0))).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return start, end


def collect_project_daily(start: datetime, end: datetime) -> SourceScan:
    daily: dict[str, int] = defaultdict(int)
    processed_hashes: set[str] = set()
    duplicate_entries = 0
    duplicate_tokens = 0
    files = get_claude_files()

    for file_path in files:
        for line in read_json_lines(file_path):
            if not isinstance(line, dict):
                continue

            entry = parse_claude_log_entry(line)
            if entry is None:
                continue

            timestamp = parse_datetime(entry.get("timestamp"))
            if timestamp is None or timestamp < start or timestamp > end:
                continue

            usage = entry.get("usage")
            if not isinstance(usage, dict):
                continue

            token_totals = create_claude_token_totals(usage)
            if token_totals.total <= 0:
                continue

            unique_hash = create_unique_hash(entry.get("message_id"), entry.get("request_id"))
            if unique_hash and unique_hash in processed_hashes:
                duplicate_entries += 1
                duplicate_tokens += token_totals.total
                continue
            if unique_hash:
                processed_hashes.add(unique_hash)

            daily[format_local_date(timestamp)] += token_totals.total

    return SourceScan(
        daily=dict(daily),
        file_count=len(files),
        duplicate_entries=duplicate_entries,
        duplicate_tokens=duplicate_tokens,
    )


def collect_stats_daily(start: datetime, end: datetime) -> SourceScan:
    daily: dict[str, int] = defaultdict(int)
    files = get_claude_stats_cache_files()

    for file_path in files:
        try:
            stats_cache = read_json_document(file_path)
        except Exception:
            continue

        for row in stats_cache.get("dailyModelTokens", []) or []:
            if not isinstance(row, dict):
                continue

            date_value = row.get("date")
            if not isinstance(date_value, str):
                continue

            timestamp = parse_datetime(f"{date_value}T00:00:00")
            if timestamp is None or timestamp < start or timestamp > end:
                continue

            tokens_by_model = row.get("tokensByModel") or {}
            if not isinstance(tokens_by_model, dict):
                continue

            model_usage = stats_cache.get("modelUsage") or {}
            if not isinstance(model_usage, dict):
                model_usage = {}

            for raw_model_name, total_tokens in tokens_by_model.items():
                if (
                    not isinstance(total_tokens, (int, float))
                    or not math.isfinite(total_tokens)
                    or total_tokens <= 0
                ):
                    continue

                token_totals = create_stats_cache_token_totals(
                    int(total_tokens),
                    model_usage.get(raw_model_name),
                )
                if token_totals.total <= 0:
                    continue

                daily[date_value] += token_totals.total

    return SourceScan(daily=dict(daily), file_count=len(files))


def format_tokens(value: int) -> str:
    return f"{value:,}"


def print_section(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def print_date_totals(label: str, dates: list[str], daily: dict[str, int]) -> None:
    total = sum(daily[day] for day in dates)
    print(f"{label}: {len(dates)} dates, {format_tokens(total)} tokens")
    for day in dates:
        print(f"  {day}: {format_tokens(daily[day])}")


def main() -> int:
    args = parse_args()
    start, end = resolve_window(args.days)
    projects = collect_project_daily(start, end)
    stats = collect_stats_daily(start, end)

    project_dates = set(projects.daily)
    stats_dates = set(stats.daily)
    overlap_dates = sorted(project_dates & stats_dates)
    project_only_dates = sorted(project_dates - stats_dates)
    stats_only_dates = sorted(stats_dates - project_dates)

    overlap_project_total = sum(projects.daily[day] for day in overlap_dates)
    overlap_stats_total = sum(stats.daily[day] for day in overlap_dates)
    project_only_total = sum(projects.daily[day] for day in project_only_dates)
    stats_only_total = sum(stats.daily[day] for day in stats_only_dates)
    combined_total = projects.total + stats_only_total

    overlap_diffs: list[tuple[int, str, int, int, int]] = []
    for day in overlap_dates:
        project_total = projects.daily[day]
        stats_total = stats.daily[day]
        if project_total == stats_total:
            continue
        overlap_diffs.append(
            (
                abs(project_total - stats_total),
                day,
                project_total,
                stats_total,
                stats_total - project_total,
            )
        )
    overlap_diffs.sort(reverse=True)

    print(f"Window: {start.date().isoformat()} to {end.date().isoformat()}")
    print(f"Claude project files: {projects.file_count}")
    print(f"Claude stats-cache files: {stats.file_count}")

    print_section("Totals")
    print(f"Projects total (deduped): {format_tokens(projects.total)} tokens across {len(project_dates)} dates")
    print(f"Stats total (raw):        {format_tokens(stats.total)} tokens across {len(stats_dates)} dates")
    print(f"Combined total used now:  {format_tokens(combined_total)} tokens")
    if projects.duplicate_entries:
        print(
            "Projects duplicates skipped: "
            f"{projects.duplicate_entries} entries, {format_tokens(projects.duplicate_tokens)} tokens"
        )

    print_section("Coverage")
    print(f"Project-only dates: {len(project_only_dates)}")
    print(f"Stats-only dates:   {len(stats_only_dates)}")
    print(f"Overlap dates:      {len(overlap_dates)}")
    print(f"Project-only total: {format_tokens(project_only_total)}")
    print(f"Stats-only total:   {format_tokens(stats_only_total)}")
    print(f"Overlap project:    {format_tokens(overlap_project_total)}")
    print(f"Overlap stats:      {format_tokens(overlap_stats_total)}")
    print(
        "Stats ignored on overlapping dates: "
        f"{format_tokens(overlap_stats_total)}"
    )

    if project_only_dates:
        print_section("Project-Only Dates")
        print_date_totals("Projects-only contribution", project_only_dates, projects.daily)

    if stats_only_dates:
        print_section("Stats-Only Dates")
        print_date_totals("Stats-only contribution", stats_only_dates, stats.daily)

    if overlap_diffs:
        print_section(f"Top {min(args.top, len(overlap_diffs))} Overlap Diffs")
        print("date        project_total    stats_total      stats_minus_project")
        for _, day, project_total, stats_total, delta in overlap_diffs[: args.top]:
            print(
                f"{day}  "
                f"{format_tokens(project_total):>14}  "
                f"{format_tokens(stats_total):>14}  "
                f"{format_tokens(delta):>20}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
