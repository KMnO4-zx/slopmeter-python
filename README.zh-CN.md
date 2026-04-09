# slopmeter

![Example heatmap](https://raw.githubusercontent.com/KMnO4-zx/slopmeter-python/master/images/slopmeter_all.png)

<p align="center">
  <a href="https://github.com/KMnO4-zx/slopmeter-python/blob/master/README.md">English</a> | <a href="https://github.com/KMnO4-zx/slopmeter-python/blob/master/README.zh-CN.md">简体中文</a>
</p>

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

### 方式 4：从 PyPI 安装已发布版本

适合你想直接安装 PyPI 上已经发布的正式版本。

```bash
uv tool install slopmeter
```

后续升级可以使用：

```bash
uv tool upgrade slopmeter
```

## 快速开始

启动本地网页界面：

```bash
slopmeter
```

默认会启动一个本地 HTTP 服务，地址从 `127.0.0.1:8000` 开始，并在终端打印最终访问地址。如果 `8000` 已被占用，会自动尝试下一个可用端口。

常用示例：

```bash
slopmeter --codex --dark
slopmeter --provider all,claude,codex
slopmeter serve --host 127.0.0.1 --port 9000
slopmeter export --format html --output ./out/heatmap.html
slopmeter export --codex --format json --output ./out/codex.json
slopmeter export --provider all,opencode,codex --format png --output ./out/custom.png
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
- 默认先显示 `all` 聚合卡片，再显示所有有数据的单渠道卡片
- 页面里的渠道卡片可以拖拽排序
- 当前页面顺序和导出勾选状态会保存在本机浏览器的 localStorage
- 页面可以把当前勾选的卡片按当前顺序导出成一张 PNG
- 默认不会把 HTML 保存到本地文件，除非你显式使用 `slopmeter export --format html`

无论是 `slopmeter` 还是 `slopmeter export`，都可以使用有序的 provider 选择参数：

```bash
slopmeter --provider all,claude,codex
slopmeter export --provider all,opencode,codex --format png --output ./out/custom.png
```

旧的 provider 布尔参数仍然可用：

```bash
slopmeter --claude
slopmeter --codex
slopmeter export --cursor --format svg --output ./out/cursor.svg
```

## 选择规则

- `all` 永远表示“当前检测到且有数据的所有渠道总和”，不是“同一条命令里其他显式写出来的渠道之和”。
- 如果 `--provider` 里同时包含存在和不存在的渠道，不存在的渠道会被直接跳过；只有当你选的渠道一个都没有可用数据时，命令才会失败。
- 在网页里，排序只能从 `Drag` 手柄开始；`Export PNG` 导出的内容始终以当前页面顺序和当前勾选状态为准。

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

- `--provider`, `-p`
  按顺序加入一个 provider，或者一次传入一个 provider 列表。
  你可以传单个值，例如 `--provider codex`，也可以传逗号分隔的列表，例如 `--provider all,claude,codex`。
  这个参数仍然可以重复传，多次出现时会按顺序继续追加。
  支持的值：`all`、`amp`、`claude`、`codex`、`cursor`、`gemini`、`opencode`、`pi`
  只要传了任意 `--provider`，它就会优先于旧的 `--all` 和各个单独 provider 布尔参数。
  示例：`slopmeter --provider all,claude,codex`

- `--all`
  兼容旧行为的参数。
  把所有检测到的 provider 合并成一张总热力图。
  如果你想让 `all` 和其他渠道一起出现并参与排序，请使用 `--provider all`。
  这里的 `all` 永远表示“所有已检测到且有数据的渠道总和”，不是“同一条命令里其他显式写出来的渠道之和”。
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

如果你没有传任何 provider 选择参数，`slopmeter` 会按下面的顺序显示所有有数据的卡片：

1. `all`
2. `Claude Code`
3. `Codex`
4. `Open Code`
5. `Cursor`
6. 再接其他有数据的 provider

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

- `--provider`, `-p`
  按顺序加入一个 provider，或者一次传入一个 provider 列表。
  你可以传单个值，例如 `--provider codex`，也可以传逗号分隔的列表，例如 `--provider all,opencode,codex`。
  这个参数仍然可以重复传，多次出现时会按顺序继续追加。
  支持的值：`all`、`amp`、`claude`、`codex`、`cursor`、`gemini`、`opencode`、`pi`
  示例：`slopmeter export --provider all,opencode,codex --format png --output ./out/custom.png`

- `--all`
  兼容旧行为的参数。
  把所有检测到的 provider 合并成一个导出结果。
  如果你想让 `all` 和其他渠道一起导出，请使用 `--provider all`。
  这里的 `all` 永远表示“所有已检测到且有数据的渠道总和”，不是“同一条命令里其他显式写出来的渠道之和”。
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
slopmeter export --provider all,opencode,codex --format png --output ./out/custom.png
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

## 参考

本项目来自 [JeanMeijer/slopmeter](https://github.com/JeanMeijer/slopmeter) 的 Python 版本，感谢原作者的创意和实现。

## Roadmap

- [ ] 支持同一用户在多台设备之间聚合 usage，并且不依赖中心服务器，同时尽量保持隐私友好。
  - 计划优先采用“用户显式触发、用户自己控制”的同步方式，例如加密导入/导出包，或基于用户自有同步目录的合并。
  - 默认行为仍应保持为纯本地：不做后台同步、不做 telemetry、也不会自动上传到任何服务器。
  - 主要难点在于去重、时间偏差，以及跨 provider / 跨设备时保持稳定的合并格式。
