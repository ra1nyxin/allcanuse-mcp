# allcanuse-mcp 工具总览

本文档汇总当前 `allcanuse-mcp` 已暴露的全部 MCP tools。  
当前工具总数：`93`

如果模型已经接入当前 MCP，也可以直接调用：

```text
list_all_tools()
```

如果想让模型拿到完整说明：

```text
list_all_tools(include_descriptions=true)
```

## 0. 按工具名速查索引

下面这一段适合快速搜索工具名，不想先读分类时可以直接看这里。

| 工具名 | 一句话作用 |
| --- | --- |
| `capture_camera_photo` | 调用指定摄像头拍摄一张照片；既可保存到本地，也可在支持视觉内容的客户端里直接把图像随工具结果返回给模型。 |
| `capture_screenshot` | 截取当前桌面截图；既可保存到本地，也可在支持视觉内容的客户端里直接把图像随工具结果返回给模型。 |
| `copy_path` | 复制文件或目录。 |
| `delete_path` | 删除文件或目录。 |
| `dns_lookup` | 解析域名对应的 IP 地址。 |
| `download_file` | 下载网络文件到本地，类似轻量版 `wget`。 |
| `extract_archive` | 解压 zip 或 tar 类归档文件到指定目录。 |
| `fetch_response_headers` | 读取 HTTP/HTTPS 响应头，适合不支持 HEAD 的接口。 |
| `extract_links_from_webpage` | 提取网页中的超链接，返回链接文本、原始 href 和绝对链接。 |
| `extract_webpage_elements` | 按标签名和属性条件提取网页元素，适合精确抓取特定 DOM 片段。 |
| `fetch_webpage_text` | 抓取网页并提取主要可读文字内容，适合让模型快速读网页正文。 |
| `webpage_to_markdown` | 抓取网页并转换成更适合模型阅读的 Markdown 文本。 |
| `find_files` | 按文件名模式递归搜索文件或目录。 |
| `find_port_process` | 查找某个端口当前对应的连接或监听进程。 |
| `get_active_window` | 读取当前前台活动窗口信息。 |
| `get_desktop_context` | 汇总当前桌面上下文，一次返回前台窗口和后台窗口列表。 |
| `get_disk_usage` | 获取指定路径所在磁盘或挂载点的空间占用情况。 |
| `get_env` | 读取环境变量。 |
| `get_ipconfig` | 兼容旧调用名的网络配置工具。 |
| `get_network_config` | 获取当前主机的网络配置摘要。 |
| `get_process_tree` | 读取指定进程的子进程树。 |
| `get_system_info` | 读取当前主机的系统概况。 |
| `get_tls_certificate` | 读取 TLS/HTTPS 证书信息，返回主题、签发者、指纹、有效期和协商协议。 |
| `get_time` | 获取本地时间、UTC 时间，以及可选时区的当前时间。 |
| `hash_file` | 计算文件哈希。 |
| `http_head` | 对 URL 发起 HEAD 请求，只读取状态码和响应头。 |
| `http_request` | 发起 HTTP/HTTPS 请求，适合检查本地服务、接口联通性或拉取文本内容。 |
| `kill_process` | 按 PID 或按进程名结束进程。 |
| `list_all_tools` | 汇总当前 MCP Server 暴露的全部工具。 |
| `list_cameras` | 枚举本机可访问的摄像头设备。 |
| `list_desktop_files` | 列出当前用户桌面目录中的文件和子目录。 |
| `list_established_connections` | 列出当前主机已经建立的网络连接。 |
| `list_listening_ports` | 列出当前主机上处于监听状态的端口。 |
| `list_network_adapters` | 读取当前主机所有网络适配器和地址信息。 |
| `list_processes` | 枚举当前主机上的进程。 |
| `list_recent_files` | 列出最近修改的文件。 |
| `list_tree` | 递归列出目录树。 |
| `list_windows` | 枚举桌面窗口标题、句柄、进程信息和窗口矩形。 |
| `mkdir` | 创建目录。 |
| `move_path` | 移动或重命名文件/目录。 |
| `patch_lines` | 按行号精确替换文件中的一段内容。 |
| `ping_host` | 对目标主机执行 ping 测试。 |
| `read_binary_file` | 读取二进制文件片段，并返回 base64 或 hex 编码。 |
| `read_file` | 读取文本文件，支持按行切片。 |
| `read_json_file` | 读取 JSON 文件并返回解析后的结构化数据。 |
| `replace_text` | 在文件中按字面值替换文本片段。 |
| `resolve_dns_records` | 直接查询 DNS 多种记录类型，支持 A、AAAA、CNAME、MX、TXT、NS、SRV。 |
| `reverse_dns_lookup` | 对 IP 地址做反向 DNS 查询。 |
| `run_cmd` | 执行一条命令。 |
| `run_powershell` | 执行一段 PowerShell 脚本或单行命令。 |
| `run_shell` | 用当前平台的默认 shell 执行命令。 |
| `raw_tcp_exchange` | 连接 TCP 服务后发送原始数据，再读取响应，适合做轻量版 netcat / 文本协议调试。 |
| `search_text` | 在文本文件中搜索关键字或正则表达式。 |
| `start_process` | 启动一个新进程并返回 PID。 |
| `stat_path` | 读取文件或目录的元信息。 |
| `submit_web_form` | 提交网页表单，支持 GET 查询串和 POST 普通表单。 |
| `tcp_connect` | 测试 TCP 端口是否可连通。 |
| `trace_http_redirects` | 追踪一个 URL 的 HTTP 重定向链，适合排查 301/302/307/308 跳转问题。 |
| `trace_route` | 执行 traceroute / tracert，查看到目标主机的路由跳点。 |
| `udp_send_receive` | 向 UDP 服务发送一段数据并等待响应。 |
| `upload_file` | 把本地文件上传到网络接口，支持 `multipart` 和原始字节流上传。 |
| `extract_tables_from_webpage` | 提取网页中的 HTML 表格，并返回结构化表头和行数据。 |
| `which_command` | 检查某个命令在当前系统中是否存在，并返回路径。 |
| `write_binary_file` | 写入二进制文件，输入内容可用 base64 或 hex 提供。 |
| `write_file` | 写入文本文件，支持覆盖或追加。 |
| `write_json_file` | 把结构化数据写入 JSON 文件。 |
| `websocket_connect` | 连接 WebSocket 接口，发送文本消息并读取返回。 |
| `zip_paths` | 把一个或多个文件/目录打包成压缩文件。 |
| `wait` | 等待一段时间后再继续。 |
| `wait_until` | 等待到指定时间点再继续。 |
| `get_scheduler_time` | 读取当前值班调度器时间和后台任务统计。 |
| `wait_for_file` | 等待文件出现、消失、变大或包含指定文本。 |
| `wait_for_process` | 等待指定进程启动或退出。 |
| `wait_for_port` | 等待某个 TCP 端口开放或关闭。 |
| `wait_for_http` | 等待 HTTP/HTTPS 接口恢复到预期状态。 |
| `wait_for_window` | 等待窗口出现、消失或切到前台。 |
| `wait_for_desktop_change` | 等待桌面窗口集合或前台窗口发生变化。 |
| `create_background_task` | 创建一个后台值班任务。 |
| `list_background_tasks` | 列出当前所有后台值班任务。 |
| `get_background_task` | 查看某个后台任务详情。 |
| `cancel_background_task` | 取消一个后台值班任务。 |
| `pause_background_task` | 暂停一个后台值班任务。 |
| `resume_background_task` | 恢复一个已暂停或等待用户的后台值班任务。 |
| `wait_for_background_task` | 等待某个后台任务进入目标状态。 |
| `create_task_plan` | 给后台任务附加步骤计划。 |
| `update_task_step` | 更新后台任务某个步骤的状态和备注。 |
| `append_task_event` | 向后台任务追加人工事件。 |
| `record_task_artifact` | 记录后台任务产出的文件或目录。 |
| `summarize_background_task` | 生成后台任务当前状态和最近事件的交接摘要。 |
| `get_task_handoff` | 生成更适合模型重连接手的任务交接摘要。 |
| `mark_task_waiting_for_user` | 显式标记后台任务当前需要用户决定。 |
| `mark_task_waiting_for_condition` | 显式标记后台任务当前在等待某个条件。 |

