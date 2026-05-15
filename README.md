# allcanuse-mcp

一个面向 Windows / Linux 实验环境的 MCP Server，用来给本地 Agent / MCP Client 暴露常用的本机操作能力。

许可证：`MIT`

`allcanuse-mcp` 的目标不是只给模型几个零散小工具，而是尽量把“这台实验机能做的事”系统化地暴露给模型。  
接入后，模型不只是能读文件和跑命令，而是能把本机当成一个可操作的工作站来使用。

当前已经提供 `90+` 个 tools，核心能力包括：

- 系统与环境探测：读取系统架构、时间、磁盘空间、环境变量、网络配置、网络适配器、当前 IP 与基础运行环境信息
- 命令执行与自动化：执行跨平台 shell、Windows `cmd`、PowerShell，支持把命令输出继续用于后续决策
- 进程与端口管理：启动进程、结束进程、列出进程、查看进程树、定位端口对应进程、枚举监听端口与已建立连接；还支持登记和保护长时间运行的实验/训练/推理进程，避免模型误杀
- 文件与代码编辑：目录树遍历、按文件名搜索、按文本搜索、分段读取长文件、精确行替换、固定文本替换、文本文件写入、JSON 读写、二进制读写、哈希、最近文件、桌面文件查看
- 开发辅助与工程操作：压缩打包、解压归档、配置修改、源码定位、局部修补、运行验证命令，适合让模型直接做修 bug、改配置、写脚本、整理项目
- 网页与 HTTP 操作：HTTP 请求、HEAD 探测、响应头获取、网页正文提取、网页转 Markdown、链接提取、表格提取、指定 HTML 元素提取、网页表单提交、文件上传、文件下载、跳转链追踪
- 网络诊断与协议调试：DNS 解析、反向解析、TLS 证书读取、ping、路由追踪、TCP 连通性测试、原始 TCP 收发、UDP 收发、WebSocket 调试、小范围端口扫描
- 桌面与窗口观察：枚举窗口、获取前台窗口、汇总桌面上下文、截取桌面截图，适合结合带视觉能力的模型一起工作
- 视觉与音频采集：枚举本地摄像头并拍照，也可调用仓库内置的本地二进制工具录制麦克风音频，适合需要多模态输入的实验场景
- 值班与长任务托管：等待时间、等待文件/进程/端口/HTTP/窗口/桌面变化、后台值班任务、任务计划、任务事件、任务产物记录、断线后交接摘要
- 原生工具与多语言扩展：除了 Python tools，还可以把 C 语言等技术栈写成仓库内置的本地可执行工具交给模型直接调用，覆盖更底层、更高性能或更贴近系统接口的能力
- 模型自检与自我发现：可直接列出全部 tools 与完整说明，方便模型在陌生任务里自行决定下一步该调用什么

## 模型接入后可以做什么

接入这个 MCP 后，模型可以做的不只是“回答问题”，而是可以在本机上主动推进任务，例如：

