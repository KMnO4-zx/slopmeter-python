from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import typer
from click.core import ParameterSource
from rich.console import Console

from .export import build_json_export, to_json_provider_summary
from .models import ColorMode, UsageSummary
from .output_path import ProviderSelectionValues, get_default_output_path
from .provider_meta import DEFAULT_PROVIDER_IDS, PROVIDER_IDS, PROVIDER_STATUS_LABEL
from .providers import AggregateUsageResult, aggregate_usage, get_provider_availability, merge_provider_usage
from .render import HEATMAP_THEMES, RenderSection, render_html_document, render_usage_heatmaps_png, render_usage_heatmaps_svg
from .server import create_html_server
from .utils import format_local_date

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
    inspected_providers: list[str]
    availability_by_provider: dict[str, bool]
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


def build_cli_values(
    *,
    output: str | None = None,
    format: str | None = None,
    dark: bool = False,
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


def print_provider_availability(availability_by_provider: dict[str, bool], providers: list[str]) -> None:
    for provider in providers:
        status = "available" if availability_by_provider[provider] else "not available"
        print(f"{PROVIDER_STATUS_LABEL[provider]} {status}")


def get_requested_providers(values: ProviderSelectionValues) -> list[str]:
    return [provider for provider in PROVIDER_IDS if getattr(values, provider)]


def get_merged_no_data_message() -> str:
    return "No usage data found for Amp, Claude Code, Codex, Cursor, Gemini CLI, Open Code, or Pi Coding Agent."


def get_requested_missing_providers_message(missing: list[str]) -> str:
    labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in missing)
    return f"Requested provider data not found: {labels}"


def get_default_output_provider_ids(rows_by_provider: dict[str, UsageSummary | None]) -> list[str]:
    selected: list[str] = []
    fallback_providers = [provider for provider in PROVIDER_IDS if provider not in DEFAULT_PROVIDER_IDS]

    for provider in [*DEFAULT_PROVIDER_IDS, *fallback_providers]:
        if rows_by_provider.get(provider) is None or provider in selected:
            continue
        selected.append(provider)
        if len(selected) == 3:
            return selected

    return selected


def get_merged_provider_title(rows_by_provider: dict[str, UsageSummary | None]) -> str:
    return " / ".join(
        HEATMAP_THEMES[provider].title
        for provider in PROVIDER_IDS
        if rows_by_provider.get(provider) is not None
    )


def select_providers_to_render(
    availability_by_provider: dict[str, bool],
    rows_by_provider: dict[str, UsageSummary | None],
    requested: list[str],
) -> list[UsageSummary]:
    default_providers = get_default_output_provider_ids(rows_by_provider)
    providers_to_render = (
        [provider for provider in requested if rows_by_provider.get(provider)]
        if requested
        else [provider for provider in default_providers if rows_by_provider.get(provider)]
    )

    if requested and len(providers_to_render) < len(requested):
        missing = [provider for provider in requested if not rows_by_provider.get(provider)]
        raise ValueError(get_requested_missing_providers_message(missing))

    if not providers_to_render:
        available_providers = [provider for provider in PROVIDER_IDS if availability_by_provider[provider]]
        if available_providers:
            available_labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in available_providers)
            default_labels = ", ".join(PROVIDER_STATUS_LABEL[provider] for provider in DEFAULT_PROVIDER_IDS)
            raise ValueError(
                "No usage data found for available providers "
                f"({available_labels}). Preferred order is {default_labels}. "
                "Use --all or specify providers explicitly."
            )
        raise ValueError(get_merged_no_data_message())

    return [rows_by_provider[provider] for provider in providers_to_render if rows_by_provider[provider]]


def get_output_providers(
    values: ProviderSelectionValues,
    availability_by_provider: dict[str, bool],
    rows_by_provider: dict[str, UsageSummary | None],
    end: datetime,
) -> list[UsageSummary]:
    if not values.all:
        return select_providers_to_render(
            availability_by_provider,
            rows_by_provider,
            get_requested_providers(values),
        )

    merged = merge_provider_usage(rows_by_provider, end)
    if merged is None:
        raise ValueError(get_merged_no_data_message())
    return [merged]


def print_run_summary(
    output_path: Path,
    fmt: str,
    color_mode: ColorMode,
    start_date: datetime,
    end_date: datetime,
    rendered: list[str],
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
    rows_by_provider: dict[str, UsageSummary | None],
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
    rows_by_provider: dict[str, UsageSummary | None],
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
    return build_json_export(
        start=start,
        end=end,
        color_mode=color_mode,
        providers=providers,
    )


def analyze_usage(values: CliArgValues) -> AnalysisBundle:
    with stdout.status("Analyzing usage data..."):
        start, end = get_date_window()
        color_mode: ColorMode = "dark" if values.dark else "light"
        requested_providers = PROVIDER_IDS if values.all else get_requested_providers(values)
        inspected_providers = requested_providers if requested_providers else PROVIDER_IDS
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
    bundle = analyze_usage(values)
    return write_export(bundle, values)


def run_serve(
    values: CliArgValues,
    *,
    host: str,
    port: int,
    strict_port: bool,
) -> str:
    bundle = analyze_usage(values)
    document = render_html_document(bundle.payload)
    server, url = create_html_server(
        document,
        host=host,
        port=port,
        strict_port=strict_port,
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