## 0.1 按任务场景快速选工具

如果你不是按工具名查，而是按任务目标查，优先按下面选：

| 任务目标 | 推荐先用的工具 | 后续常接的工具 |
| --- | --- | --- |
| 想先知道当前机器是什么环境 | `get_system_info`, `get_env`, `get_time` | `get_disk_usage`, `get_network_config`, `list_network_adapters` |
| 想看当前项目或目录结构 | `list_tree`, `find_files` | `read_file`, `search_text`, `list_recent_files`, `stat_path` |
| 想修改代码或文本文件 | `read_file`, `search_text` | `patch_lines`, `replace_text`, `write_file`, `write_json_file` |
| 想处理压缩包、二进制、JSON | `extract_archive`, `zip_paths`, `read_json_file` | `write_json_file`, `read_binary_file`, `write_binary_file`, `hash_file` |
| 想执行命令或安装依赖 | `run_shell` | `run_cmd`, `run_powershell`, `which_command`, `start_process` |
| 想看进程、杀进程、查端口 | `list_processes`, `find_port_process` | `get_process_tree`, `kill_process`, `list_listening_ports`, `list_established_connections`, `tcp_connect` |
| 想看桌面、窗口、前后台信息 | `get_desktop_context` | `get_active_window`, `list_windows`, `capture_screenshot` |
| 想用摄像头 | `list_cameras` | `capture_camera_photo` |
| 想下载文件或测接口 | `http_head`, `download_file`, `http_request` | `fetch_response_headers`, `submit_web_form`, `trace_http_redirects`, `dns_lookup`, `resolve_dns_records`, `ping_host`, `tcp_connect`, `get_tls_certificate`, `trace_route` |
| 想把本地文件传到网络 | `upload_file` | `zip_paths`, `http_head`, `fetch_response_headers`, `http_request`, `submit_web_form`, `trace_http_redirects` |
| 想读网页正文 | `trace_http_redirects`, `http_head`, `fetch_webpage_text`, `webpage_to_markdown` | `fetch_response_headers`, `extract_links_from_webpage`, `extract_tables_from_webpage`, `extract_webpage_elements`, `submit_web_form`, `download_file` |
| 想抓网页里的链接 | `extract_links_from_webpage` | `fetch_webpage_text`, `extract_webpage_elements` |
| 想抓网页里的表格 | `extract_tables_from_webpage` | `fetch_webpage_text`, `webpage_to_markdown`, `extract_webpage_elements` |
| 想抓网页里的指定元素 | `extract_webpage_elements` | `fetch_webpage_text`, `extract_links_from_webpage` |
| 想提交网页表单 | `submit_web_form` | `http_head`, `fetch_response_headers`, `trace_http_redirects`, `fetch_webpage_text`, `extract_webpage_elements` |
| 想查 DNS、证书、原始协议 | `resolve_dns_records`, `get_tls_certificate` | `reverse_dns_lookup`, `raw_tcp_exchange`, `udp_send_receive`, `websocket_connect`, `trace_route`, `scan_ports` |
| 想值班、长期等待、用户离线后继续观察 | `create_background_task`, `wait_for_file`, `wait_for_port`, `wait_for_http`, `wait_for_window`, `wait_for_desktop_change` | `wait`, `wait_until`, `wait_for_process`, `list_background_tasks`, `get_background_task`, `summarize_background_task`, `get_task_handoff`, `create_task_plan`, `append_task_event`, `record_task_artifact` |
| 想看桌面文件 | `list_desktop_files` | `read_file`, `copy_path`, `move_path`, `delete_path` |