- 帮你排查“某个服务为什么起不来”：先看端口、再看进程、再看日志、再发 HTTP 请求、最后给出定位结果
- 帮你改代码和修配置：先搜索目标文件和函数，再分段读取大文件，精确修改几行代码，然后自动跑验证命令
- 帮你阅读网页和整理资料：不只抓当前页正文，还能继续提取站内链接、章节页、详情页、表格、结构化元数据和附件，递进式收集整个网站里与任务相关的内容
- 帮你做更接近“研究助手”式的网页探索：模型会先判断当前页是正文页、目录页、索引页还是文档首页，再决定继续抓正文、提链接、读 metadata、还是批量递进抓多个子页，而不是把一组固定 URL 机械跑完就结束
- 帮你把网站内容按任务目标动态展开：例如先读文档首页，再沿安装页、API 页、FAQ 页、下载页继续深入；或者先读文章页，再顺着相关详情页和附件链接继续补全上下文
- 帮你在抓取过程中边读边判断：模型可以根据当前抓到的标题、正文、canonical、Open Graph、JSON-LD、链接文字和页面结构，决定下一步该继续读哪一页、跳过哪一页、下载哪个附件、提取哪个表格或元素
- 帮你把网页抓取和本地工作流连起来：抓到内容后不只是返回原始文本，还可以继续下载文件、保存结果、整理为 Markdown、提取表格、再结合本地代码、日志、网络状态一起分析
- 帮你检查本地网络问题：看 DNS、ping、端口、TLS、路由和连接状态，判断是解析问题、主机不可达、端口不通还是应用层异常
- 帮你自动观察桌面变化：盯安装器、盯窗口弹出、盯前台切换、自动截图，适合实验环境里的 GUI 任务
- 帮你采集实验输入素材：模型不仅能截图、拍照，也能在需要时调用本地原生音频录制能力采集麦克风输入，便于做语音、会议、访谈、环境声等实验流程
- 帮你上传和下载本地文件：把日志、压缩包、构建产物上传到接口，也可以像轻量版 `wget` 一样把网络文件拉到本地
- 帮你做长时间值班：用户暂时离开后继续等文件生成、等服务恢复、等窗口出现，回来时再通过交接摘要快速接手
- 帮你在虚拟机里做实验自动化：把“观察 -> 判断 -> 执行 -> 验证”整套流程交给模型，而不是只让模型停留在口头建议
- 帮你托管超长实验进程：对于要跑几小时到几天的训练、推理、服务或批处理任务，模型可以把它登记成受保护的长时进程，stdout/stderr 会写入持久日志；即使 AI 会话或客户端连接中断，本机进程仍可继续运行，下一次连接后可用 `get_managed_process` 读取状态和日志尾部继续接手
- 帮你利用仓库内置的原生程序做更底层工作：当某些任务更适合用 C 或本地可执行程序处理时，模型可以直接调用这些内置工具，而不必把所有能力都限制在 Python 层

如果你想让模型更像一个真正能动手的本地助手，而不只是会说不会做，`allcanuse-mcp` 的定位就是把这些能力统一交到模型手里。

## 快速开始

现在主流 AI 客户端接入 MCP 时，通常只需要：

1. 安装依赖
2. 在客户端配置 MCP
3. 重启客户端

不需要你手动先启动这个服务端进程，客户端会按配置自动拉起。

### 1. 安装依赖

先安装当前项目最基础的运行依赖：

```powershell
pip install -r requirements.txt
```

如果你是开发者，或者希望本地命令更短，也可以：

```powershell
pip install -e .
```

### 2. 在客户端里配置 MCP

#### ChatGPT Codex / Codex CLI

配置文件通常是：

```text
~/.codex/config.toml
```

示例：

```toml
[mcp_servers.allcanuse]
type = "stdio"
command = "python"
args = ["run_server.py", "--transport", "stdio", "--profile", "codex"]
cwd = "D:/path/to/allcanuse"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180
```

如果在 macOS 上使用 Codex，并且希望明确走当前项目内置的 `stdio` 兼容层，可以写成下面这种更完整的形式：

```toml
[mcp_servers.allcanuse]
type = "stdio"
command = "/opt/homebrew/bin/python3"
args = ["run_server.py", "--transport", "stdio", "--profile", "codex"]
cwd = "/Users/you/path/to/allcanuse-mcp"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 240
```

Codex 建议显式加 `--profile codex`。该 profile 会优先保留 Codex 原生没有的桌面观察、截图、摄像头、值班/后台任务、长时进程登记、Microsoft 文档检查等能力，并隐藏 `run_shell`、`read_file`、`patch_lines`、`fetch_webpage_text` 这类 Codex 已经原生提供的能力，减少初始化上下文和工具选择开销。

这里不需要额外配置兼容开关，只要保持 `--transport stdio` 即可。当前 `stdio` 启动入口会自动兼容 Codex 可能使用的 `Content-Length` framing，以及其他客户端常见的逐行 JSON 输入输出。如果 Codex 中出现工具调用结果为空、初始化超时或 stderr 里看到 `Content-Length: ...` 被当成 JSON 解析的情况，优先确认本地代码已经更新到包含 `src/allcanuse_mcp/stdio_compat.py` 的版本，然后完全重启 Codex 让它重新拉起 MCP 服务端。

注意：`--profile codex` 下 `list_all_tools()` 只会列出当前暴露给 Codex 的精简工具集。需要完整 100+ 工具时，把参数改成 `--profile full`，或者设置环境变量 `ALLCANUSE_MCP_PROFILE=full` 后重启客户端。

