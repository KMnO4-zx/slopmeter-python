from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

import typer
from click.core import ParameterSource
from rich.console import Console

from .bundle_export import build_bundle_payload, build_device_source, build_theme_payload
from .device_meta import get_or_create_device_metadata
from .export import build_json_export, to_json_provider_summary
from .html_document import render_html_document
from .models import ColorMode, ProviderId, UsageProviderId, UsageSummary
from .output_path import ProviderSelectionValues, get_default_output_path
from .provider_meta import (
    DEFAULT_PROVIDER_IDS,
    ORDERABLE_PROVIDER_IDS,
    PROVIDER_IDS,
    PROVIDER_STATUS_LABEL,
    SERVICE_DEFAULT_PROVIDER_IDS,
)
from .providers import AggregateUsageResult, aggregate_usage, get_provider_availability, merge_provider_usage
from .render import HEATMAP_THEMES, RenderSection, render_usage_heatmaps_png, render_usage_heatmaps_svg
from .server import create_html_server
from .utils import format_local_date
from .yaml_bundle import dump_yaml

SelectionMode = Literal["serve", "export"]
SERVICE_EXPORT_ENDPOINT = "/api/export"
SERVICE_STORAGE_KEY = "slopmeter.provider-state"

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    name="slopmeter",
    context_settings={"help_option_names": ["-h", "--help"]},
)
stdout = Console()
stderr = Console(stderr=True)


@dataclass
class CliArgValues(ProviderSelectionValues):
    output: str | None = None
    format: str | None = None
    dark: bool = False


@dataclass
class AnalysisBundle:
    start: datetime
    end: datetime
    color_mode: ColorMode
    inspected_providers: list[ProviderId]
    availability_by_provider: dict[ProviderId, bool]
    aggregate_result: AggregateUsageResult
    export_providers: list[UsageSummary]
    payload: dict[str, object]


def infer_format(format_arg: str | None, output_arg: str | None) -> str:
    valid = {"png", "svg", "json", "html"}
    if format_arg:
        if format_arg not in valid:
            raise ValueError(f"Unsupported format: {format_arg}")
        return format_arg

    if output_arg:
        suffix = Path(output_arg).suffix.lower()
        if suffix in {".svg", ".json", ".html"}:
            return suffix[1:]

    return "png"


def get_date_window() -> tuple[datetime, datetime]:
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        start = start.replace(year=start.year - 1)
    except ValueError:
        start = start.replace(month=2, day=28, year=start.year - 1)

    end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999000)
    return start, end


def normalize_usage_provider_ids(provider_ids: list[str] | None) -> list[UsageProviderId]:
    normalized: list[UsageProviderId] = []
    seen: set[UsageProviderId] = set()
    valid = ", ".join(ORDERABLE_PROVIDER_IDS)

    for raw in provider_ids or []:
        raw_value = raw.strip()
        if raw_value.startswith("[") and raw_value.endswith("]"):
            raw_value = raw_value[1:-1]

        candidates = [item for item in re.split(r"[\s,，]+", raw_value) if item]
        if not candidates:
            raise ValueError(f"Unsupported provider: {raw}. Expected one of: {valid}")

        for candidate in candidates:
            lowered = candidate.strip().lower()
            if lowered not in ORDERABLE_PROVIDER_IDS:
                raise ValueError(f"Unsupported provider: {candidate}. Expected one of: {valid}")

            provider = cast(UsageProviderId, lowered)
            if provider in seen:
                raise ValueError(f"Duplicate provider requested: {PROVIDER_STATUS_LABEL[provider]}")

            normalized.append(provider)
            seen.add(provider)

    return normalized


def build_cli_values(
    *,
    output: str | None = None,
    format: str | None = None,
    dark: bool = False,
    providers: list[str] | None = None,
    all: bool = False,
    amp: bool = False,
    claude: bool = False,
    codex: bool = False,
    cursor: bool = False,
    gemini: bool = False,
    opencode: bool = False,
    pi: bool = False,
) -> CliArgValues:
    return CliArgValues(
        providers=normalize_usage_provider_ids(providers),
        output=output,
        format=format,
        dark=dark,
        all=all,
        amp=amp,
        claude=claude,
        codex=codex,
        cursor=cursor,
        gemini=gemini,
        opencode=opencode,
        pi=pi,
    )