## 1. 系统类工具

这一类工具主要用于先了解当前主机环境。

| 工具名 | 用途 | 常见关键参数 | 示例 |
| --- | --- | --- | --- |
| `list_all_tools` | 汇总全部工具 | `include_descriptions` | `list_all_tools(include_descriptions=true)` |
| `get_system_info` | 读取系统概况 | 无 | `get_system_info()` |
| `get_env` | 读取环境变量 | `names` | `get_env(names=["PATH","HOME"])` |
| `get_time` | 读取本地时间、UTC、指定时区时间 | `timezone` | `get_time(timezone="Asia/Shanghai")` |
| `get_disk_usage` | 查看指定路径所在磁盘空间 | `path` | `get_disk_usage(path="C:\\")` |
| `get_network_config` | 获取网络配置摘要 | `max_output_chars`, `timeout_ms` | `get_network_config(timeout_ms=60000)` |
| `get_ipconfig` | `get_network_config` 的兼容旧名称 | `max_output_chars`, `timeout_ms` | `get_ipconfig()` |
| `list_network_adapters` | 读取全部网络适配器信息 | 无 | `list_network_adapters()` |

## 2. 命令与进程类工具

这一类工具用于执行命令、启动进程、结束进程、排查端口与进程关系。

| 工具名 | 用途 | 常见关键参数 | 示例 |
| --- | --- | --- | --- |
| `run_shell` | 用当前平台默认 shell 执行命令 | `command`, `cwd`, `timeout_ms`, `max_output_chars` | `run_shell(command="python --version")` |
| `run_cmd` | 执行一条命令 | `command`, `cwd`, `timeout_ms`, `max_output_chars` | `run_cmd(command="dir")` |
| `run_powershell` | 执行 PowerShell 脚本或命令 | `script`, `cwd`, `timeout_ms`, `max_output_chars` | `run_powershell(script="Get-Process | Select-Object -First 5")` |
| `start_process` | 启动新进程并返回 PID | `command`, `cwd`, `detach` | `start_process(command="python -m http.server 9000")` |
| `kill_process` | 按 PID 或进程名结束进程 | `pid`, `name`, `force` | `kill_process(name="notepad.exe")` |
| `list_processes` | 枚举进程 | `name_filter`, `limit` | `list_processes(name_filter="python")` |
| `get_process_tree` | 读取指定进程的子进程树 | `pid`, `max_depth` | `get_process_tree(pid=1234, max_depth=3)` |
| `find_port_process` | 查找端口对应的进程 | `port` | `find_port_process(port=8000)` |