通常不需要把 `args` 改成 `["stdio_compat.py", "--transport", "stdio"]`，推荐仍然从仓库根目录启动 `run_server.py`。如果某个客户端只能配置到包目录并直接运行兼容入口，当前版本也支持下面这种备用写法：

```toml
[mcp_servers.allcanuse]
type = "stdio"
command = "/opt/homebrew/bin/python3"
args = ["stdio_compat.py", "--transport", "stdio", "--profile", "codex"]
cwd = "/Users/you/path/to/allcanuse-mcp/src/allcanuse_mcp"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 240
```

如果已经执行过 `pip install -e .`，也可以改成：

```toml
[mcp_servers.allcanuse]
type = "stdio"
command = "allcanuse-mcp"
enabled = true
startup_timeout_ms = 30000
tool_timeout_sec = 180
```

#### Claude Code

项目内常见做法是在仓库根目录写 `.mcp.json`：

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

如果已经安装为命令行入口，也可以：

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

#### OpenCode

OpenCode 通常写在用户目录的 .config/opencode 目录的 `opencode.json` 或 `opencode.jsonc` 的 `mcp` 字段里：

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "allcanuse": {
      "type": "local",
      "command": ["python", "D:/*****/allcanuse/run_server.py", "--transport", "stdio"],
      "enabled": true
    }
  }
}
```

如果已经安装为命令行入口，也可以：

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

#### LM Studio

在 LM Studio 的 `mcp.json` 中可写：

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

如果已经安装为命令行入口，也可以：

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

### 2.1 更多客户端配置格式参考

下面这些格式参考了相关权威客户端接入文档中的常见配置结构，再按当前项目的本地 `stdio` 启动方式改写成 `allcanuse-mcp` 可直接使用的示例。

#### GitHub Copilot CLI

GitHub Copilot CLI 的 MCP 配置文件通常是：

```text
~/.copilot/mcp-config.json
```

如果已经执行过 `pip install -e .`，推荐直接写成：

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "allcanuse-mcp"
    }
  }
}
```

如果更希望从仓库目录直接运行，也可以写：

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

#### GitHub Copilot IDEs

GitHub Copilot IDE 文档中的常见结构是项目级或用户级 `.mcp.json`，并使用 `servers` 字段。

如果已经安装成命令行入口，推荐这样写：

```json
{
  "servers": {
    "allcanuse": {
      "type": "stdio",
      "command": "allcanuse-mcp"
    }
  }
}
```

如果你的具体 IDE 版本支持本地命令加参数，也可以改成：

```json
{
  "servers": {
    "allcanuse": {
      "type": "stdio",
      "command": "python",
      "args": ["run_server.py", "--transport", "stdio"]
    }
  }
}
```

#### Cursor

Cursor 文档里常见全局 MCP 配置文件是：

```text
~/.cursor/mcp.json
```

推荐示例：

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

如果已经安装为命令行入口，也可以：

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "allcanuse-mcp"
    }
  }
}
```

#### Windsurf

Windsurf 文档里常见 MCP 配置文件是：

```text
~/.codeium/windsurf/mcp_config.json
```

推荐示例：

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

如果已经安装为命令行入口，也可以：

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "allcanuse-mcp"
    }
  }
}
```

#### Rovo Dev CLI

Rovo Dev CLI 文档中的常见做法是先运行：

```text
acli rovodev mcp
```

打开对应 MCP 配置后，可按同样的 `mcpServers` 结构写入本项目。推荐示例：

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

如果已经安装为命令行入口，也可以：

```json
{
  "mcpServers": {
    "allcanuse": {
      "command": "allcanuse-mcp"
    }
  }
}
```

### 3. 重启客户端后直接使用

配置保存后，重启对应客户端即可。

接入成功后，建议先让模型调用：

```text
list_all_tools()
```

然后再让模型调用：

```text
get_system_info()
get_desktop_context()
```

如果这些调用都正常返回，通常就说明 MCP 已接通并可直接使用。

### 4. `stdio` 接入异常排查

少数环境里可能会遇到一种比较反常的 `stdio` 接入失败：

- 客户端配置看起来正确，服务端进程也能被拉起
- 模型侧调用工具后结果为空，或初始化阶段一直等不到响应
- 手工测试服务端 stderr 里能看到类似 `Invalid JSON: expected value`，并且输入内容像 `Content-Length: 172`