def print_provider_availability(availability_by_provider: dict[ProviderId, bool], providers: list[ProviderId]) -> None:
    for provider in providers:
        status = "available" if availability_by_provider[provider] else "not available"
        print(f"{PROVIDER_STATUS_LABEL[provider]} {status}")


def get_requested_providers(values: ProviderSelectionValues) -> list[ProviderId]:
    return [provider for provider in PROVIDER_IDS if getattr(values, provider)]


def get_merged_no_data_message() -> str:
    return "No usage data found for Amp, Claude Code, Codex, Cursor, Gemini CLI, Open Code, or Pi Coding Agent."


def get_requested_missing_providers_message(missing: list[UsageProviderId]) -> str:
    labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in missing)
    return f"Requested provider data not found: {labels}"


def get_no_selected_provider_data_message(requested: list[UsageProviderId]) -> str:
    labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in requested)
    return f"No usage data found for selected providers: {labels}"


def get_default_output_provider_ids(rows_by_provider: dict[ProviderId, UsageSummary | None]) -> list[ProviderId]:
    selected: list[ProviderId] = []
    fallback_providers = [provider for provider in PROVIDER_IDS if provider not in DEFAULT_PROVIDER_IDS]

    for provider in [*DEFAULT_PROVIDER_IDS, *fallback_providers]:
        if rows_by_provider.get(provider) is None or provider in selected:
            continue
        selected.append(provider)
        if len(selected) == 3:
            return selected

    return selected


def filter_available_provider_ids(
    provider_ids: list[UsageProviderId],
    summary_lookup: dict[UsageProviderId, UsageSummary],
) -> tuple[list[UsageProviderId], list[UsageProviderId]]:
    available = [provider for provider in provider_ids if provider in summary_lookup]
    missing = [provider for provider in provider_ids if provider not in summary_lookup]
    return available, missing


def get_available_summary_lookup(
    rows_by_provider: dict[ProviderId, UsageSummary | None],
    end: datetime,
) -> dict[UsageProviderId, UsageSummary]:
    lookup: dict[UsageProviderId, UsageSummary] = {}
    for provider in PROVIDER_IDS:
        summary = rows_by_provider.get(provider)
        if summary is not None:
            lookup[provider] = summary

    merged = merge_provider_usage(rows_by_provider, end)
    if merged is not None:
        lookup["all"] = merged

    return lookup


def get_default_service_provider_ids(summary_lookup: dict[UsageProviderId, UsageSummary]) -> list[UsageProviderId]:
    selected: list[UsageProviderId] = []
    if "all" in summary_lookup:
        selected.append("all")

    for provider in SERVICE_DEFAULT_PROVIDER_IDS:
        if provider in summary_lookup:
            selected.append(provider)

    return selected


def get_merged_provider_title(rows_by_provider: dict[ProviderId, UsageSummary | None]) -> str:
    return " / ".join(
        HEATMAP_THEMES[provider].title
        for provider in PROVIDER_IDS
        if rows_by_provider.get(provider) is not None
    )


def get_no_data_with_available_message(
    availability_by_provider: dict[ProviderId, bool],
    *,
    selection_mode: SelectionMode,
) -> str:
    available_providers = [provider for provider in PROVIDER_IDS if availability_by_provider[provider]]
    if not available_providers:
        return get_merged_no_data_message()

    available_labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in available_providers)
    if selection_mode == "serve":
        preferred_order = ["all", *SERVICE_DEFAULT_PROVIDER_IDS]
    else:
        preferred_order = list(DEFAULT_PROVIDER_IDS)
    preferred_labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in preferred_order)
    return (
        "No usage data found for available providers "
        f"({available_labels}). Preferred order is {preferred_labels}."
    )


