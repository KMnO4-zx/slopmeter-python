# slopmeter-python

Python rewrite of the `slopmeter` CLI.

## Setup

```bash
uv sync
```

## Usage

```bash
uv run slopmeter --format html --output ./out/heatmap.html
uv run slopmeter --codex --format json --output ./out/codex.json
uv run slopmeter --all --dark --format png --output ./out/all.png
```

## Output formats

- `png`
- `svg`
- `json`
- `html`

The HTML export is self-contained and includes hover tooltips for each day cell.

