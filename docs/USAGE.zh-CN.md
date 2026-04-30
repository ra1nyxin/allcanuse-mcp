# allcanuse-mcp 使用说明

## 1. 这是什么

`allcanuse-mcp` 是一个本地 MCP Server。启动后，支持 MCP 的客户端可以调用它暴露的工具，让模型在当前机器上执行常见的系统、文件、网络、窗口、截图、下载和开发辅助操作。

它的定位不是“单一功能工具”，而是一套本机能力入口。

## 2. 适用环境

- Windows
- Linux
- Python 3.11 及以上

## 3. 启动方式

### 方式一：直接在仓库内运行

这是当前最直接的方式。

Windows / Linux 通用：

```bash
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

### 方式二：安装后运行

```bash
pip install -e .
allcanuse-mcp
```

## 4. 常用启动参数

### `stdio`

最适合 MCP 客户端接入：

```bash
python run_server.py --transport stdio
```

### `streamable-http`

适合需要 HTTP 方式接入的场景：

```bash
python run_server.py --transport streamable-http --host 127.0.0.1 --port 8000
```

## 5. 工具如何查看

模型可以直接调用：

```text
list_all_tools()
```

如果想看完整说明：

```text
list_all_tools(include_descriptions=true)
```

如果你想看当前项目维护好的完整工具清单文档，请直接看：

- [TOOLS.zh-CN.md](./TOOLS.zh-CN.md)

## 6. 常用工具分类

### 系统类

- `get_system_info`
- `get_env`
- `get_time`
- `get_disk_usage`
- `get_network_config`
- `list_network_adapters`

### 命令与进程类

- `run_shell`
- `run_cmd`
- `run_powershell`
- `start_process`
- `kill_process`
- `list_processes`
- `get_process_tree`
- `find_port_process`

### 文件类

- `list_tree`
- `read_file`
- `write_file`
- `patch_lines`
- `replace_text`
- `find_files`
- `search_text`
- `copy_path`
- `move_path`
- `delete_path`
- `zip_paths`
- `extract_archive`
- `hash_file`
- `read_binary_file`
- `write_binary_file`
- `read_json_file`
- `write_json_file`

### 值班与等待类

- `wait`
- `wait_until`
- `get_scheduler_time`
- `wait_for_file`
- `wait_for_process`
- `wait_for_port`
- `wait_for_http`
- `wait_for_window`
- `wait_for_desktop_change`
- `create_background_task`
- `list_background_tasks`
- `get_background_task`
- `cancel_background_task`
- `pause_background_task`
- `resume_background_task`
- `wait_for_background_task`
- `create_task_plan`
- `update_task_step`
- `append_task_event`
- `record_task_artifact`
- `summarize_background_task`
- `get_task_handoff`
- `mark_task_waiting_for_user`
- `mark_task_waiting_for_condition`

### 窗口与桌面类

- `list_windows`
- `get_active_window`
- `get_desktop_context`
- `capture_screenshot`

### 网络类

- `http_head`
- `fetch_response_headers`
- `http_request`
- `download_file`
- `submit_web_form`
- `upload_file`
- `trace_http_redirects`
- `fetch_webpage_text`
- `webpage_to_markdown`
- `extract_links_from_webpage`
- `extract_tables_from_webpage`
- `extract_webpage_elements`
- `trace_route`
- `resolve_dns_records`
- `reverse_dns_lookup`
- `dns_lookup`
- `get_tls_certificate`
- `ping_host`
- `tcp_connect`
- `raw_tcp_exchange`
- `udp_send_receive`
- `websocket_connect`
- `scan_ports`
- `list_established_connections`
- `list_listening_ports`

更完整的逐项说明、关键参数和示例请看：

- [TOOLS.zh-CN.md](./TOOLS.zh-CN.md)

## 7. 代码编辑与大文件阅读建议

如果模型主要要做的是读代码、写代码、修改配置、修 bug，推荐直接遵循下面流程：

1. 先 `list_tree` 看项目结构。
2. 再 `find_files` 按文件名模式缩小范围，例如 `*.py`、`*.ts`、`*.json`、`*test*`。
3. 再 `search_text` 搜函数名、类名、配置项、报错文本、固定字符串。
4. 命中后再 `read_file(path=..., start_line=..., end_line=...)` 局部读取上下文。
5. 长文件优先每段读取 `50` 到 `200` 行；不够再继续扩读，不要默认整文件通读。
6. 已知行号范围时优先 `patch_lines`。
7. 已知固定文本时优先 `replace_text`。
8. 只有在新建文件、生成完整小文件、或确实需要整体重写时再用 `write_file`。
9. JSON 优先 `read_json_file` 与 `write_json_file`。
10. 改完后再次 `read_file` 回读修改结果，再执行验证命令。

简化示例：

```text
find_files(root="src", pattern="*.py")
search_text(root="src", query="TODO", file_pattern="*.py")
read_file(path="src/app.py", start_line=80, end_line=160)
replace_text(path="src/app.py", old_text="DEBUG = False", new_text="DEBUG = True", count=1)
read_file(path="src/app.py", start_line=80, end_line=120)
```

## 8. 超时说明

网络和长时工具尽量都暴露了 `timeout_ms` 给模型自己控制。

例如：

```text
http_head(url="https://example.com/file.zip", timeout_ms=60000)
```

```text
download_file(url="https://example.com/big.zip", destination="downloads/big.zip", timeout_ms=180000)
```

```text
http_request(url="https://example.com/api", timeout_ms=60000)
```

```text
submit_web_form(url="https://example.com/search", method="GET", form_fields={"q":"mcp tools"}, timeout_ms=60000)
```

```text
upload_file(url="https://example.com/upload", file_path="dist/app.zip", form_fields={"project":"allcanuse"}, timeout_ms=180000)
```

```text
create_background_task(title="等待服务恢复", goal="等到健康检查恢复 200", task_type="wait_http", condition={"url":"http://127.0.0.1:8000/health","expected_statuses":[200]}, poll_interval_ms=5000, timeout_ms=3600000)
```

```text
create_background_task(title="等待安装窗口", goal="等安装向导切到前台", task_type="wait_window", condition={"title_filter":"Setup","state":"foreground"}, poll_interval_ms=1000, timeout_ms=1800000)
```

```text
get_task_handoff(task_id="...", include_recent_events=20)
```

```text
get_scheduler_time()
```

返回里的 `scheduler.running`、`scheduler.last_error`、`scheduler.last_error_at` 可用于排查调度器是否还在正常轮询。

```text
tcp_connect(host="10.0.0.5", port=443, timeout_ms=10000)
```

## 8. 可选依赖

以下依赖不是启动必需，但某些功能会用到：

- `opencv-python`
  - 用于摄像头枚举与拍照
- `wmctrl`
  - Linux 窗口枚举
- `xprop`
  - Linux 活动窗口查询
- `gnome-screenshot` / `scrot` / `imagemagick`
  - Linux 桌面截图备用后端

## 9. 验证项目状态

```bash
python -m compileall src tests run_server.py
python -m unittest discover -s tests -v
```

## 10. 发布后如何使用

如果以后发布成包，推荐用户使用下面两种方式之一。

### 方式一：安装后直接运行

```bash
pip install allcanuse-mcp
allcanuse-mcp
```

### 方式二：固定版本安装

```bash
pip install allcanuse-mcp==0.1.0
allcanuse-mcp
```

如果以后你发布到私有源或 Git 仓库，也可以把安装命令换成对应地址，但启动方式仍然尽量保持 `allcanuse-mcp` 或 `python run_server.py` 这种简单入口。