def resolve_provider_ids_to_render(
    values: ProviderSelectionValues,
    availability_by_provider: dict[ProviderId, bool],
    rows_by_provider: dict[ProviderId, UsageSummary | None],
    end: datetime,
    *,
    selection_mode: SelectionMode,
) -> list[UsageProviderId]:
    summary_lookup = get_available_summary_lookup(rows_by_provider, end)
    requested_flag_providers = get_requested_providers(values)

    if values.providers:
        provider_ids: list[UsageProviderId] = list(values.providers)
    elif values.all:
        provider_ids = ["all"]
    elif requested_flag_providers:
        provider_ids = list(requested_flag_providers)
    elif selection_mode == "serve":
        provider_ids = get_default_service_provider_ids(summary_lookup)
    else:
        provider_ids = list(get_default_output_provider_ids(rows_by_provider))

    if not provider_ids:
        raise ValueError(
            get_no_data_with_available_message(
                availability_by_provider,
                selection_mode=selection_mode,
            )
        )

    available_provider_ids, missing = filter_available_provider_ids(provider_ids, summary_lookup)
    if available_provider_ids:
        return available_provider_ids

    if values.providers or values.all or requested_flag_providers:
        if missing:
            raise ValueError(get_no_selected_provider_data_message(provider_ids))
        raise ValueError(get_no_selected_provider_data_message(provider_ids))

    raise ValueError(
        get_no_data_with_available_message(
            availability_by_provider,
            selection_mode=selection_mode,
        )
    )


def get_output_providers(
    values: ProviderSelectionValues,
    availability_by_provider: dict[ProviderId, bool],
    rows_by_provider: dict[ProviderId, UsageSummary | None],
    end: datetime,
    *,
    selection_mode: SelectionMode,
) -> list[UsageSummary]:
    summary_lookup = get_available_summary_lookup(rows_by_provider, end)
    provider_ids = resolve_provider_ids_to_render(
        values,
        availability_by_provider,
        rows_by_provider,
        end,
        selection_mode=selection_mode,
    )
    return [summary_lookup[provider] for provider in provider_ids]


def get_output_providers_for_ids(
    provider_ids: list[UsageProviderId],
    rows_by_provider: dict[ProviderId, UsageSummary | None],
    end: datetime,
) -> list[UsageSummary]:
    if not provider_ids:
        raise ValueError("Select at least one provider to export.")

    summary_lookup = get_available_summary_lookup(rows_by_provider, end)
    available_provider_ids, missing = filter_available_provider_ids(provider_ids, summary_lookup)
    if not available_provider_ids:
        if missing:
            raise ValueError(get_no_selected_provider_data_message(provider_ids))
        raise ValueError("Select at least one provider to export.")
    return [summary_lookup[provider] for provider in available_provider_ids]


def print_run_summary(
    output_path: Path,
    fmt: str,
    color_mode: ColorMode,
    start_date: datetime,
    end_date: datetime,
    rendered: list[UsageProviderId],
) -> None:
    print(
        json.dumps(
            {
                "output": str(output_path),
                "format": fmt,
                "colorMode": color_mode,
                "startDate": format_local_date(start_date),
                "endDate": format_local_date(end_date),
                "rendered": rendered,
            },
            indent=2,
        )
    )


def build_render_sections(
    export_providers: list[UsageSummary],
    rows_by_provider: dict[ProviderId, UsageSummary | None],
) -> list[RenderSection]:
    sections: list[RenderSection] = []
    for provider in export_providers:
        theme_key = provider.provider if provider.provider != "all" else "all"
        theme = HEATMAP_THEMES[theme_key]
        title = get_merged_provider_title(rows_by_provider) if provider.provider == "all" else theme.title
        sections.append(
            RenderSection(
                daily=provider.daily,
                insights=provider.insights,
                title=title,
                title_caption=theme.title_caption,
                colors=theme.colors,
            )
        )
    return sections


def build_export_payload(
    export_providers: list[UsageSummary],
    *,
    start: datetime,
    end: datetime,
    color_mode: ColorMode,
    rows_by_provider: dict[ProviderId, UsageSummary | None],
) -> dict[str, object]:
    providers = []
    for provider in export_providers:
        theme_key = provider.provider if provider.provider != "all" else "all"
        theme = HEATMAP_THEMES[theme_key]
        title = get_merged_provider_title(rows_by_provider) if provider.provider == "all" else theme.title
        providers.append(
            to_json_provider_summary(
                provider,
                title=title,
                colors=theme.colors[color_mode],
            )
        )
    payload = build_json_export(
        start=start,
        end=end,
        color_mode=color_mode,
        providers=providers,
    )
    bundle_source = build_device_source(
        get_or_create_device_metadata(),
        get_bundle_export_providers(export_providers, rows_by_provider),
        generated_at=datetime.now(),
    )
    payload["bundle"] = build_bundle_payload(
        start=start,
        end=end,
        sources=[bundle_source],
    )
    payload["themes"] = build_theme_payload(color_mode)
    return payload