## 3. 文件类工具

这一类工具覆盖代码读写、目录遍历、文本替换、二进制读写、压缩解压、JSON 读写等常用操作。

| 工具名 | 用途 | 常见关键参数 | 示例 |
| --- | --- | --- | --- |
| `list_tree` | 递归列出目录树 | `root`, `max_depth`, `max_entries`, `show_hidden` | `list_tree(root=".")` |
| `read_file` | 读取文本文件，可按行切片 | `path`, `start_line`, `end_line`, `encoding` | `read_file(path="README.md")` |
| `write_file` | 写入文本文件 | `path`, `content`, `mode`, `create_dirs` | `write_file(path="notes.txt", content="hello")` |
| `patch_lines` | 按行号精确替换文件片段 | `path`, `start_line`, `end_line`, `new_text` | `patch_lines(path="main.py", start_line=10, end_line=14, new_text="print('ok')\n")` |
| `replace_text` | 按字面值替换文本 | `path`, `old_text`, `new_text`, `count` | `replace_text(path="config.py", old_text="DEBUG = False", new_text="DEBUG = True")` |
| `mkdir` | 创建目录 | `path`, `parents`, `exist_ok` | `mkdir(path="logs")` |
| `move_path` | 移动或重命名文件/目录 | `source`, `destination`, `overwrite` | `move_path(source="a.txt", destination="backup/a.txt")` |
| `delete_path` | 删除文件或目录 | `path`, `recursive`, `missing_ok` | `delete_path(path="/tmp/build", recursive=true, missing_ok=true)` |
| `zip_paths` | 打包文件或目录 | `paths`, `destination`, `archive_type` | `zip_paths(paths=["src","README.md"], destination="bundle.zip")` |
| `extract_archive` | 解压归档文件 | `archive_path`, `destination_dir`, `overwrite` | `extract_archive(archive_path="bundle.zip", destination_dir="out")` |
| `list_desktop_files` | 列出桌面文件和目录 | 无 | `list_desktop_files()` |
| `find_files` | 按文件名模式递归搜索 | `root`, `pattern`, `max_depth`, `max_results` | `find_files(root=".", pattern="*.py")` |
| `search_text` | 在文本文件中搜索关键字或正则 | `root`, `query`, `use_regex`, `file_pattern` | `search_text(root="src", query="TODO")` |
| `stat_path` | 读取文件或目录元信息 | `path` | `stat_path(path="README.md")` |
| `copy_path` | 复制文件或目录 | `source`, `destination`, `overwrite` | `copy_path(source="a.txt", destination="backup/a.txt")` |
| `hash_file` | 计算文件哈希 | `path`, `algorithm` | `hash_file(path="archive.zip", algorithm="sha256")` |
| `read_binary_file` | 读取二进制文件片段 | `path`, `offset`, `length`, `as_base64` | `read_binary_file(path="image.png", length=256)` |
| `write_binary_file` | 写入二进制文件 | `path`, `content`, `input_encoding`, `mode` | `write_binary_file(path="sample.bin", content="AAECAw==")` |
| `list_recent_files` | 列出最近修改的文件 | `root`, `limit` | `list_recent_files(root=".", limit=20)` |
| `read_json_file` | 读取 JSON 文件并解析 | `path` | `read_json_file(path="package.json")` |
| `write_json_file` | 写入结构化 JSON 数据 | `path`, `data`, `indent`, `ensure_ascii` | `write_json_file(path="config.json", data={"ok": true})` |
| `which_command` | 检查命令是否存在并返回路径 | `name` | `which_command(name="git")` |

