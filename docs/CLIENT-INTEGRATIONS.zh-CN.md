# Codex / Claude Code / OpenCode 接入教程

本文档说明如何把当前项目 `allcanuse-mcp` 接入到以下客户端：

- ChatGPT Codex / Codex CLI
- Claude Code
- OpenCode

以下内容基于 `2026-04-30` 查到的官方资料整理，重点覆盖当前项目最常用的 `stdio` 方式接入。

## 1. 接入前准备

无论接哪个客户端，先确保下面至少有一个启动方式可用。

### 方式一：直接从仓库启动

在项目根目录执行：

```bash
python run_server.py --transport stdio
```

### 方式二：安装后启动

```bash
pip install -e .
allcanuse-mcp
```

如果你现在还处于开发阶段，优先建议使用“仓库方式”，因为：

- 不需要先打包或发布
- 改完代码后可直接重启客户端继续测试
- 多数客户端都支持配置 `cwd` 或直接在项目目录下启动

## 2. ChatGPT Codex / Codex CLI 接入

### 配置文件位置

根据 OpenAI Codex 当前配置文档，MCP Server 配置写在：

```text
~/.codex/config.toml
```

当前文档中，MCP 相关配置位于 `mcp_servers` 下，每个服务一个表。

### 方式 A：直接从仓库运行

#### Windows 示例

```toml
[mcp_servers.allcanuse]
command = "python"
args = ["run_server.py", "--transport", "stdio"]
cwd = "D:/path/to/allcanuse"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180
```

#### Linux 示例

```toml
[mcp_servers.allcanuse]
command = "python"
args = ["run_server.py", "--transport", "stdio"]
cwd = "/path/to/allcanuse"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180
```

### 方式 B：安装后运行

```toml
[mcp_servers.allcanuse]
command = "allcanuse-mcp"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180
```

### 推荐补充项

如果你希望显式传环境变量，可以继续补：

```toml
[mcp_servers.allcanuse]
command = "python"
args = ["run_server.py", "--transport", "stdio"]
cwd = "D:/path/to/allcanuse"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180

[mcp_servers.allcanuse.env]
PYTHONIOENCODING = "utf-8"
```

如果你发现某些长时工具容易超时，优先增大：

- `startup_timeout_ms`
- `tool_timeout_sec`

同时，这个 MCP 自身很多网络类或长时工具还支持在工具调用参数里传 `timeout_ms`，两层超时都可以调。

### 接入后怎么验证

进入 Codex 后，建议先调用：

```text
list_all_tools()
```

然后继续调用：

```text
get_system_info()
get_desktop_context()
```

如果这些调用都能返回结果，说明 MCP 已经成功接通。

### 常见排查

- `config.toml` 写对了，但看不到服务：重启 Codex 会话后再试。
- `python` 找不到：改成 Python 的绝对路径。
- 仓库方式无法启动：检查 `cwd` 是否真的指向项目根目录。
- 工具容易超时：同时检查 Codex 侧 `tool_timeout_sec` 和工具参数里的 `timeout_ms`。

## 3. Claude Code 接入

根据 Claude Code 当前文档，常见做法有两种：

1. 用 `claude mcp add` 直接添加
2. 在项目根目录写 `.mcp.json`

### 方式 A：用 CLI 添加

#### 仅当前用户本地使用

```bash
claude mcp add --transport stdio allcanuse -- python run_server.py --transport stdio
```

#### 写入当前项目，便于项目内共享

```bash
claude mcp add --transport stdio --scope project allcanuse -- python run_server.py --transport stdio
```

如果你已经安装成命令行入口，也可以改成：

```bash
claude mcp add --transport stdio --scope project allcanuse -- allcanuse-mcp
```

### 方式 B：手写 `.mcp.json`

Claude Code 当前文档说明，项目级共享配置通常写在项目根目录：

```text
.mcp.json
```

#### 仓库方式示例

```json
{
  "mcpServers": {
    "allcanuse": {
      "type": "stdio",
      "command": "python",
      "args": ["run_server.py", "--transport", "stdio"],
      "env": {}
    }
  }
}
```

#### 安装后示例

```json
{
  "mcpServers": {
    "allcanuse": {
      "type": "stdio",
      "command": "allcanuse-mcp",
      "args": [],
      "env": {}
    }
  }
}
```

### Claude Code 里几个要点

- `local` 是常见默认 scope，只在你本机生效。
- `project` 会写到当前项目的 `.mcp.json`。
- `.mcp.json` 支持环境变量展开。
- 使用项目级 MCP 配置时，Claude Code 会提示审批或确认。

### 接入后怎么验证

在 Claude Code 中先让模型调用：

