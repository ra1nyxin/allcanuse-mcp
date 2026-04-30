# allcanuse-mcp

一个面向 Windows / Linux 实验环境的 MCP Server，用来给本地 Agent / MCP Client 暴露常用的本机操作能力。

许可证：`MIT`

当前已实现的能力包括：

- 系统信息、时间、磁盘、环境变量、网络配置、网络适配器
- 通用 shell、`cmd`、PowerShell 执行
- 进程启动、结束、枚举、进程树、端口到进程定位
- 文件树、读写、精确行替换、文本替换、目录创建、移动、复制、删除
- 打包、解压、二进制读写、JSON 读写、哈希、最近文件、文件搜索、文本搜索
- 摄像头枚举与拍照
- 等待、条件等待、窗口/桌面值班、后台值班任务、任务恢复和交接摘要
- 窗口枚举、前台窗口、桌面上下文、桌面截图
- HTTP 头检查、HTTP 请求、网页表单提交、文件上传、下载文件、DNS 解析、ping、TCP 连通性测试、WebSocket 调试、监听端口枚举
- 工具汇总，可直接列出当前项目全部 tools

## 快速开始

直接在仓库根目录运行：

```powershell
python run_server.py --transport stdio
```

Windows 也可以：

```powershell
start.cmd --transport stdio
```

Linux 也可以：

```bash
./start.sh --transport stdio
```

如果已经安装为包，也可以：

```powershell
pip install -e .
allcanuse-mcp
```

## 文档

- 通用使用说明：[docs/USAGE.zh-CN.md](./docs/USAGE.zh-CN.md)
- 全部工具总览：[docs/TOOLS.zh-CN.md](./docs/TOOLS.zh-CN.md)
- 值班工作流说明：`resource://guides/workflows/duty-watch`
- LM Studio 接入教程：[docs/LM-STUDIO.zh-CN.md](./docs/LM-STUDIO.zh-CN.md)
- Codex / Claude Code / OpenCode 接入教程：[docs/CLIENT-INTEGRATIONS.zh-CN.md](./docs/CLIENT-INTEGRATIONS.zh-CN.md)
- 发布后最终用户使用教程：[docs/RELEASE-USAGE.zh-CN.md](./docs/RELEASE-USAGE.zh-CN.md)

如果你要把当前 MCP 接到不同客户端，建议优先看：

- `LM Studio`：`docs/LM-STUDIO.zh-CN.md`
- `全部工具清单`：`docs/TOOLS.zh-CN.md`
- `ChatGPT Codex / Codex CLI`：`docs/CLIENT-INTEGRATIONS.zh-CN.md`
- `Claude Code`：`docs/CLIENT-INTEGRATIONS.zh-CN.md`
- `OpenCode`：`docs/CLIENT-INTEGRATIONS.zh-CN.md`
- `发布后最终用户安装与接入`：`docs/RELEASE-USAGE.zh-CN.md`

## 可选依赖

- 摄像头功能依赖 `opencv-python`
- Linux 窗口枚举依赖 `wmctrl`
- Linux 活动窗口查询依赖 `xprop`
- Linux 截图可能使用 `gnome-screenshot`、`scrot` 或 `imagemagick`

## 验证

```powershell
python -m compileall src tests run_server.py
$env:PYTHONPATH=(Resolve-Path .\src).Path
python -m unittest discover -s tests -v
```