### 3.1 代码编辑与大文件阅读建议

如果模型要写代码、改代码、读长文件，建议固定按下面顺序工作：

1. 先用 `list_tree` 看目录结构，或用 `find_files` 按 `*.py`、`*.ts`、`*test*`、`*config*` 之类模式找候选文件。
2. 再用 `search_text` 定位函数名、类名、配置项、路由、报错文本或固定字符串。
3. 命中后再用 `read_file(path=..., start_line=..., end_line=...)` 读取局部上下文，优先每次读 `50` 到 `200` 行。
4. 第一段不够时，再围绕命中行向前后扩读；不要默认把整个大文件一次性读完。
5. 已知行号范围的小改动优先 `patch_lines`。
6. 固定文本、配置值、导入语句之类的稳定替换优先 `replace_text`，必要时配合 `count`。
7. 只有在新建文件、生成完整小文件、或确实需要整体重写时再优先 `write_file`。
8. JSON 配置优先 `read_json_file` 和 `write_json_file`。
9. 改完后再次用 `read_file` 回读已修改片段，再用 `run_shell`、`run_cmd` 或 `run_powershell` 做验证。

推荐组合示例：

```text
list_tree(root="src")
find_files(root="src", pattern="*.py")
search_text(root="src", query="class MyService", file_pattern="*.py")
read_file(path="src/service.py", start_line=120, end_line=220)
patch_lines(path="src/service.py", start_line=156, end_line=168, new_text="...")
read_file(path="src/service.py", start_line=150, end_line=175)
```

如果仓库很大，`search_text` 建议显式传 `file_pattern`，必要时调整 `max_results` 和 `max_file_size_bytes`，避免无关扫描过多。

## 4. 设备类工具

这一类工具主要面向摄像头。

| 工具名 | 用途 | 常见关键参数 | 示例 |
| --- | --- | --- | --- |
| `list_cameras` | 枚举可访问的摄像头设备 | `max_devices` | `list_cameras(max_devices=8)` |
| `capture_camera_photo` | 调用摄像头拍照并保存，必要时直接返回图像内容 | `camera_index`, `output_path`, `return_image_content`, `include_image_preview_text` | `capture_camera_photo(camera_index=0, return_image_content=true)` |

## 5. 值班与等待类工具

这一类工具用于短等待、条件等待、后台值守、任务恢复和交接。

