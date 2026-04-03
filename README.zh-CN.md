# slopmeter

[English](./README.md) | [简体中文](./README.zh-CN.md)

英文主文档请见 [README.md](./README.md)。

这是一个用于展示 AI 编码工具使用热力图，并提供本地网页查看器的工具。

## 安装

### 方式 1：直接在仓库里运行

适合本地开发，或者你只是想从源码直接试用。

```bash
uv sync
```

然后通过 `uv run` 运行：

```bash
uv run slopmeter
```

### 方式 2：安装到当前 Python 虚拟环境

适合你想在当前 virtualenv 里直接使用 `slopmeter` 命令。

```bash
uv pip install .
```

### 方式 3：安装成独立 CLI 工具

适合你想把 `slopmeter` 直接放到 shell 的 `PATH` 里。

```bash
uv tool install .
```

如果你使用 `uv pip install .` 或 `uv tool install .` 安装完成，之后就可以直接运行 `slopmeter`，不需要再写 `uv run`。

## 快速开始

启动本地网页界面：

```bash
slopmeter
```

默认会启动一个本地 HTTP 服务，地址从 `127.0.0.1:8000` 开始，并在终端打印最终访问地址。如果 `8000` 已被占用，会自动尝试下一个可用端口。

常用示例：

```bash
slopmeter --codex --dark
slopmeter serve --host 127.0.0.1 --port 9000
slopmeter export --format html --output ./out/heatmap.html
slopmeter export --codex --format json --output ./out/codex.json
slopmeter export --all --dark --format png --output ./out/all.png
```

## CLI 行为

- `slopmeter`
  启动本地网页服务。
- `slopmeter serve`
  和 `slopmeter` 一样，只是显式写出 `serve` 子命令。
- `slopmeter export`
  不启动服务，而是把结果导出到文件。

当你运行 `slopmeter` 或 `slopmeter serve` 时：

- 程序会在启动时扫描一次 provider 数据
- 在内存里生成一份 HTML 快照
- 通过 HTTP 服务把这份快照提供给浏览器
- 默认不会把 HTML 保存到本地文件，除非你显式使用 `slopmeter export --format html`

无论是 `slopmeter` 还是 `slopmeter export`，都可以使用 provider 过滤参数：

```bash
slopmeter --claude
slopmeter --codex
slopmeter --all
slopmeter export --cursor --format svg --output ./out/cursor.svg
```

## 参数说明

### `slopmeter` / `slopmeter serve`

这些参数用于控制本地网页服务。

- `--host`
  本地 HTTP 服务绑定地址。
  默认值：`127.0.0.1`
  示例：`slopmeter serve --host 0.0.0.0`

- `--port`
  本地 HTTP 服务端口。
  默认值：`8000`
  行为：
  如果你没有显式传 `--port`，程序会从 `8000` 开始尝试，并在端口被占用时自动换到下一个可用端口。
  如果你显式传了 `--port`，那么必须绑定这个端口；如果该端口已被占用，命令会直接失败。
  示例：`slopmeter serve --port 9000`

- `--dark`
  使用深色主题渲染网页。
  示例：`slopmeter --dark`

- `--all`
  把所有检测到的 provider 合并成一张总热力图。
  如果设置了 `--all`，单独的 provider 参数在渲染时会被忽略。
  示例：`slopmeter --all`

- `--amp`
  只展示 Amp 使用数据。
  示例：`slopmeter --amp`

- `--claude`
  只展示 Claude Code 使用数据。
  示例：`slopmeter --claude`

- `--codex`
  只展示 Codex 使用数据。
  示例：`slopmeter --codex`

- `--cursor`
  只展示 Cursor 使用数据。
  示例：`slopmeter --cursor`

- `--gemini`
  只展示 Gemini CLI 使用数据。
  示例：`slopmeter --gemini`

- `--opencode`
  只展示 Open Code 使用数据。
  示例：`slopmeter --opencode`

- `--pi`
  只展示 Pi Coding Agent 使用数据。
  示例：`slopmeter --pi`

如果你没有传任何 provider 参数，`slopmeter` 会优先按下面的顺序选择可用 provider：

1. `Claude Code`
2. `Codex`
3. `Cursor`
4. 如果这些没有数据，再依次尝试其他 provider

### `slopmeter export`

这些参数用于控制导出行为。

- `--output`, `-o`
  输出文件路径。
  如果省略，会自动生成默认文件名，例如 `./heatmap-last-year.png` 或 `./heatmap-last-year_codex.json`。
  示例：`slopmeter export --format html --output ./out/heatmap.html`

- `--format`, `-f`
  导出格式。
  支持：`png`、`svg`、`json`、`html`
  如果省略，会优先根据输出文件扩展名推断；如果无法推断，则默认使用 `png`。
  示例：`slopmeter export --format svg --output ./out/heatmap.svg`

- `--dark`
  使用深色主题导出。
  示例：`slopmeter export --dark --format png --output ./out/dark.png`

- `--all`
  把所有检测到的 provider 合并成一个导出结果。
  示例：`slopmeter export --all --format html --output ./out/all.html`

- `--amp`
  只导出 Amp 使用数据。

- `--claude`
  只导出 Claude Code 使用数据。

- `--codex`
  只导出 Codex 使用数据。

- `--cursor`
  只导出 Cursor 使用数据。

- `--gemini`
  只导出 Gemini CLI 使用数据。

- `--opencode`
  只导出 Open Code 使用数据。

- `--pi`
  只导出 Pi Coding Agent 使用数据。

示例：

```bash
slopmeter export --codex --format json --output ./out/codex.json
slopmeter export --cursor --format svg --output ./out/cursor.svg
slopmeter export --all --dark --format png --output ./out/all.png
slopmeter export --claude --format html --output ./out/claude.html
```

## 输出格式

- `png`
- `svg`
- `json`
- `html`

导出的 HTML 是一个自包含文件，包含每日格子的 hover tooltip。

## 帮助

```bash
slopmeter --help
slopmeter serve --help
slopmeter export --help
```
