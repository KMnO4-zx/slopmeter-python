# slopmeter

![Example heatmap](https://raw.githubusercontent.com/KMnO4-zx/slopmeter-python/master/images/slopmeter_all.png)

<p align="center">
  <a href="./README.md">English</a> | <a href="./README.zh-CN.md">简体中文</a>
</p>


Local usage heatmaps and a web viewer for AI coding tools.

## Install

### Option 1: Run from this repo

Use this when you are developing locally or just want to try the project from source.

```bash
uv sync
```

Then run commands through `uv run`:

```bash
uv run slopmeter
```

### Option 2: Install the CLI into your current Python environment

Use this when you want the `slopmeter` command available inside an existing virtualenv.

```bash
uv pip install .
```

### Option 3: Install it as a standalone CLI tool

Use this when you want `slopmeter` available on your shell `PATH`.

```bash
uv tool install .
```

After installing with `uv pip install .` or `uv tool install .`, you can run `slopmeter` directly without `uv run`.

## Quick Start

Start the local web UI:

```bash
slopmeter
```

This starts a local HTTP server on `127.0.0.1:8000` by default and prints the final URL in the terminal. If port `8000` is already in use, it automatically picks the next available port.

Common variants:

```bash
slopmeter --codex --dark
slopmeter --provider all,claude,codex
slopmeter serve --host 127.0.0.1 --port 9000
slopmeter export --format html --output ./out/heatmap.html
slopmeter export --codex --format json --output ./out/codex.json
slopmeter export --provider all,claude,codex --format png --output ./out/custom.png
slopmeter export --all --dark --format png --output ./out/all.png
```

## CLI Behavior

- `slopmeter`
  Starts the local web server.
- `slopmeter serve`
  Explicit form of the same local server command.
- `slopmeter export`
  Writes a file to disk instead of starting a server.

When you run `slopmeter` or `slopmeter serve`:

- the app scans provider data once at startup
- it renders one HTML snapshot in memory
- it serves that snapshot over HTTP
- it shows `all` first, then all available provider cards
- provider cards can be drag-sorted in the page
- the current page order and export selection are saved in local browser storage
- the page can export the currently selected cards as one PNG
- it does not save an HTML file unless you explicitly use `slopmeter export --format html`

Ordered provider selection can be used with either `slopmeter` or `slopmeter export`:

```bash
slopmeter --provider all,claude,codex
slopmeter export --provider all,opencode,codex --format png --output ./out/custom.png
```

Legacy provider flags are still supported:

```bash
slopmeter --claude
slopmeter --codex
slopmeter export --cursor --format svg --output ./out/cursor.svg
```

## Selection Notes

- `all` always means the aggregate of every detected provider that currently has data. It does not mean “the sum of the other providers named in the same command”.
- If you pass `--provider` with a mix of existing and missing providers, missing providers are skipped. The command fails only when none of the selected providers have usable data.
- In the web UI, drag sorting starts from the `Drag` handle, and the current order plus checked cards are what `Export PNG` uses.

## Parameters

### `slopmeter` / `slopmeter serve`

These options control the local web server.

- `--host`
  Bind address for the local HTTP server.
  Default: `127.0.0.1`
  Example: `slopmeter serve --host 0.0.0.0`

- `--port`
  Port for the local HTTP server.
  Default: `8000`
  Behavior:
  If you do not pass `--port`, `slopmeter` starts from `8000` and automatically moves to the next free port if needed.
  If you do pass `--port`, that exact port is required; if it is already in use, the command fails.
  Example: `slopmeter serve --port 9000`

- `--dark`
  Render the web UI in dark mode.
  Example: `slopmeter --dark`

- `--provider`, `-p`
  Add one provider or one ordered provider list to the render/export selection.
  You can pass a single provider such as `--provider codex`, or a comma-separated list such as `--provider all,claude,codex`.
  Repeating `--provider` still works and appends more providers in order.
  Supported values: `all`, `amp`, `claude`, `codex`, `cursor`, `gemini`, `opencode`, `pi`
  If any `--provider` is passed, it takes priority over the legacy `--all` and per-provider boolean flags.
  Example: `slopmeter --provider all,claude,codex`

- `--all`
  Legacy compatibility flag.
  Merge all detected providers into a single combined heatmap.
  Use `--provider all` when you want `all` to appear alongside other providers and participate in ordering.
  `all` always means the total across every detected provider with data, not just the other providers named in the same command.
  Example: `slopmeter --all`

- `--amp`
  Only render Amp usage.
  Example: `slopmeter --amp`

- `--claude`
  Only render Claude Code usage.
  Example: `slopmeter --claude`

- `--codex`
  Only render Codex usage.
  Example: `slopmeter --codex`

- `--cursor`
  Only render Cursor usage.
  Example: `slopmeter --cursor`

- `--gemini`
  Only render Gemini CLI usage.
  Example: `slopmeter --gemini`

- `--opencode`
  Only render Open Code usage.
  Example: `slopmeter --opencode`

- `--pi`
  Only render Pi Coding Agent usage.
  Example: `slopmeter --pi`

If you do not pass any provider selector, `slopmeter` shows all available cards in this order:

1. `all`
2. `Claude Code`
3. `Codex`
4. `Open Code`
5. `Cursor`
6. then the remaining available providers

### `slopmeter export`

These options control file export.

- `--output`, `-o`
  Output file path.
  If omitted, a default file name is used such as `./heatmap-last-year.png` or `./heatmap-last-year_codex.json`.
  Example: `slopmeter export --format html --output ./out/heatmap.html`

- `--format`, `-f`
  Export format.
  Supported values: `png`, `svg`, `json`, `html`
  If omitted, the format is inferred from the output extension when possible; otherwise it defaults to `png`.
  Example: `slopmeter export --format svg --output ./out/heatmap.svg`

- `--dark`
  Export using dark theme colors.
  Example: `slopmeter export --dark --format png --output ./out/dark.png`

- `--provider`, `-p`
  Add one provider or one ordered provider list to the export selection.
  You can pass a single provider such as `--provider codex`, or a comma-separated list such as `--provider all,opencode,codex`.
  Repeating `--provider` still works and appends more providers in order.
  Supported values: `all`, `amp`, `claude`, `codex`, `cursor`, `gemini`, `opencode`, `pi`
  Missing providers are skipped as long as at least one requested provider has data.
  Example: `slopmeter export --provider all,opencode,codex --format png --output ./out/custom.png`

- `--all`
  Legacy compatibility flag.
  Merge all detected providers into one combined export.
  Use `--provider all` when you want `all` to be exported together with other providers.
  `all` always means the total across every detected provider with data, not just the other providers named in the same command.
  Example: `slopmeter export --all --format html --output ./out/all.html`

- `--amp`
  Export Amp usage only.

- `--claude`
  Export Claude Code usage only.

- `--codex`
  Export Codex usage only.

- `--cursor`
  Export Cursor usage only.

- `--gemini`
  Export Gemini CLI usage only.

- `--opencode`
  Export Open Code usage only.

- `--pi`
  Export Pi Coding Agent usage only.

Examples:

```bash
slopmeter export --codex --format json --output ./out/codex.json
slopmeter export --cursor --format svg --output ./out/cursor.svg
slopmeter export --provider all,opencode,codex --format png --output ./out/custom.png
slopmeter export --all --dark --format png --output ./out/all.png
slopmeter export --claude --format html --output ./out/claude.html
```

## Output Formats

- `png`
- `svg`
- `json`
- `html`

The HTML export is self-contained and includes hover tooltips for each day cell.

## Help

```bash
slopmeter --help
slopmeter serve --help
slopmeter export --help
```

## Credits

This project is a Python adaptation of [JeanMeijer/slopmeter](https://github.com/JeanMeijer/slopmeter). Credit to the original author for the idea and implementation.