| 工具名 | 用途 | 常见关键参数 | 示例 |
| --- | --- | --- | --- |
| `wait` | 等待一段时间后再继续 | `duration_ms`, `reason` | `wait(duration_ms=5000, reason="等待服务启动")` |
| `wait_until` | 等待到指定时间点再继续 | `timestamp`, `reason` | `wait_until(timestamp="2026-05-01T09:00:00+08:00")` |
| `get_scheduler_time` | 查看当前值班调度器时间、任务统计和调度器健康状态 | 无 | `get_scheduler_time()` |
| `wait_for_file` | 等待文件出现、消失、变大或包含指定文本 | `path`, `state`, `timeout_ms`, `poll_interval_ms`, `min_size_bytes`, `text_contains` | `wait_for_file(path="dist/app.zip", timeout_ms=600000)` |
| `wait_for_process` | 等待进程启动或退出 | `pid`, `name`, `state`, `timeout_ms`, `poll_interval_ms` | `wait_for_process(name="python.exe", state="running", timeout_ms=60000)` |
| `wait_for_port` | 等待端口开放或关闭 | `host`, `port`, `state`, `timeout_ms`, `poll_interval_ms` | `wait_for_port(host="127.0.0.1", port=8000, state="open")` |
| `wait_for_http` | 等待 HTTP/HTTPS 接口恢复到预期状态 | `url`, `expected_statuses`, `timeout_ms`, `poll_interval_ms`, `request_timeout_ms`, `text_contains` | `wait_for_http(url="http://127.0.0.1:8000/health", expected_statuses=[200])` |
| `wait_for_window` | 等待窗口出现、消失或切到前台 | `title_filter`, `hwnd`, `process_name`, `state`, `limit`, `timeout_ms`, `poll_interval_ms` | `wait_for_window(title_filter="Chrome", state="foreground")` |
| `wait_for_desktop_change` | 等待桌面状态变化 | `include_invisible`, `limit`, `baseline_snapshot`, `timeout_ms`, `poll_interval_ms` | `wait_for_desktop_change(timeout_ms=600000, poll_interval_ms=1000)` |
| `create_background_task` | 创建后台值班任务 | `title`, `goal`, `task_type`, `condition`, `poll_interval_ms`, `timeout_ms` | `create_background_task(title="等待服务恢复", goal="等 200", task_type="wait_http", condition={"url":"http://127.0.0.1:8000/health","expected_statuses":[200]})` |
| `list_background_tasks` | 列出后台任务 | `statuses`, `limit` | `list_background_tasks(statuses=["running","waiting_for_condition"])` |
| `get_background_task` | 查看后台任务详情 | `task_id` | `get_background_task(task_id="...")` |
| `cancel_background_task` | 取消后台任务 | `task_id`, `reason` | `cancel_background_task(task_id="...", reason="不再需要")` |
| `pause_background_task` | 暂停后台任务 | `task_id`, `reason` | `pause_background_task(task_id="...", reason="等待确认")` |
| `resume_background_task` | 恢复后台任务 | `task_id`, `reason` | `resume_background_task(task_id="...", reason="继续值班")` |
| `wait_for_background_task` | 同步等待后台任务进入目标状态 | `task_id`, `target_statuses`, `timeout_ms`, `poll_interval_ms` | `wait_for_background_task(task_id="...", timeout_ms=60000)` |
| `create_task_plan` | 给后台任务补步骤计划 | `task_id`, `steps` | `create_task_plan(task_id="...", steps=["观察","等待","验证","汇总"])` |
| `update_task_step` | 更新后台任务步骤状态 | `task_id`, `step_index`, `status`, `note` | `update_task_step(task_id="...", step_index=2, status="completed")` |
| `append_task_event` | 追加任务事件 | `task_id`, `message`, `event_type`, `data` | `append_task_event(task_id="...", event_type="decision", message="进入验证阶段")` |
| `record_task_artifact` | 记录任务产物 | `task_id`, `path`, `description` | `record_task_artifact(task_id="...", path="dist/app.zip", description="最终产物")` |
| `summarize_background_task` | 生成后台任务交接摘要 | `task_id`, `include_recent_events` | `summarize_background_task(task_id="...", include_recent_events=20)` |
| `get_task_handoff` | 生成更适合重连接手的交接摘要 | `task_id`, `include_recent_events` | `get_task_handoff(task_id="...", include_recent_events=20)` |
| `mark_task_waiting_for_user` | 标记任务当前需要用户决定 | `task_id`, `question` | `mark_task_waiting_for_user(task_id="...", question="是否继续重试到明早？")` |
| `mark_task_waiting_for_condition` | 显式标记当前在等待某个条件 | `task_id`, `note` | `mark_task_waiting_for_condition(task_id="...", note="等待端口 8000 开放")` |

