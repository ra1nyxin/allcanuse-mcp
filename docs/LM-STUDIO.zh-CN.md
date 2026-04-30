# LM Studio 接入教程

## 1. 适用版本

根据 LM Studio 官方文档，LM Studio 从 `0.3.17` 开始支持作为 MCP Host 使用，并支持通过 `mcp.json` 添加本地或远程 MCP Server。

如果你要通过 API 使用 MCP，官方文档说明相关能力需要 `0.4.0` 或更新版本。

## 2. 在 LM Studio 里打开 `mcp.json`

LM Studio 官方文档给出的路径是：

1. 打开 LM Studio
2. 进入右侧边栏的 `Program`
3. 点击 `Install`
4. 点击 `Edit mcp.json`

这会打开 LM Studio 内置的 `mcp.json` 编辑器。

## 3. 本地项目接入方式

### 方案 A：直接从仓库运行

如果你当前就是在这个仓库里开发，推荐这样写。

### Windows 示例

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "python",
      "args": ["run_server.py", "--transport", "stdio"],
      "cwd": "D:/path/to/allcanuse"
    }
  }
}
```

### Linux 示例

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "python",
      "args": ["run_server.py", "--transport", "stdio"],
      "cwd": "/path/to/allcanuse"
    }
  }
}
```

这套写法的好处是：

- 不要求用户自己配置 `PYTHONPATH`
- 不要求用户修改脚本入口
- 只要 `cwd` 指向仓库根目录即可

## 4. 发布后推荐接入方式

如果以后你已经发布成包，并且用户机器上已经安装了这个包，推荐用更短的配置。

### Windows / Linux 通用

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "allcanuse-mcp",
      "args": []
    }
  }
}
```

如果你后续希望保留显式参数，也可以：

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

## 5. 保存后会发生什么

根据 LM Studio 官方说明，保存 `mcp.json` 后，LM Studio 会自动加载你定义的 MCP Server，并为每个本地 MCP Server 启动独立进程。

## 6. 在聊天里如何使用

接入成功后，LM Studio 中的模型就能看到并调用该 MCP 的工具。

你可以先让模型调用：

```text
list_all_tools()
```

这样模型能先知道当前这个 MCP 提供了哪些工具，再决定具体调用哪些能力。

如果你希望模型先了解桌面和系统上下文，推荐它优先调用：

```text
get_system_info()
get_desktop_context()
list_all_tools()
```

## 7. 常见问题

### 7.1 `python` 找不到

如果 LM Studio 启动时报找不到 `python`，说明 Python 不在系统 PATH 中。

这时有两种办法：

1. 把 Python 加入系统 PATH
2. 在 `mcp.json` 里把 `command` 改成 Python 的绝对路径

例如 Windows：

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "C:/Users/yourname/AppData/Local/Programs/Python/Python312/python.exe",
      "args": ["run_server.py", "--transport", "stdio"],
      "cwd": "D:/path/to/allcanuse"
    }
  }
}
```

### 7.2 仓库方式启动失败

优先检查：

- `cwd` 是否真的指向项目根目录
- 该目录下是否存在 `run_server.py`
- 当前 Python 版本是否至少为 3.11

### 7.3 已安装包方式启动失败

优先检查：

- 是否真的执行过 `pip install -e .` 或正式安装命令
- `allcanuse-mcp` 是否已经在 PATH 中

### 7.4 摄像头或 Linux 窗口工具不可用

这不是 MCP 注册失败，而是运行环境缺少可选依赖：

- 摄像头：`opencv-python`
- Linux 窗口枚举：`wmctrl`
- Linux 活动窗口查询：`xprop`
- Linux 截图：`gnome-screenshot`、`scrot` 或 `imagemagick`

### 7.5 模型能不能自己安装依赖

可以。当前这个 MCP 的提示词已经允许模型在确实需要时自行调用工具安装最小必需依赖，例如：

- `run_shell(command="pip install opencv-python")`
- `run_shell(command="apt install -y wmctrl")`

## 8. API 侧额外注意

如果你是通过 LM Studio 的 API 使用 `mcp.json` 里的 MCP，LM Studio 官方文档还提到：

- 需要启用 `Allow calling servers from mcp.json`
- 该选项要求同时启用 `Require Authentication`

这条主要影响 API 使用，不影响你在 LM Studio 聊天界面里直接用 MCP。

## 9. 官方文档参考

- LM Studio MCP 使用说明：
  https://lmstudio.ai/docs/app/plugins/mcp
- LM Studio MCP API 说明：
  https://lmstudio.ai/docs/developer/core/mcp//
- LM Studio Server Settings：
  https://lmstudio.ai/docs/developer/core/server/settings
