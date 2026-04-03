# slopmeter

[English](./README.md) | [简体中文](./README.zh-CN.md)

The primary README is in English. For a Chinese version, see [README.zh-CN.md](./README.zh-CN.md).

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
slopmeter serve --host 127.0.0.1 --port 9000
slopmeter export --format html --output ./out/heatmap.html
slopmeter export --codex --format json --output ./out/codex.json
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
- it does not save an HTML file unless you explicitly use `slopmeter export --format html`

Provider filters can be used with either `slopmeter` or `slopmeter export`:

```bash
slopmeter --claude
slopmeter --codex
slopmeter --all
slopmeter export --cursor --format svg --output ./out/cursor.svg
```

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

- `--all`
  Merge all detected providers into a single combined heatmap.
  If `--all` is set, individual provider flags are ignored for rendering.
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

If you do not pass any provider flag, `slopmeter` prefers the first available providers in this order:

1. `Claude Code`
2. `Codex`
3. `Cursor`
4. then the remaining providers if those are missing

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

- `--all`
  Merge all detected providers into one combined export.
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
