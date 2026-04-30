# allcanuse-mcp 发布后使用教程

本文档面向最终用户，默认你拿到的是已经整理好的源码仓库、打包产物，或团队内部发放的安装来源，目标是尽量做到安装后直接接入使用。

如果你当前还在源码仓库里开发，请优先看：

- [USAGE.zh-CN.md](./USAGE.zh-CN.md)
- [LM-STUDIO.zh-CN.md](./LM-STUDIO.zh-CN.md)
- [CLIENT-INTEGRATIONS.zh-CN.md](./CLIENT-INTEGRATIONS.zh-CN.md)

## 1. 安装

### 方式一：从源码仓库直接安装

如果你拿到的是 Git 仓库地址：

```bash
pip install git+https://your-repo-url.git
```

如果你已经把仓库克隆到本地：

```bash
pip install -e .
```

### 方式二：从本地构建产物安装

如果你拿到的是别人打好的 wheel：

```bash
pip install allcanuse_mcp-0.1.0-py3-none-any.whl
```

安装完成后，优先确认入口命令可用：

```bash
allcanuse-mcp --transport stdio
```

如果命令能正常启动，说明客户端后续可以直接通过这个入口接入。

### 方式三：不安装，直接从仓库运行

如果你不想装到当前 Python 环境，也可以直接在项目根目录运行：

```bash
python run_server.py --transport stdio
```

这种方式更适合开发、调试、实验环境。

## 2. 系统要求

- Windows 或 Linux
- Python 3.11 及以上

以下依赖不是启动必需，但某些功能会用到：

- `opencv-python`
  - 摄像头枚举和拍照
- `wmctrl`
  - Linux 窗口枚举
- `xprop`
  - Linux 前台窗口查询
- `gnome-screenshot` / `scrot` / `imagemagick`
  - Linux 截图

## 3. LM Studio 接入

在 LM Studio 中打开 `mcp.json` 后，可直接填写：

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "allcanuse-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

如果你的环境里 `allcanuse-mcp` 不在 PATH 中，就改成绝对路径。

### Windows 绝对路径示例

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "C:/Users/yourname/AppData/Local/Programs/Python/Python312/Scripts/allcanuse-mcp.exe",
      "args": ["--transport", "stdio"]
    }
  }
}
```

### Linux 绝对路径示例

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "/home/yourname/.local/bin/allcanuse-mcp",
      "args": ["--transport", "stdio"]
    }
  }
}
```

接入后，建议先让模型调用：

```text
list_all_tools()
```

## 4. ChatGPT Codex / Codex CLI 接入

把以下内容写入：

```text
~/.codex/config.toml
```

示例：

```toml
[mcp_servers.allcanuse]
command = "allcanuse-mcp"
args = ["--transport", "stdio"]
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180
```

如果命令不在 PATH 中，也可以改成绝对路径：

```toml
[mcp_servers.allcanuse]
command = "C:/Users/yourname/AppData/Local/Programs/Python/Python312/Scripts/allcanuse-mcp.exe"
args = ["--transport", "stdio"]
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180
```

首次接入后建议先测试：

```text
list_all_tools()
get_system_info()
```

## 5. Claude Code 接入

### 方式一：CLI 添加

```bash
claude mcp add --transport stdio --scope project allcanuse -- allcanuse-mcp --transport stdio
```

### 方式二：项目根目录 `.mcp.json`

```json
{
  "mcpServers": {
    "allcanuse": {
      "type": "stdio",
      "command": "allcanuse-mcp",
      "args": ["--transport", "stdio"],
      "env": {}
    }
  }
}
```

如果你不想共享给项目其他人，也可以不加 `--scope project`，只在本机当前用户范围内使用。

## 6. OpenCode 接入

在 OpenCode 的 `opencode.json` 或 `opencode.jsonc` 中加入：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "allcanuse": {
      "type": "local",
      "command": ["allcanuse-mcp", "--transport", "stdio"],
      "enabled": true
    }
  }
}
```

如果你需要环境变量，也可以继续写：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "allcanuse": {
      "type": "local",
      "command": ["allcanuse-mcp", "--transport", "stdio"],
      "enabled": true,
      "environment": {
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

## 7. 建议的首次验证流程

无论你接到哪个客户端，第一次都建议这样验证：

1. 调 `list_all_tools()`
2. 调 `get_system_info()`
3. 调 `get_desktop_context()`
4. 调 `get_network_config(timeout_ms=60000)`

如果这四步都成功，基本说明安装、启动、工具注册和主要能力都已正常。

## 8. 模型缺依赖时怎么办

当前项目允许模型自行调用已有工具补安装缺失依赖。

例如：

```text
run_shell(command="pip install opencv-python")
```

Linux 下也可以：

```text
run_shell(command="apt install -y wmctrl xprop")
```

也就是说，模型发现某些工具缺依赖时，可以直接先安装再继续执行任务。

## 9. 常见问题

### `allcanuse-mcp` 找不到

说明它不在 PATH 中。处理方式：

- 改成绝对路径
- 或重新确认 `pip install` 的 Python 环境是否和当前客户端使用的是同一套环境

### 工具接入成功但部分功能不可用

先区分两类问题：

- MCP 没启动成功
- MCP 已启动，但当前机器缺少可选依赖

通常摄像头、Linux 窗口、Linux 截图类问题都属于第二类。

### 网络类工具容易超时

优先做两件事：

- 在客户端配置里调大工具超时
- 在工具调用里显式传更大的 `timeout_ms`

## 10. 推荐给最终用户的最简方案

如果你只想要一套最省事的接法，优先推荐：

1. `pip install -e .` 或安装团队提供的 wheel
2. 在客户端里把命令写成 `allcanuse-mcp --transport stdio`
3. 进入会话后先调用 `list_all_tools()`

这通常就是最短路径。