def get_bundle_export_providers(
    export_providers: list[UsageSummary],
    rows_by_provider: dict[ProviderId, UsageSummary | None],
) -> list[UsageSummary]:
    selected: list[UsageSummary] = []
    seen: set[ProviderId] = set()
    includes_all = any(provider.provider == "all" for provider in export_providers)

    if includes_all:
        for provider_id in PROVIDER_IDS:
            summary = rows_by_provider.get(provider_id)
            if summary is None or provider_id in seen:
                continue
            selected.append(summary)
            seen.add(provider_id)
        return selected

    for provider in export_providers:
        if provider.provider not in PROVIDER_IDS:
            continue
        provider_id = cast(ProviderId, provider.provider)
        if provider_id in seen:
            continue
        selected.append(provider)
        seen.add(provider_id)
    return selected


def get_data_export_providers(
    values: ProviderSelectionValues,
    rows_by_provider: dict[ProviderId, UsageSummary | None],
) -> list[UsageSummary]:
    summary_lookup = {
        provider: summary
        for provider, summary in rows_by_provider.items()
        if summary is not None
    }

    if values.providers:
        requested: list[ProviderId] = []
        includes_all = "all" in values.providers
        if includes_all:
            requested.extend(PROVIDER_IDS)
        for provider in values.providers:
            if provider == "all":
                continue
            provider_id = cast(ProviderId, provider)
            if provider_id not in requested:
                requested.append(provider_id)
    elif values.all:
        requested = list(PROVIDER_IDS)
    else:
        requested_flags = get_requested_providers(values)
        requested = requested_flags or list(PROVIDER_IDS)

    selected = [summary_lookup[provider] for provider in requested if provider in summary_lookup]
    if selected:
        return selected

    if requested:
        labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in requested)
        raise ValueError(f"No usage data found for selected providers: {labels}")

    raise ValueError(get_merged_no_data_message())


def analyze_usage(values: CliArgValues, *, selection_mode: SelectionMode) -> AnalysisBundle:
    with stdout.status("Analyzing usage data..."):
        start, end = get_date_window()
        color_mode: ColorMode = "dark" if values.dark else "light"

        if values.providers:
            includes_all = "all" in values.providers
            requested_from_providers = [provider for provider in values.providers if provider != "all"]
            requested_providers = (
                list(PROVIDER_IDS)
                if includes_all
                else [cast(ProviderId, provider) for provider in requested_from_providers]
            )
            inspected_providers = list(PROVIDER_IDS) if includes_all else (requested_providers or list(PROVIDER_IDS))
        else:
            requested_providers = list(PROVIDER_IDS) if values.all else get_requested_providers(values)
            inspected_providers = requested_providers if requested_providers else list(PROVIDER_IDS)

        availability_by_provider = get_provider_availability(inspected_providers)
        aggregate_result = aggregate_usage(
            start=start,
            end=end,
            requested_providers=requested_providers,
        )

    for warning in aggregate_result.warnings:
        stderr.print(warning)

    print_provider_availability(availability_by_provider, inspected_providers)
    export_providers = get_output_providers(
        values,
        availability_by_provider,
        aggregate_result.rows_by_provider,
        end,
        selection_mode=selection_mode,
    )
    payload = build_export_payload(
        export_providers,
        start=start,
        end=end,
        color_mode=color_mode,
        rows_by_provider=aggregate_result.rows_by_provider,
    )
    return AnalysisBundle(
        start=start,
        end=end,
        color_mode=color_mode,
        inspected_providers=inspected_providers,
        availability_by_provider=availability_by_provider,
        aggregate_result=aggregate_result,
        export_providers=export_providers,
        payload=payload,
    )