## 6. 窗口与桌面类工具

这一类工具用于了解当前图形界面状态，适合配合支持视觉的模型一起使用。

| 工具名 | 用途 | 常见关键参数 | 示例 |
| --- | --- | --- | --- |
| `list_windows` | 枚举窗口标题、句柄、进程和前后台状态 | `include_invisible`, `title_filter`, `limit` | `list_windows(title_filter="Chrome")` |
| `get_active_window` | 读取当前前台窗口信息 | 无 | `get_active_window()` |
| `get_desktop_context` | 一次返回前台窗口和后台窗口列表 | `limit`, `include_invisible` | `get_desktop_context(limit=50)` |
| `capture_screenshot` | 截取当前桌面截图并保存，必要时直接返回图像内容 | `output_path`, `all_screens`, `return_image_content`, `include_image_preview_text` | `capture_screenshot(all_screens=true, return_image_content=true)` |

## 7. 网络与网页类工具

这一类工具覆盖 HTTP 头探测、普通请求、网页表单提交、文件上传、重定向、下载、网页正文提取、网页转 Markdown、超链接提取、表格提取、元素提取、DNS、反向解析、TLS 证书、ping、路由追踪、TCP/UDP 原始收发、WebSocket 调试、端口扫描、已建立连接和监听端口。

| 工具名 | 用途 | 常见关键参数 | 示例 |
| --- | --- | --- | --- |
| `download_file` | 下载网络文件到本地 | `url`, `destination`, `headers`, `timeout_ms`, `overwrite` | `download_file(url="https://example.com/file.zip", destination="downloads/file.zip", timeout_ms=180000)` |
| `http_head` | 对 URL 发起 HEAD 请求 | `url`, `headers`, `timeout_ms` | `http_head(url="https://example.com/file.zip", timeout_ms=60000)` |
| `fetch_response_headers` | 读取 HTTP/HTTPS 响应头 | `url`, `method`, `headers`, `body`, `timeout_ms` | `fetch_response_headers(url="https://example.com/api/info")` |
| `http_request` | 发起 HTTP/HTTPS 请求 | `url`, `method`, `headers`, `body`, `timeout_ms`, `save_to` | `http_request(url="https://example.com/api", timeout_ms=60000)` |
| `submit_web_form` | 提交网页表单 | `url`, `form_fields`, `method`, `encoding`, `timeout_ms`, `save_to` | `submit_web_form(url="https://example.com/search", method="GET", form_fields={"q":"mcp tools"})` |
| `upload_file` | 上传本地文件到网络接口 | `url`, `file_path`, `method`, `upload_mode`, `field_name`, `form_fields`, `timeout_ms` | `upload_file(url="https://example.com/upload", file_path="dist/app.zip", form_fields={"project":"allcanuse"})` |
| `trace_http_redirects` | 追踪 HTTP 重定向链 | `url`, `headers`, `timeout_ms`, `max_hops` | `trace_http_redirects(url="http://example.com")` |
| `fetch_webpage_text` | 抓取网页并提取主要正文文字 | `url`, `headers`, `timeout_ms`, `max_text_chars`, `include_title` | `fetch_webpage_text(url="https://example.com/docs", max_text_chars=40000)` |
| `webpage_to_markdown` | 抓取网页并转换成 Markdown | `url`, `headers`, `timeout_ms`, `max_markdown_chars` | `webpage_to_markdown(url="https://example.com/docs")` |
| `extract_links_from_webpage` | 提取网页中的超链接 | `url`, `text_filter`, `href_filter`, `max_links`, `timeout_ms` | `extract_links_from_webpage(url="https://example.com", href_filter=".pdf")` |
| `extract_tables_from_webpage` | 提取网页中的 HTML 表格 | `url`, `headers`, `timeout_ms`, `max_tables`, `max_rows_per_table` | `extract_tables_from_webpage(url="https://example.com/table-page")` |
| `extract_webpage_elements` | 按标签名和属性提取特定网页元素 | `url`, `tag`, `attr_filters`, `max_elements`, `timeout_ms` | `extract_webpage_elements(url="https://example.com", tag="meta", attr_filters={"name":"description"})` |
| `resolve_dns_records` | 查询 DNS 多种记录类型 | `hostname`, `record_types`, `dns_server`, `timeout_ms` | `resolve_dns_records(hostname="example.com", record_types=["MX","TXT"])` |
| `reverse_dns_lookup` | 对 IP 做反向 DNS 查询 | `ip_address` | `reverse_dns_lookup(ip_address="8.8.8.8")` |
| `dns_lookup` | 解析域名到 IP | `hostname` | `dns_lookup(hostname="example.com")` |
| `get_tls_certificate` | 读取 TLS/HTTPS 证书信息 | `host`, `port`, `server_hostname`, `timeout_ms`, `verify` | `get_tls_certificate(host="example.com")` |
| `ping_host` | 对目标执行 ping 测试 | `hostname`, `count`, `timeout_ms` | `ping_host(hostname="127.0.0.1", count=4)` |
| `trace_route` | 执行 traceroute / tracert | `host`, `max_hops`, `timeout_ms` | `trace_route(host="example.com")` |
| `tcp_connect` | 测试 TCP 端口是否可连接 | `host`, `port`, `timeout_ms` | `tcp_connect(host="127.0.0.1", port=443, timeout_ms=10000)` |
| `raw_tcp_exchange` | 发送原始 TCP 数据并读取响应 | `host`, `port`, `data`, `timeout_ms`, `input_encoding`, `output_encoding` | `raw_tcp_exchange(host="127.0.0.1", port=6379, data="PING\\r\\n")` |
| `udp_send_receive` | 发送 UDP 数据并等待响应 | `host`, `port`, `data`, `timeout_ms`, `input_encoding`, `output_encoding` | `udp_send_receive(host="127.0.0.1", port=5353, data="hello")` |
| `websocket_connect` | 连接 WebSocket 接口并收发文本消息 | `url`, `messages`, `subprotocols`, `timeout_ms`, `receive_limit` | `websocket_connect(url="ws://127.0.0.1:8765/echo", messages=["hello"])` |
| `scan_ports` | 扫描一组 TCP 端口或一个端口范围 | `host`, `ports`, `start_port`, `end_port`, `timeout_ms`, `open_only` | `scan_ports(host="127.0.0.1", start_port=8000, end_port=8100)` |
| `list_established_connections` | 列出当前已建立连接 | `limit` | `list_established_connections(limit=500)` |
| `list_listening_ports` | 列出当前主机监听端口 | 无 | `list_listening_ports()` |