这通常不是工具注册失败，而是客户端和当前 Python MCP SDK 对 `stdio` 消息格式的理解不一致。某些客户端会按 `Content-Length: ...\r\n\r\n{json}` 这种 framing 方式发送 JSON-RPC 消息，而部分 SDK 版本默认按“一行一个 JSON”读取 stdin，导致它把 `Content-Length: ...` 当成 JSON 正文解析。

当前项目的 `--transport stdio` 已经做了兼容处理：

- 继续支持原本的逐行 JSON 输入输出
- 同时支持 `Content-Length` framing 输入输出
- 服务端会根据客户端实际发送的首个消息格式自动选择响应格式

如果某台机器上出现“其他 macOS / Windows / Linux 正常，但当前机器调用结果空白”的情况，建议按下面顺序排查：

1. 确认客户端配置仍然使用 `--transport stdio`
2. 更新到包含 `src/allcanuse_mcp/stdio_compat.py` 的版本
3. 完全重启 MCP 客户端，让客户端重新拉起服务端进程
4. 先调用 `list_all_tools()`，再调用一个简单工具如 `get_system_info()`
5. 如果仍然异常，再用最小 stdio 客户端分别测试逐行 JSON 与 `Content-Length` framing

## 文档

- 通用使用说明：[docs/USAGE.zh-CN.md](./docs/USAGE.zh-CN.md)
- 全部工具总览：[docs/TOOLS.zh-CN.md](./docs/TOOLS.zh-CN.md)
- 值班工作流说明：`resource://guides/workflows/duty-watch`
- LM Studio 接入教程：[docs/LM-STUDIO.zh-CN.md](./docs/LM-STUDIO.zh-CN.md)
- Codex / Claude Code / OpenCode 接入教程：[docs/CLIENT-INTEGRATIONS.zh-CN.md](./docs/CLIENT-INTEGRATIONS.zh-CN.md)
- 发布后最终用户使用教程：[docs/RELEASE-USAGE.zh-CN.md](./docs/RELEASE-USAGE.zh-CN.md)

如果要把当前 MCP 接到不同客户端，建议优先看：

- [LM Studio](./docs/LM-STUDIO.zh-CN.md)
- [全部工具清单](./docs/TOOLS.zh-CN.md)
- [ChatGPT Codex / Codex CLI](./docs/CLIENT-INTEGRATIONS.zh-CN.md)
- [Claude Code](./docs/CLIENT-INTEGRATIONS.zh-CN.md)
- [OpenCode](./docs/CLIENT-INTEGRATIONS.zh-CN.md)
- [发布后最终用户安装与接入](./docs/RELEASE-USAGE.zh-CN.md)

## 可选依赖

- 摄像头功能优先使用 `opencv-python`，Linux 还可回退到 `ffmpeg`、`libcamera-still`、`fswebcam`，Windows 还可回退到 `ffmpeg`
- Windows 下截图能力默认依赖 `Pillow`
- Windows 下进程、端口、系统信息增强依赖 `psutil` 与 `pywin32`
- Linux 窗口枚举依赖 `wmctrl`
- Linux 活动窗口查询依赖 `xprop`
- Linux 截图可能使用 `gnome-screenshot`、`scrot` 或 `imagemagick`

补充说明：

- Linux 现在即使不安装 `psutil`，核心系统信息、进程查询、端口查询、监听端口、已建立连接等能力也能通过底层 `/proc` 与 `/sys` 回退实现继续工作
- Linux 下截图、窗口枚举、前台窗口查询、摄像头这类能力仍然主要依赖系统图形环境或额外工具；摄像头枚举还支持直接读取 `/dev/video*` 与 `/sys/class/video4linux`

关于图像如何传给模型：

- `capture_screenshot` 和 `capture_camera_photo` 现在不只会返回本地文件路径
- 如果调用时把 `return_image_content=true`，在支持视觉内容的 MCP 客户端里，工具结果会直接附带图像内容，模型可以直接看图
- 如果客户端暂时不支持图像内容，工具仍会正常返回结构化元数据和本地路径，后续依然可以继续读取、上传、分析或交给其他支持视觉的链路处理

## 验证

```powershell
python -m compileall src tests run_server.py
$env:PYTHONPATH=(Resolve-Path .\src).Path
python -m unittest discover -s tests -v
```