def write_export(bundle: AnalysisBundle, values: CliArgValues) -> Path:
    fmt = infer_format(values.format, values.output)
    output_path = Path(values.output or get_default_output_path(values, fmt)).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        output_path.write_text(json.dumps(bundle.payload, indent=2) + "\n", encoding="utf-8")
    elif fmt == "html":
        output_path.write_text(render_html_document(bundle.payload), encoding="utf-8")
    else:
        sections = build_render_sections(bundle.export_providers, bundle.aggregate_result.rows_by_provider)
        if fmt == "svg":
            svg = render_usage_heatmaps_svg(
                start_date=bundle.start,
                end_date=bundle.end,
                sections=sections,
                color_mode=bundle.color_mode,
            )
            output_path.write_text(svg, encoding="utf-8")
        else:
            png_bytes = render_usage_heatmaps_png(
                start_date=bundle.start,
                end_date=bundle.end,
                sections=sections,
                color_mode=bundle.color_mode,
            )
            output_path.write_bytes(png_bytes)

    stdout.print("Analysis complete")
    print_run_summary(
        output_path,
        fmt,
        bundle.color_mode,
        bundle.start,
        bundle.end,
        [provider.provider for provider in bundle.export_providers],
    )
    return output_path


def run_export(values: CliArgValues) -> Path:
    bundle = analyze_usage(values, selection_mode="export")
    return write_export(bundle, values)


def get_default_bundle_output_path() -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"./slopmeter-bundle-{timestamp}.yaml"


def run_export_data(values: CliArgValues) -> Path:
    bundle = analyze_usage(values, selection_mode="export")
    provider_summaries = get_data_export_providers(values, bundle.aggregate_result.rows_by_provider)
    device_metadata = get_or_create_device_metadata()
    payload = build_bundle_payload(
        start=bundle.start,
        end=bundle.end,
        sources=[
            build_device_source(
                device_metadata,
                provider_summaries,
                generated_at=datetime.now(),
            )
        ],
    )
    output_path = Path(values.output or get_default_bundle_output_path()).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dump_yaml(payload), encoding="utf-8")
    stdout.print("Analysis complete")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "format": "yaml",
                "kind": payload["kind"],
                "sourceCount": len(payload["sources"]),
                "providers": [provider.provider for provider in provider_summaries],
            },
            indent=2,
        )
    )
    return output_path


def build_service_payload(payload: dict[str, object]) -> dict[str, object]:
    service_payload = dict(payload)
    service_payload["ui"] = {
        "storageKey": SERVICE_STORAGE_KEY,
        "export": {
            "endpoint": SERVICE_EXPORT_ENDPOINT,
            "format": "png",
        },
    }
    return service_payload


def build_service_png_export(
    bundle: AnalysisBundle,
    provider_ids: list[str],
) -> tuple[bytes, str]:
    normalized_provider_ids = normalize_usage_provider_ids(provider_ids)
    export_providers = get_output_providers_for_ids(
        normalized_provider_ids,
        bundle.aggregate_result.rows_by_provider,
        bundle.end,
    )
    sections = build_render_sections(export_providers, bundle.aggregate_result.rows_by_provider)
    png_bytes = render_usage_heatmaps_png(
        start_date=bundle.start,
        end_date=bundle.end,
        sections=sections,
        color_mode=bundle.color_mode,
    )
    return png_bytes, f"slopmeter_{'_'.join(normalized_provider_ids)}.png"


def run_serve(
    values: CliArgValues,
    *,
    host: str,
    port: int,
    strict_port: bool,
) -> str:
    bundle = analyze_usage(values, selection_mode="serve")
    document = render_html_document(build_service_payload(bundle.payload))
    server, url = create_html_server(
        document,
        host=host,
        port=port,
        strict_port=strict_port,
        export_png=lambda provider_ids: build_service_png_export(bundle, provider_ids),
    )

    stdout.print(f"Serving slopmeter at {url}")
    stdout.print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stdout.print("Stopping slopmeter")
    finally:
        server.server_close()
    return url


def handle_cli_error(error: Exception) -> None:
    stderr.print(f"Failed: {error}")
    raise typer.Exit(1) from error