## 8. 推荐模型使用顺序

如果模型刚接入当前环境，推荐优先这样做：

1. 先调 `list_all_tools()`，确认工具列表。
2. 再调 `get_system_info()`、`get_env()`、`get_network_config()` 了解环境。
3. 处理代码或文本时优先用 `list_tree()`、`find_files()`、`search_text()`、`read_file()`、`patch_lines()`。
4. 长代码文件先搜索再按行分段读取，不要默认整文件读取。
4. 处理桌面任务时优先用 `get_desktop_context()`；需要模型直接理解截图时优先 `capture_screenshot(return_image_content=true)`。
5. 需要值班或用户长时间离线时，优先把长期等待动作转成 `create_background_task()`，并配合 `create_task_plan()`、`append_task_event()`、`record_task_artifact()` 记录过程；重新接手时优先看 `get_task_handoff()`。
6. 处理网页时优先用 `trace_http_redirects()`、`http_head()` 或 `fetch_response_headers()` 先看头部，再用 `fetch_webpage_text()`、`webpage_to_markdown()` 读正文；找链接时再用 `extract_links_from_webpage()`，需要表格时用 `extract_tables_from_webpage()`，需要精确抓标签时再用 `extract_webpage_elements()`，需要提交表单时用 `submit_web_form()`，需要上传本地文件时用 `upload_file()`。
7. 网络或长时任务尽量显式传 `timeout_ms`。

## 8. 额外说明

- 当前项目除了 tools 以外，还提供了面向模型的 guide resources 和 prompt。
- 如果某个工具调用失败并明确提示缺少依赖，模型可以使用现有命令工具安装最小必需依赖后再继续。
- 最权威的运行时工具清单仍然是 `list_all_tools(include_descriptions=true)` 的返回结果。