```text
list_all_tools()
```

然后再调用：

```text
get_system_info()
get_desktop_context()
```

如果你想让模型一次完成首轮验证，可以直接输入：

```text
先调用 list_all_tools，再调用 get_system_info 和 get_desktop_context。
```

### 常见排查

- 项目里写了 `.mcp.json` 但未生效：确认你打开的就是这个项目目录。
- `claude mcp add` 成功但工具没出现：重新进入会话再试。
- `python` 或 `allcanuse-mcp` 找不到：改成绝对路径。
- 某些工具报依赖缺失：按工具说明安装缺少的系统命令或 Python 包。

## 4. OpenCode 接入

根据 OpenCode 当前文档，MCP Server 配置写在 OpenCode 配置文件的 `mcp` 字段下。

文档给出的基础结构类似：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "server-name": {
      "type": "local",
      "command": ["npx", "-y", "some-mcp-server"],
      "enabled": true
    }
  }
}
```

这意味着 OpenCode 不是单独写 `mcp.json`，而是写到它自己的配置文件里。文档中给出的文件名是 `opencode.json`，也支持 `opencode.jsonc`。

### 仓库方式接入

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "allcanuse": {
      "type": "local",
      "command": ["python", "run_server.py", "--transport", "stdio"],
      "enabled": true
    }
  }
}
```

### 安装后接入

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "allcanuse": {
      "type": "local",
      "command": ["allcanuse-mcp"],
      "enabled": true
    }
  }
}
```

### 可选环境变量和超时

如果你需要补环境变量，可以写：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "allcanuse": {
      "type": "local",
      "command": ["python", "run_server.py", "--transport", "stdio"],
      "enabled": true,
      "environment": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

如果你的 OpenCode 版本支持 MCP 级超时配置，建议把超时放在客户端侧配置；如果没有，就优先在调用本项目网络类工具时显式传 `timeout_ms`。

### OpenCode 的几个要点

- OpenCode 文档强调，启用的 MCP 越多，占用的上下文越多。
- 这个项目工具很多，建议服务名统一用 `allcanuse`，避免模型混淆。
- 仓库方式如果依赖当前目录，建议从项目根目录启动 OpenCode，或者改成绝对路径命令。

### 接入后怎么验证

进入 OpenCode 后，先调用：

```text
list_all_tools()
```

再调用：

```text
get_system_info()
get_desktop_context()
```

## 5. 推荐接入顺序

如果你当前处于开发和测试阶段，建议按下面顺序使用：

1. LM Studio：最适合先验证 `stdio` 启动链路。
2. Claude Code：项目级 `.mcp.json` 便于共享和复测。
3. Codex / Codex CLI：适合把 MCP 纳入长期本地工具链。
4. OpenCode：适合补充另一类本地 Agent 工作流。

如果以后你把项目发布为可直接安装的包，三类客户端都建议统一切换到：

```text
allcanuse-mcp
```

这样配置更短，也更稳定。

## 6. 建议的首次验证流程

无论接入哪个客户端，第一次都建议按这个顺序验证：

1. 调 `list_all_tools()`
2. 调 `get_system_info()`
3. 调 `get_desktop_context()`
4. 调 `get_network_config(timeout_ms=60000)`

如果这四步都正常，基本可以说明：

- MCP Server 已成功启动
- 工具列表已正确暴露
- 系统信息类工具正常
- 桌面上下文和窗口类工具正常
- 网络相关工具正常

## 7. 依赖与故障排查

### `python` 找不到

把配置里的 `python` 改成 Python 可执行文件绝对路径。

### 启动了但没有工具

优先检查：

- 是否真的以 `stdio` 模式启动
- `run_server.py` 是否存在
- 启动目录是否正确
- 客户端是否需要重启会话

### 摄像头、窗口、截图类工具不可用

先确认 MCP 已经接通，再检查依赖：

- 摄像头通常依赖 `opencv-python`
- Linux 窗口枚举通常依赖 `wmctrl`
- Linux 前台窗口查询通常依赖 `xprop`
- Linux 截图通常依赖 `gnome-screenshot`、`scrot` 或 `imagemagick`

### 某些网络或长时工具超时

优先做两件事：

- 在客户端配置里调大 MCP 启动或工具超时
- 在具体工具调用时传更大的 `timeout_ms`

## 8. 参考文档

- OpenAI Codex 配置参考：
  https://developers.openai.com/codex/config-reference
- OpenAI Codex 开源仓库：
  https://github.com/openai/codex
- Claude Code MCP 文档：
  https://code.claude.com/docs/en/mcp
- OpenCode MCP 文档：
  https://opencode.ai/docs/zh-cn/mcp-servers/