def is_explicit_option(ctx: typer.Context, name: str) -> bool:
    return ctx.get_parameter_source(name) is not ParameterSource.DEFAULT


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535),
    providers: list[str] | None = typer.Option(None, "--provider", "-p"),
    dark: bool = typer.Option(False, "--dark"),
    all: bool = typer.Option(False, "--all"),
    amp: bool = typer.Option(False, "--amp"),
    claude: bool = typer.Option(False, "--claude"),
    codex: bool = typer.Option(False, "--codex"),
    cursor: bool = typer.Option(False, "--cursor"),
    gemini: bool = typer.Option(False, "--gemini"),
    opencode: bool = typer.Option(False, "--opencode"),
    pi: bool = typer.Option(False, "--pi"),
) -> None:
    if ctx.invoked_subcommand is not None:
        return

    values = build_cli_values(
        providers=providers,
        dark=dark,
        all=all,
        amp=amp,
        claude=claude,
        codex=codex,
        cursor=cursor,
        gemini=gemini,
        opencode=opencode,
        pi=pi,
    )
    try:
        run_serve(
            values,
            host=host,
            port=port,
            strict_port=is_explicit_option(ctx, "port"),
        )
    except Exception as error:  # pragma: no cover - top-level CLI guard
        handle_cli_error(error)


@app.command("serve")
def serve_command(
    ctx: typer.Context,
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535),
    providers: list[str] | None = typer.Option(None, "--provider", "-p"),
    dark: bool = typer.Option(False, "--dark"),
    all: bool = typer.Option(False, "--all"),
    amp: bool = typer.Option(False, "--amp"),
    claude: bool = typer.Option(False, "--claude"),
    codex: bool = typer.Option(False, "--codex"),
    cursor: bool = typer.Option(False, "--cursor"),
    gemini: bool = typer.Option(False, "--gemini"),
    opencode: bool = typer.Option(False, "--opencode"),
    pi: bool = typer.Option(False, "--pi"),
) -> None:
    values = build_cli_values(
        providers=providers,
        dark=dark,
        all=all,
        amp=amp,
        claude=claude,
        codex=codex,
        cursor=cursor,
        gemini=gemini,
        opencode=opencode,
        pi=pi,
    )
    try:
        run_serve(
            values,
            host=host,
            port=port,
            strict_port=is_explicit_option(ctx, "port"),
        )
    except Exception as error:  # pragma: no cover - top-level CLI guard
        handle_cli_error(error)


@app.command("export")
def export_command(
    output: str | None = typer.Option(None, "--output", "-o"),
    format: str | None = typer.Option(None, "--format", "-f"),
    providers: list[str] | None = typer.Option(None, "--provider", "-p"),
    dark: bool = typer.Option(False, "--dark"),
    all: bool = typer.Option(False, "--all"),
    amp: bool = typer.Option(False, "--amp"),
    claude: bool = typer.Option(False, "--claude"),
    codex: bool = typer.Option(False, "--codex"),
    cursor: bool = typer.Option(False, "--cursor"),
    gemini: bool = typer.Option(False, "--gemini"),
    opencode: bool = typer.Option(False, "--opencode"),
    pi: bool = typer.Option(False, "--pi"),
) -> None:
    values = build_cli_values(
        output=output,
        format=format,
        providers=providers,
        dark=dark,
        all=all,
        amp=amp,
        claude=claude,
        codex=codex,
        cursor=cursor,
        gemini=gemini,
        opencode=opencode,
        pi=pi,
    )
    try:
        run_export(values)
    except Exception as error:  # pragma: no cover - top-level CLI guard
        handle_cli_error(error)


@app.command("export-data")
def export_data_command(
    output: str | None = typer.Option(None, "--output", "-o"),
    providers: list[str] | None = typer.Option(None, "--provider", "-p"),
    all: bool = typer.Option(False, "--all"),
    amp: bool = typer.Option(False, "--amp"),
    claude: bool = typer.Option(False, "--claude"),
    codex: bool = typer.Option(False, "--codex"),
    cursor: bool = typer.Option(False, "--cursor"),
    gemini: bool = typer.Option(False, "--gemini"),
    opencode: bool = typer.Option(False, "--opencode"),
    pi: bool = typer.Option(False, "--pi"),
) -> None:
    values = build_cli_values(
        output=output,
        providers=providers,
        all=all,
        amp=amp,
        claude=claude,
        codex=codex,
        cursor=cursor,
        gemini=gemini,
        opencode=opencode,
        pi=pi,
    )
    try:
        run_export_data(values)
    except Exception as error:  # pragma: no cover - top-level CLI guard
        handle_cli_error(error)
