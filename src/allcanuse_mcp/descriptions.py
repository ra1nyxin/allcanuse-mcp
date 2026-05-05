from __future__ import annotations

from datetime import datetime, timezone as dt_timezone
from textwrap import dedent


BASE_SERVER_INSTRUCTIONS = dedent(
    """
    你正在操作一台 Windows 或 Linux 实验环境主机，当前 MCP Server 已经暴露了一组可直接调用的系统工具。

    核心原则：
    1. 这些工具就是你的手、眼睛和操作能力。需要观察、读取、判断、修改、验证时，就应主动调用工具，不要无谓回避工具。
    2. 不要只停留在口头建议。如果任务可以通过工具继续推进，就直接用工具推进。
    3. 遇到多步任务时，优先把它拆成“观察 -> 判断 -> 执行 -> 验证”四段，并在每一段主动选择合适工具。
    4. 工具之间可以组合使用；组合工具通常比单次猜测更可靠。

    工作方式：
    1. 先根据任务选择最合适的工具，不要空想，不要盲猜；该看就看，该查就查。
    2. 优先使用结构化工具，而不是把所有事情都交给 shell。
    3. 当需要查看代码或文件时，优先使用 `list_tree`、`read_file`、`find_files`、`search_text`、`replace_text`、`patch_lines`、`write_file`。
    4. 当需要执行系统动作时，优先根据场景选择 `run_shell`、`run_cmd`、`run_powershell`、`start_process`、`kill_process`。
    5. 当需要了解图形界面状态时，使用 `get_desktop_context`、`get_active_window`、`list_windows`、`capture_screenshot`。
    6. 当需要判断网络状态或读取网页时，优先使用 `get_network_config`、`list_network_adapters`、`resolve_dns_records`、`dns_lookup`、`reverse_dns_lookup`、`ping_host`、`tcp_connect`、`raw_tcp_exchange`、`udp_send_receive`、`websocket_connect`、`http_head`、`fetch_response_headers`、`http_request`、`submit_web_form`、`upload_file`、`trace_http_redirects`、`download_file`、`get_tls_certificate`、`fetch_webpage_text`、`extract_webpage_metadata`、`extract_links_from_webpage`、`extract_webpage_elements`、`crawl_webpages`、`list_established_connections`。
    7. 当需要值班、等待条件变化、在用户离开后继续观察任务时，优先使用 `wait`、`wait_until`、`wait_for_file`、`wait_for_process`、`wait_for_port`、`wait_for_http`、`wait_for_window`、`wait_for_desktop_change`、`create_background_task`、`list_background_tasks`、`get_background_task`、`wait_for_background_task`、`summarize_background_task`、`get_task_handoff`。
    8. 当 MCP 已经提供了本地可用工具时，优先直接调用工具，而不是为了同类能力额外安装新库。
    9. 不要因为担心多调用工具而放弃获取必要上下文。只要工具与当前任务直接相关，就应该使用。
    10. 如果任务是长时间实验、长时间训练、长时间推理、长时间服务、可能持续几小时到几天的后台程序，不要只把它当普通临时进程启动。优先使用长时进程工具登记并保护它，后续只监视、记录、汇报；除非用户明确要求停止，否则不要主动结束这类进程。

    推荐组合方式：
    - 代码任务：`list_tree/find_files` -> `search_text/read_file` -> `patch_lines/replace_text/write_file` -> `run_shell` 验证
    - 网页任务：`trace_http_redirects` -> `http_head/fetch_response_headers` -> `fetch_webpage_text/webpage_to_markdown` -> `extract_webpage_metadata` -> `extract_links_from_webpage` 或 `crawl_webpages` -> `extract_webpage_elements/extract_tables_from_webpage` -> `submit_web_form/upload_file/download_file`
    - 桌面任务：`get_desktop_context` -> `get_active_window/list_windows` -> `capture_screenshot`
    - 网络任务：`get_network_config` -> `resolve_dns_records/dns_lookup/ping_host` -> `tcp_connect/raw_tcp_exchange/udp_send_receive/websocket_connect` -> `http_head/fetch_response_headers/http_request/get_tls_certificate`
    - 进程任务：`list_processes` -> `get_process_tree/find_port_process` -> `kill_process/start_process`
    - 长时实验任务：`start_managed_process` -> `get_managed_process/list_managed_processes` -> `wait_for_process` 或 `create_background_task` -> `note_managed_process` -> 只有用户明确要求时才 `stop_managed_process`
    - 值班任务：`create_background_task` -> `create_task_plan` -> `append_task_event/record_task_artifact` -> `wait_for_window/wait_for_desktop_change` -> `get_background_task/list_background_tasks` -> `summarize_background_task/get_task_handoff`

    值班模式判断规则：
    - 如果只是几秒到几十秒的短暂停顿，并且你会在当前回复里继续处理，优先用 `wait` 或 `wait_until`，不要急着托管后台任务。
    - 如果等待的是明确条件，例如文件生成、端口开放、窗口出现、前台切换、桌面变化，优先用对应的 `wait_for_*`。
    - 如果用户会离开、去睡觉、稍后再回来，或者任务本身可能跨会话、跨重连持续几分钟到几小时，优先立刻用 `create_background_task` 托管，不要只停在“我等等看”。
    - 如果任务托管后还需要后续交接，尽早补 `create_task_plan`、`append_task_event`、`record_task_artifact`，不要等任务快结束时才补记录。
    - 如果当前必须等待用户决定才能继续，优先用 `mark_task_waiting_for_user` 明确卡点；如果只是等外部条件成熟，优先用 `mark_task_waiting_for_condition`。
    - 重新接手老任务、断线重连、跨模型交接时，优先用 `get_task_handoff`，必要时再看 `get_background_task` 或 `summarize_background_task`。

    常见值班场景示例：
    - 用户说“我去吃饭了，你继续盯安装器”：优先 `create_background_task(task_type='wait_window' 或 'wait_desktop_change')`，并记录步骤与事件。
    - 用户说“等服务恢复后你自己继续测”：优先 `create_background_task(task_type='wait_http')`，恢复后再由新会话读取 handoff 继续。
    - 用户说“我今晚不在，你值班到明早”：不要在当前回复里空等，应把长期观察条件托管成后台任务，并写清楚下一步计划。
    - 用户说“我马上回来，等 10 秒再继续”：这种短等待优先 `wait(duration_ms=...)`，不必创建后台任务。

    结果处理要求：
    - 先读取环境，再执行修改。
    - 先观察，再下结论；先验证，再结束任务。
    - 命令输出可能很长，优先设置合理的 `max_output_chars`。
    - 网络和长时工具优先显式传入 `timeout_ms`，按任务需要自行调整。
    - 读网页时不要默认只读当前页；如果当前页明显是目录页、导航页、列表页、文档首页、搜索结果页或聚合页，应继续进入其中最相关的站内链接收集内容。
    - 当网页里出现目录、章节导航、上一篇/下一篇、详情页、文档页、下载页、API 页、FAQ 页等入口时，应把它们视为后续探索候选，而不是停在表面摘要。
    - 处理文件时请显式传入目标路径，必要时先调用 `list_tree` 或 `read_file` 确认内容。
    - 如果一个任务需要多步完成，请基于工具输出逐步决策。
    - 如果工具提示缺少系统命令或 Python 依赖，并且当前任务确实需要它，你可以使用 shell 工具安装最小必需依赖后再继续。
    - 如果你亲手启动了一个长时间实验或推理进程，默认把它视为“持续工作的被托管对象”而不是“做完当前回复就该清理的临时子进程”；除非用户明确说“停止”“关闭”“杀掉”“结束实验”，否则不要主动调用 `kill_process` 结束它。
    - 如果本机访问海外网站、`git clone`、`git push`、`pip install`、`npm install`、`apt install` 或其他海外网络相关动作因超时、连接失败、TLS 握手异常、拉取失败而受阻，不要立刻放弃。先检查本机是否已有可复用代理：优先看 `list_listening_ports` / `find_port_process` 是否存在 `7890`、`7897`、`46464` 等常见代理监听端口，再看 `list_processes` 是否存在 `v2rayN`、`Clash for Windows`、`clash`、`clash-core-service` 等代理进程，必要时也查看 `get_env` 里的代理环境变量。
    - 如果已经发现本机代理存在，就直接在后续网络命令、下载命令、Git、pip、npm、apt 等动作里显式带上代理设置后重试，而不是停在第一次失败。
    - 如果代理端口和代理进程都没有发现，或者带代理重试后仍失败，再明确询问用户是否已经开启代理软件，并请用户协助打开代理后继续。

    你可以充分使用当前 MCP Server 已暴露的工具来完成任务。工具不是装饰，而是默认工作方式；应主动、合理、连续地使用与当前任务直接相关的工具。
    """
).strip()


def render_runtime_context_text() -> str:
    local_now = datetime.now().astimezone()
    utc_now = datetime.now(dt_timezone.utc)
    return (
        f"当前本地时间：{local_now.isoformat()}。"
        f"当前本地时区：{local_now.tzinfo}。"
        f"当前 UTC 时间：{utc_now.isoformat()}。"
        "处理“现在、今天、今晚、明天、一小时后、到点、截止时间、值班轮换”等时间相关任务时，默认以这里的时间上下文为准；"
        "如果任务跨较长时间跨度，或你怀疑时间已经推进较多，再调用 `get_time` 或 `get_scheduler_time` 复核。"
    )


def build_server_instructions() -> str:
    return (
        f"{BASE_SERVER_INSTRUCTIONS}\n\n"
        "实时时间上下文：\n"
        f"- {render_runtime_context_text()}"
    )


SERVER_INSTRUCTIONS = build_server_instructions()


def _doc(title: str, body: str) -> str:
    return f"{title}\n\n{dedent(body).strip()}"


TOOL_DESCRIPTIONS: dict[str, str] = {
    "list_all_tools": _doc(
        "汇总当前 MCP Server 暴露的全部工具。",
        """
        输入：
        - `include_descriptions`: 是否附带完整说明，默认 `false`

        适用场景：
        - 模型想快速查看当前有哪些工具可用
        - 某些客户端拿不到原生 MCP 工具列表时的兜底入口

        调用示例：
        - `list_all_tools()`
        - `list_all_tools(include_descriptions=True)`
        """,
    ),
    "get_system_info": _doc(
        "读取当前主机的系统概况。",
        """
        适用场景：
        - 判断当前机器架构、CPU、内存、启动时间
        - 确认系统版本、主机名、Python 环境

        输入：
        - 无

        调用示例：
        - `get_system_info()`
        """,
    ),
    "get_env": _doc(
        "读取环境变量。",
        """
        输入：
        - `names`: 可选，只读取指定变量名；留空时返回全部环境变量

        适用场景：
        - 检查 `PATH`、`HOME`、`USERPROFILE`、代理变量、模型运行环境变量

        调用示例：
        - `get_env()`
        - `get_env(names=["PATH", "HOME", "USERPROFILE"])`
        """,
    ),
    "get_time": _doc(
        "获取本地时间、UTC 时间，以及可选时区的当前时间。",
        """
        输入：
        - `timezone`: 可选，例如 `Asia/Shanghai`、`UTC`、`America/New_York`

        调用示例：
        - `get_time()`
        - `get_time(timezone="UTC")`
        """,
    ),
    "get_disk_usage": _doc(
        "获取指定路径所在磁盘或挂载点的空间占用情况。",
        """
        输入：
        - `path`: 要检查的路径，例如 `C:\\`、`D:\\project`、`/`、`/home/user/project`

        返回：
        - 总空间、已用空间、可用空间、百分比

        调用示例：
        - `get_disk_usage(path="C:\\")`
        - `get_disk_usage(path="/")`
        """,
    ),
    "get_network_config": _doc(
        "获取当前主机的网络配置摘要。",
        """
        平台行为：
        - Windows 下执行 `ipconfig /all`
        - Linux 下优先执行 `ip addr` 和 `ip route`

        输入：
        - `max_output_chars`: 限制返回文本长度，默认 `12000`
        - `timeout_ms`: 执行超时毫秒数，默认 `30000`

        调用示例：
        - `get_network_config()`
        - `get_network_config(max_output_chars=4000, timeout_ms=60000)`
        """,
    ),
    "get_ipconfig": _doc(
        "兼容旧调用名的网络配置工具。",
        """
        输入：
        - `max_output_chars`: 限制返回文本长度，默认 `12000`
        - `timeout_ms`: 执行超时毫秒数，默认 `30000`

        调用示例：
        - `get_ipconfig()`
        - `get_ipconfig(timeout_ms=60000)`
        """,
    ),
    "list_network_adapters": _doc(
        "读取当前主机所有网络适配器和地址信息。",
        """
        输入：
        - 无

        调用示例：
        - `list_network_adapters()`
        """,
    ),
    "wait": _doc(
        "等待一段时间后再继续，适合短暂停顿、轮询前休眠或在同一轮工具调用里延后下一步动作。",
        """
        输入：
        - `duration_ms`: 等待毫秒数
        - `reason`: 可选，记录等待原因

        适用场景：
        - 等待进程启动几秒
        - 等待下载、安装、解压或编译稍微推进一会儿
        - 用户明确要求“过一会儿再查一次”
        - 当前只是几秒到几十秒的短暂停顿，没必要立刻托管后台任务

        调用示例：
        - `wait(duration_ms=5000, reason="等待服务启动")`
        - `wait(duration_ms=30000, reason="等安装器先跑完这一阶段")`
        - `wait(duration_ms=10000, reason="稍后再检查一次端口是否开放")`

        什么时候用它：
        - 你会在同一轮回复里继续推进，不需要跨会话托管
        - 你只是想给外部系统一点启动、缓冲、刷新的时间

        不要用它的场景：
        - 用户说要离开一小时、去睡觉、明早再看
        - 等待时间不可控，明显会跨会话
        - 你已经知道后面要持续检查多个条件
        """,
    ),
    "wait_until": _doc(
        "等待到指定时间点再继续，适合值班场景下按绝对时间继续检查或执行下一步。",
        """
        输入：
        - `timestamp`: ISO 8601 时间，例如 `2026-05-01T09:00:00+08:00`
        - `reason`: 可选，记录等待原因

        调用示例：
        - `wait_until(timestamp="2026-05-01T09:00:00+08:00", reason="等到明早再继续巡检")`
        - `wait_until(timestamp="2026-05-01T15:00:00+08:00", reason="到点后继续验证服务状态")`
        - `wait_until(timestamp="2026-05-01T22:30:00+08:00", reason="用户回来前先等到约定时间")`

        什么时候用它：
        - 用户给了明确的时间点，而不是模糊的“过会儿”
        - 你想按时恢复检查、回报或执行下一步

        推荐组合：
        - 先 `wait_until`，到点后再 `get_scheduler_time` 看调度器状态，必要时接着 `get_task_handoff`
        """,
    ),
    "get_scheduler_time": _doc(
        "读取当前值班调度器时间、时区、单调时钟和后台任务状态统计。",
        """
        输入：
        - 无

        返回补充：
        - `scheduler.running`: 调度线程当前是否存活
        - `scheduler.last_error`: 最近一次调度器级异常
        - `scheduler.last_error_at`: 最近一次调度器级异常时间

        调用示例：
        - `get_scheduler_time()`
        - `get_scheduler_time()` 配合 `wait_until` 或 `create_background_task` 检查当前值班节奏

        什么时候用它：
        - 你想确认当前调度器还活着，后台任务有没有在跑
        - 你想知道当前时间，决定是继续同步等待还是切后台托管
        """,
    ),
    "wait_for_file": _doc(
        "等待文件出现或消失，也可要求文件达到最小大小或包含指定文本。",
        """
        输入：
        - `path`: 目标文件路径
        - `state`: `exists` 或 `missing`
        - `timeout_ms`: 最长等待多久
        - `poll_interval_ms`: 每次检查间隔
        - `min_size_bytes`: 可选，要求文件至少达到多少字节
        - `text_contains`: 可选，要求文件内容包含某段文本
        - `encoding`: 读取文本时使用的编码

        调用示例：
        - `wait_for_file(path="build/output.zip", timeout_ms=600000, poll_interval_ms=2000)`
        - `wait_for_file(path="logs/server.log", text_contains="Started", timeout_ms=120000)`
        """,
    ),
    "wait_for_process": _doc(
        "等待指定进程开始运行或退出，适合守护长任务、安装程序或后台服务。",
        """
        输入：
        - `pid`: 可选，指定 PID
        - `name`: 可选，指定进程名
        - `state`: `running` 或 `exited`
        - `timeout_ms`: 最长等待多久
        - `poll_interval_ms`: 检查间隔

        使用规则：
        - `pid` 和 `name` 至少传一个

        调用示例：
        - `wait_for_process(name="python.exe", state="running", timeout_ms=60000)`
        - `wait_for_process(pid=1234, state="exited", timeout_ms=3600000, poll_interval_ms=5000)`
        """,
    ),
    "wait_for_port": _doc(
        "等待某个 TCP 端口开放或关闭，适合等本地服务启动、关闭或重启完成。",
        """
        输入：
        - `host`: 目标主机
        - `port`: 目标端口
        - `state`: `open` 或 `closed`
        - `timeout_ms`: 最长等待多久
        - `poll_interval_ms`: 检查间隔
        - `connect_timeout_ms`: 单次连通性探测超时

        调用示例：
        - `wait_for_port(host="127.0.0.1", port=8000, state="open", timeout_ms=120000)`
        - `wait_for_port(host="127.0.0.1", port=3306, state="closed", timeout_ms=30000)`
        """,
    ),
    "wait_for_http": _doc(
        "等待某个 HTTP/HTTPS 接口恢复到预期状态码，也可要求响应正文包含指定文本。",
        """
        输入：
        - `url`: 目标地址
        - `expected_statuses`: 预期状态码列表，默认 `[200]`
        - `method`: 请求方法
        - `headers`: 可选请求头
        - `body`: 可选请求体
        - `timeout_ms`: 最长等待多久
        - `poll_interval_ms`: 检查间隔
        - `request_timeout_ms`: 单次请求超时
        - `text_contains`: 可选，要求响应包含某段文本

        调用示例：
        - `wait_for_http(url="https://example.com/health", expected_statuses=[200,204], timeout_ms=300000)`
        - `wait_for_http(url="http://127.0.0.1:8000/", text_contains="ready", timeout_ms=120000)`
        """,
    ),
    "wait_for_window": _doc(
        "等待某个窗口出现、消失或切到前台，适合值班观察安装器、浏览器、IDE、终端或实验程序窗口状态。",
        """
        输入：
        - `title_filter`: 可选，按窗口标题做不区分大小写的包含匹配
        - `hwnd`: 可选，按窗口句柄精确匹配
        - `process_name`: 可选，按进程名匹配
        - `state`: `appeared`、`missing` 或 `foreground`
        - `include_invisible`: 是否把不可见窗口也纳入匹配
        - `limit`: 单次检查最多扫描多少个窗口，默认 `500`
        - `timeout_ms`: 最长等待多久
        - `poll_interval_ms`: 轮询间隔

        使用规则：
        - `title_filter`、`hwnd`、`process_name` 至少传一个
        - 想等某个窗口切到最前面时优先用 `state="foreground"`

        调用示例：
        - `wait_for_window(title_filter="Setup", state="appeared", timeout_ms=300000)`
        - `wait_for_window(title_filter="Chrome", state="foreground", poll_interval_ms=1000)`
        """,
    ),
    "wait_for_desktop_change": _doc(
        "记录当前桌面快照后持续观察，一旦前台窗口或窗口集合发生变化就返回，适合值班盯安装器、弹窗、程序切换和实验界面状态。",
        """
        输入：
        - `include_invisible`: 是否把不可见窗口也纳入桌面签名
        - `limit`: 快照里最多记录多少个窗口
        - `baseline_snapshot`: 可选，手动传入基线快照；不传时自动以调用当下的桌面状态作为基线
        - `timeout_ms`: 最长等待多久
        - `poll_interval_ms`: 轮询间隔

        调用示例：
        - `wait_for_desktop_change(timeout_ms=600000, poll_interval_ms=1000)`
        - `wait_for_desktop_change(include_invisible=True, limit=100, timeout_ms=120000)`
        """,
    ),
    "create_background_task": _doc(
        "创建一个后台值班任务，让 MCP 调度器在用户不在线时持续等待和检查条件。",
        """
        输入：
        - `title`: 任务标题
        - `goal`: 任务目标
        - `task_type`: 当前支持 `sleep`、`wait_file`、`wait_process`、`wait_port`、`wait_http`、`wait_window`、`wait_desktop_change`
        - `condition`: 任务条件字典
        - `poll_interval_ms`: 轮询间隔
        - `timeout_ms`: 可选，任务总超时
        - `priority`: 优先级
        - `owner`: 可选，当前接手该任务的模型或会话标识
        - `tags`: 可选标签列表
        - `notes`: 可选备注

        适用场景：
        - 用户离开后让模型持续值班
        - 长时间等待端口开放、文件生成、接口恢复
        - 让模型重连后还能继续接手任务
        - 用户一句话让模型“自己做某某事一个小时”时，应该优先把工作拆成后台任务而不是同步空等

        调用示例：
        - `create_background_task(title="等待构建产物", goal="等到打包结果出现", task_type="wait_file", condition={"path":"dist/app.zip","state":"exists"}, poll_interval_ms=3000, timeout_ms=1800000)`
        - `create_background_task(title="等待服务恢复", goal="等本地服务回到 200", task_type="wait_http", condition={"url":"http://127.0.0.1:8000/health","expected_statuses":[200]}, poll_interval_ms=5000, timeout_ms=3600000)`
        - `create_background_task(title="等安装器弹窗", goal="等安装向导窗口出现", task_type="wait_window", condition={"title_filter":"Setup","state":"appeared"}, poll_interval_ms=1000, timeout_ms=900000)`
        - `create_background_task(title="值班一小时", goal="在接下来一小时内持续观察安装、服务和日志", task_type="sleep", condition={"until":"2026-05-01T15:00:00+08:00"}, poll_interval_ms=3000, timeout_ms=3600000)`

        什么时候立即创建它：
        - 用户说“你自己盯一个小时”
        - 用户说“我去吃饭/睡觉/出门，回来前都由你负责”
        - 需要在用户不在线时持续轮询、记录、等待、交接

        创建后应该马上做什么：
        - 先 `create_task_plan` 把 3 到 6 个关键步骤列出来
        - 再 `append_task_event` 记录当前初始判断
        - 如果有产物先用 `record_task_artifact`
        - 必要时先用 `get_task_handoff` 产出交接摘要，防止会话中断后丢上下文

        任务提前完成时怎么做：
        - 先补 `append_task_event` 说明已完成
        - 再 `record_task_artifact` 记录产物
        - 再 `summarize_background_task` 或 `get_task_handoff` 做收口
        - 如果用户原本要求的是一小时，但实际上十分钟就完成了，不要空等到一小时结束；可以直接转向下一项相关检查，或者把后台任务标记清楚后继续新的任务
        """,
    ),
    "list_background_tasks": _doc(
        "列出当前所有后台值班任务，可按状态过滤。",
        """
        输入：
        - `statuses`: 可选状态过滤列表
        - `limit`: 最多返回多少条

        调用示例：
        - `list_background_tasks()`
        - `list_background_tasks(statuses=["running","waiting_for_condition"], limit=200)`
        - `list_background_tasks(statuses=["completed"], limit=50)`

        什么时候用它：
        - 想看看当前是否已经有一个一小时值班任务在跑
        - 想快速确认哪些任务还在等待、哪些已完成、哪些失败
        """,
    ),
    "get_background_task": _doc(
        "读取某个后台任务的完整状态、条件、最近结果、步骤和产物。",
        """
        输入：
        - `task_id`: 任务 ID

        调用示例：
        - `get_background_task(task_id="...")`
        - `get_background_task(task_id="...")` 用来确认当前步骤、阻塞点和剩余超时

        什么时候用它：
        - 你想知道后台任务现在卡在哪
        - 你想看最新轮询结果、最近事件和已有产物
        """,
    ),
    "cancel_background_task": _doc(
        "取消一个后台值班任务。",
        """
        输入：
        - `task_id`: 任务 ID
        - `reason`: 可选取消原因

        调用示例：
        - `cancel_background_task(task_id="...", reason="用户不再需要继续等待")`

        什么时候用它：
        - 用户改主意了
        - 目标已经不再需要继续等
        - 任务已经完成且你确认不需要继续轮询
        """,
    ),
    "pause_background_task": _doc(
        "暂停一个后台值班任务，暂停后调度器不会继续轮询它。",
        """
        输入：
        - `task_id`: 任务 ID
        - `reason`: 可选暂停原因

        调用示例：
        - `pause_background_task(task_id="...", reason="先暂停，等用户确认")`

        什么时候用它：
        - 你暂时不想让它继续检查，但又不想彻底丢掉任务
        - 用户离开了，但你还不确定下一步是否要继续
        """,
    ),
    "resume_background_task": _doc(
        "恢复一个已暂停或等待用户的后台任务。",
        """
        输入：
        - `task_id`: 任务 ID
        - `reason`: 可选恢复原因

        调用示例：
        - `resume_background_task(task_id="...", reason="继续值班")`

        什么时候用它：
        - 用户回来并确认可以继续
        - 暂停后又决定恢复轮询
        """,
    ),
    "wait_for_background_task": _doc(
        "在当前会话里等待某个后台任务进入目标状态，适合创建后台任务后同步等一小段时间看结果。",
        """
        输入：
        - `task_id`: 任务 ID
        - `target_statuses`: 目标状态列表，默认 `completed`、`failed`、`cancelled`
        - `timeout_ms`: 最长等待多久
        - `poll_interval_ms`: 轮询间隔

        调用示例：
        - `wait_for_background_task(task_id="...", timeout_ms=60000)`
        - `wait_for_background_task(task_id="...", target_statuses=["completed","failed"], timeout_ms=300000)`

        什么时候用它：
        - 你已经创建了后台任务，想在当前会话里短等一小会儿看是否立刻完成
        - 你想在等待期间继续拿到任务最终状态，而不是等下次会话再看
        """,
    ),
    "create_task_plan": _doc(
        "给某个后台任务附加步骤计划，方便后续交接、恢复和总结。",
        """
        输入：
        - `task_id`: 任务 ID
        - `steps`: 步骤标题列表

        调用示例：
        - `create_task_plan(task_id="...", steps=["观察日志","等待端口开放","验证 HTTP 200","汇总结果"])`
        - `create_task_plan(task_id="...", steps=["先托管一小时","每 10 分钟检查一次","完成后收口交接"])`

        什么时候用它：
        - 任务较长，准备分多步推进
        - 你想让后续接手的人一眼看懂整个流程
        """,
    ),
    "update_task_step": _doc(
        "更新后台任务某个步骤的状态和备注。",
        """
        输入：
        - `task_id`: 任务 ID
        - `step_index`: 步骤序号，从 1 开始
        - `status`: `pending`、`in_progress`、`completed`、`failed`、`skipped`
        - `note`: 可选备注

        调用示例：
        - `update_task_step(task_id="...", step_index=2, status="completed", note="端口已开放")`
        - `update_task_step(task_id="...", step_index=1, status="in_progress", note="开始一小时值班")`

        什么时候用它：
        - 你已经有任务步骤计划，想标记当前进度
        - 想把“已经做完了什么”显式写到任务里
        """,
    ),
    "append_task_event": _doc(
        "向后台任务追加一条人工事件，适合记录判断、错误、提醒和中间结论。",
        """
        输入：
        - `task_id`: 任务 ID
        - `message`: 事件内容
        - `event_type`: 事件类型，例如 `info`、`warning`、`decision`、`error`
        - `data`: 可选附加结构化数据

        调用示例：
        - `append_task_event(task_id="...", event_type="decision", message="网络已恢复，转入 HTTP 验证阶段")`
        - `append_task_event(task_id="...", event_type="info", message="已创建一小时值班任务，开始第一轮检查")`
        - `append_task_event(task_id="...", event_type="warning", message="当前还没到点，继续观察")`

        什么时候用它：
        - 你做出一个关键判断
        - 你想记录某次轮询结果、失败原因或重试理由
        - 任务提前完成或任务超时，都应该用它收尾说明
        """,
    ),
    "record_task_artifact": _doc(
        "记录某个后台任务产出的文件或目录，方便后续交接和总结。",
        """
        输入：
        - `task_id`: 任务 ID
        - `path`: 产物路径
        - `description`: 可选说明

        调用示例：
        - `record_task_artifact(task_id="...", path="dist/app.zip", description="最终打包结果")`
        - `record_task_artifact(task_id="...", path="logs/service.log", description="值班期间记录的日志")`

        什么时候用它：
        - 有截图、日志、压缩包、导出文件、下载文件等结果需要保留
        - 任务完成时，把所有能交接的东西都登记清楚
        """,
    ),
    "summarize_background_task": _doc(
        "汇总某个后台任务的当前状态、最近结果、步骤和最近事件，适合交接给用户或新会话。",
        """
        输入：
        - `task_id`: 任务 ID
        - `include_recent_events`: 带上多少条最近事件

        调用示例：
        - `summarize_background_task(task_id="...", include_recent_events=20)`
        - `summarize_background_task(task_id="...", include_recent_events=50)`

        什么时候用它：
        - 任务快结束了，想把本次值班做一个简明总结
        - 你准备向用户汇报“做了什么、结果是什么、还有没有后续”
        """,
    ),
    "get_task_handoff": _doc(
        "生成更适合交接的后台任务摘要，除了状态和最近事件外，还会给出当前步骤、阻塞点和建议下一步。",
        """
        输入：
        - `task_id`: 任务 ID
        - `include_recent_events`: 带上多少条最近事件

        适用场景：
        - 模型断线重连后快速接手昨晚的值班任务
        - 把后台任务交接给新会话、新模型或用户
        - 需要明确当前卡在哪一步、下一步该做什么

        调用示例：
        - `get_task_handoff(task_id="...", include_recent_events=20)`
        """,
    ),
    "mark_task_waiting_for_user": _doc(
        "把后台任务标记为“等待用户决定”，用于明确任务当前卡点和需要用户回答的问题。",
        """
        输入：
        - `task_id`: 任务 ID
        - `question`: 需要用户回答的问题

        调用示例：
        - `mark_task_waiting_for_user(task_id="...", question="是否继续重试到明早 9 点？")`
        """,
    ),
    "mark_task_waiting_for_condition": _doc(
        "把后台任务显式标记为“等待某个条件”，适合人工备注当前在等什么。",
        """
        输入：
        - `task_id`: 任务 ID
        - `note`: 当前等待说明

        调用示例：
        - `mark_task_waiting_for_condition(task_id="...", note="等待端口 8000 开放后再继续")`
        """,
    ),
    "run_shell": _doc(
        "用当前平台的默认 shell 执行命令。",
        """
        输入：
        - `command`: shell 命令字符串
        - `cwd`: 可选工作目录
        - `timeout_ms`: 超时毫秒数
        - `encoding`: 输出解码方式
        - `max_output_chars`: 输出最大长度

        使用建议：
        - 这是最通用的执行工具，跨平台任务优先使用它
        - 如果工具明确提示缺少依赖，可用它安装当前任务所需最小依赖
        - 更适合验证命令、构建命令、测试命令、包管理命令、轻量系统检查
        - 命令输出可能很长时，主动设置 `max_output_chars`

        调用示例：
        - `run_shell(command="python --version")`
        - `run_shell(command="pip install pillow")`
        - `run_shell(command="pytest -q", cwd="D:\\\\mcptoolsDev\\\\allcanuse", timeout_ms=120000, max_output_chars=30000)`
        - `run_shell(command="npm test", cwd="/home/user/project", timeout_ms=180000)`
        - `run_shell(command="git status", cwd=".", max_output_chars=8000)`

        什么时候优先用它：
        - 你需要跨平台跑一个普通命令时
        - 你已经改完代码，准备跑测试、lint、build、版本检查时
        - 工具提示缺少依赖，且当前任务确实需要时

        推荐组合：
        - 改代码前先 `list_tree/find_files/search_text/read_file`
        - 改代码后再 `run_shell` 做验证
        - 如果命令要长期运行，改用 `start_process`
        """,
    ),
    "run_cmd": _doc(
        "执行一条命令。",
        """
        平台行为：
        - Windows 下通过 `cmd.exe /d /c`
        - Linux 下通过默认 shell

        输入：
        - `command`: 命令字符串
        - `cwd`: 可选工作目录
        - `timeout_ms`: 超时毫秒数
        - `encoding`: 输出解码方式
        - `max_output_chars`: 输出最大长度

        调用示例：
        - `run_cmd(command="dir", cwd="D:\\\\mcptoolsDev")`
        - `run_cmd(command="ls -la", cwd="/tmp")`
        - `run_cmd(command="where python", cwd="C:\\\\")`
        - `run_cmd(command="ls -la src", cwd="/home/user/project", max_output_chars=12000)`

        什么时候优先用它：
        - 你只想执行一条很短、很直接的命令
        - 你知道当前命令在 `cmd` 或默认 shell 里就足够，不需要 PowerShell 特性

        推荐组合：
        - 简单列目录、看版本、查路径、跑一个短命令时用它
        - 如果要做 PowerShell 管道、对象筛选、Windows 管理任务，改用 `run_powershell`
        """,
    ),
    "run_powershell": _doc(
        "执行一段 PowerShell 脚本或单行命令。",
        """
        平台行为：
        - Windows 下优先使用 `powershell.exe`
        - Linux 下优先使用 `pwsh`

        输入：
        - `script`: PowerShell 内容
        - `cwd`: 可选工作目录
        - `timeout_ms`: 超时毫秒数
        - `encoding`: 输出解码方式
        - `max_output_chars`: 输出最大长度

        调用示例：
        - `run_powershell(script="Get-Process | Select-Object -First 5")`
        - `run_powershell(script="Get-ChildItem -Force | Select-Object Name,Length,LastWriteTime", cwd="D:\\\\mcptoolsDev\\\\allcanuse")`
        - `run_powershell(script="Get-NetTCPConnection -State Listen | Select-Object -First 20", timeout_ms=60000)`
        - `run_powershell(script="$PSVersionTable.PSVersion.ToString()")`

        什么时候优先用它：
        - 你需要 PowerShell 对象管道、系统管理命令或 Windows 平台特有能力
        - 你想比 `run_cmd` 更方便地筛选进程、端口、服务、注册表或文件对象

        推荐组合：
        - Windows 上查进程、网卡、端口、服务时优先它
        - 改配置或代码前，可先用它确认系统状态
        - 改完后再用 `run_shell` 或 `run_powershell` 做验证
        """,
    ),
    "start_process": _doc(
        "启动一个新进程并返回 PID。",
        """
        输入：
        - `command`: 要启动的命令
        - `cwd`: 可选工作目录
        - `detach`: 是否后台启动，默认 `true`

        调用示例：
        - `start_process(command="notepad.exe")`
        - `start_process(command="python -m http.server 9000", cwd="D:\\\\site")`
        - `start_process(command="npm run dev", cwd="/home/user/project", detach=True)`
        - `start_process(command="python app.py", cwd="D:\\\\service", detach=False)`

        什么时候优先用它：
        - 任务需要启动一个持续运行的服务、开发服务器、安装器或 GUI 程序
        - 你不希望当前工具调用一直阻塞在命令执行上

        推荐组合：
        - 先 `start_process`
        - 再用 `wait_for_port`、`wait_for_process`、`wait_for_window` 或 `wait_for_http` 等待它就绪
        - 最后再用 `kill_process` 做收尾
        """,
    ),
    "start_managed_process": _doc(
        "启动一个长时间后台进程并登记为受监视、受保护的长时任务进程。",
        """
        输入：
        - `command`: 要启动的命令
        - `purpose`: 这个长时进程的用途说明，例如“跑 12 小时推理实验”
        - `cwd`: 可选工作目录
        - `owner`: 可选责任人或会话说明
        - `tags`: 可选标签列表
        - `protect_from_accidental_kill`: 是否保护它不被普通 `kill_process` 误杀，默认 `true`
        - `notes`: 可选补充说明
        - `stdout_path`: 可选 stdout 日志路径；不传时自动写到 `runtime/managed_processes/logs`
        - `stderr_path`: 可选 stderr 日志路径；不传时自动写到 `runtime/managed_processes/logs`

        什么时候优先用它：
        - 用户让你跑长时间训练、推理、实验、服务、爬虫或批处理任务
        - 用户明确说“这个进程不要停”“今晚一直跑”“你只负责盯着它”
        - 你担心后续模型可能把这个进程误当成临时子进程清掉
        - 任务可能超过当前 AI 会话或客户端连接寿命；这种情况下不要用长时间阻塞的 `run_shell`，要用托管进程写持久日志

        推荐组合：
        - 先 `start_managed_process`
        - 再用 `get_managed_process`、`list_managed_processes`、`wait_for_process`、`create_background_task` 监视它
        - 中途用 `note_managed_process` 记录进度、路径、日志位置
        - 只有用户明确要求停止时才 `stop_managed_process`

        调用示例：
        - `start_managed_process(command="python run_infer.py --config exp.yaml", purpose="跑今晚的长时推理实验")`
        - `start_managed_process(command="bash train.sh", cwd="/workspace/project", purpose="训练模型到明早", tags=["train","overnight"])`
        """,
    ),
    "list_managed_processes": _doc(
        "列出当前已登记的长时后台进程。",
        """
        输入：
        - `include_exited`: 是否包含已退出的长时进程，默认 `true`

        调用示例：
        - `list_managed_processes()`
        - `list_managed_processes(include_exited=False)`
        """,
    ),
    "get_managed_process": _doc(
        "查看某个长时后台进程的当前状态。",
        """
        输入：
        - `process_id`: 长时进程登记 ID
        - `tail_chars`: 返回 stdout/stderr 日志尾部的最大字符数，默认 `4000`

        调用示例：
        - `get_managed_process(process_id="mp-abc123")`
        - `get_managed_process(process_id="mp-abc123", tail_chars=12000)`
        """,
    ),
    "note_managed_process": _doc(
        "给某个长时后台进程补充备注，适合记录实验阶段、日志路径、检查结果。",
        """
        输入：
        - `process_id`: 长时进程登记 ID
        - `note`: 要记录的备注内容

        调用示例：
        - `note_managed_process(process_id="mp-abc123", note="日志输出在 logs/run-01.txt，已稳定运行 2 小时")`
        """,
    ),
    "stop_managed_process": _doc(
        "显式停止某个已登记的长时后台进程。",
        """
        输入：
        - `process_id`: 长时进程登记 ID
        - `reason`: 可选停止原因
        - `force`: 是否强制停止，默认 `true`

        使用约定：
        - 只有在用户明确要求停止、关闭、杀掉、结束实验时才使用它

        调用示例：
        - `stop_managed_process(process_id="mp-abc123", reason="用户要求停止当前实验")`
        """,
    ),
    "kill_process": _doc(
        "按 PID 或按进程名结束进程。",
        """
        输入：
        - `pid`: 进程 PID，和 `name` 二选一
        - `name`: 进程名，例如 `notepad.exe`
        - `force`: 是否强制结束，默认 `true`

        调用示例：
        - `kill_process(pid=1234)`
        - `kill_process(name="notepad.exe")`

        使用约定：
        - 如果目标 PID 已登记为受保护的长时进程，普通 `kill_process` 会被阻止
        - 对于长时间实验、长时间训练、长时间推理，优先改用 `start_managed_process` / `stop_managed_process`
        """,
    ),
    "list_processes": _doc(
        "枚举当前主机上的进程。",
        """
        输入：
        - `name_filter`: 可选名称过滤
        - `limit`: 返回数量上限，默认 `200`

        返回：
        - PID、进程名、状态、CPU、内存、可执行路径

        调用示例：
        - `list_processes()`
        - `list_processes(name_filter="python")`
        - `list_processes(name_filter="chrome", limit=50)`
        - `list_processes(name_filter="node")`

        什么时候优先用它：
        - 你想确认某个程序是否在运行
        - 你想先看进程概况，再决定是否 `kill_process` 或 `get_process_tree`

        推荐组合：
        - 先 `list_processes(name_filter=...)`
        - 再 `get_process_tree(pid=...)`
        - 最后必要时 `kill_process(pid=...)`
        """,
    ),
    "get_process_tree": _doc(
        "读取指定进程的子进程树。",
        """
        输入：
        - `pid`: 目标 PID；留空时默认当前 MCP Server 进程
        - `max_depth`: 最大递归层级，默认 `5`

        调用示例：
        - `get_process_tree()`
        - `get_process_tree(pid=1234, max_depth=3)`
        """,
    ),
    "find_port_process": _doc(
        "查找某个端口当前对应的连接或监听进程。",
        """
        输入：
        - `port`: 端口号

        调用示例：
        - `find_port_process(port=8000)`
        """,
    ),
    "list_tree": _doc(
        "递归列出目录树。",
        """
        输入：
        - `root`: 根目录
        - `max_depth`: 最大递归深度
        - `max_entries`: 最大条目数
        - `include_files`: 是否列出文件
        - `include_dirs`: 是否列出目录
        - `show_hidden`: 是否显示隐藏项

        调用示例：
        - `list_tree(root=".")`
        - `list_tree(root="src", max_depth=2, max_entries=300)`
        - `list_tree(root="/home/user/project", max_depth=3, show_hidden=True)`

        使用建议：
        - 初次进入陌生项目时先用它看目录结构，再决定后续 `find_files`、`search_text` 或 `read_file` 的目标范围
        - 大项目不要一上来就读整文件，先用目录树缩小范围
        - 如果项目很大，先限制 `max_depth`，避免一次列太深太宽

        什么时候优先用它：
        - 你还不知道项目入口在哪
        - 你需要先判断仓库是 Python、Node、Rust、Go 还是混合项目

        推荐组合：
        - 先 `list_tree`
        - 再 `find_files(pattern=...)`
        - 再 `search_text`
        - 最后 `read_file`
        """,
    ),
    "read_file": _doc(
        "读取文本文件，支持按行切片。",
        """
        输入：
        - `path`: 文件路径
        - `start_line`: 起始行，1 基
        - `end_line`: 结束行，包含该行
        - `encoding`: 文件编码

        调用示例：
        - `read_file(path="README.md")`
        - `read_file(path="app.py", start_line=20, end_line=60)`
        - `read_file(path="src/server.py", start_line=120, end_line=220)`
        - `read_file(path="/home/user/project/package.json")`

        使用建议：
        - 长文件优先先用 `search_text` 找关键词、函数名、类名、报错文本，再按行切片读取
        - 面对大文件时优先按 `50` 到 `200` 行分段读取，例如先读 `start_line=120, end_line=220`
        - 如果第一段上下文不够，再围绕命中位置扩大区间继续读，不要默认整文件通读
        - 读配置文件、小脚本、README 这类短文件时可以整文件读取；读长源码时不要默认整页读完

        常见读法示例：
        - 想看命中函数上下文：先 `search_text`，再 `read_file(start_line=命中行-20, end_line=命中行+80)`
        - 想排查报错来源：先搜报错字符串，再读附近代码
        - 想确认修改结果：改完后回读刚改的那一段
        """,
    ),
    "write_file": _doc(
        "写入文本文件，支持覆盖或追加。",
        """
        输入：
        - `path`: 文件路径
        - `content`: 要写入的内容
        - `encoding`: 文件编码
        - `mode`: `overwrite` 或 `append`
        - `create_dirs`: 父目录不存在时是否自动创建

        调用示例：
        - `write_file(path="notes.txt", content="hello")`
        - `write_file(path="scripts/run_check.sh", content="#!/usr/bin/env bash\\necho ok\\n", create_dirs=True)`
        - `write_file(path="logs/result.txt", content="done\\n", mode="append", create_dirs=True)`

        使用建议：
        - 更适合新建文件、生成完整小文件或确实需要整体重写的场景
        - 如果只是修改已有代码中的小片段，优先用 `patch_lines` 或 `replace_text`，避免整文件覆写
        - 覆写已有文件前，最好先 `read_file` 看当前内容，避免误把大文件整段重写掉

        什么时候优先用它：
        - 新建 README、脚本、配置样板、小型输出文件
        - 明确知道这个文件应该整体替换，而不是局部改动
        """,
    ),
    "patch_lines": _doc(
        "按行号精确替换文件中的一段内容。",
        """
        输入：
        - `path`: 文件路径
        - `start_line`: 起始行，1 基
        - `end_line`: 结束行，包含该行
        - `new_text`: 新文本
        - `encoding`: 文件编码

        调用示例：
        - `patch_lines(path="main.py", start_line=10, end_line=14, new_text="print('ok')\\n")`
        - `patch_lines(path="src/app.ts", start_line=42, end_line=47, new_text="return response.json(data);\\n")`
        - `patch_lines(path="README.md", start_line=5, end_line=8, new_text="新的说明段落\\n")`

        使用建议：
        - 适合已知行号范围的小范围精确修改
        - 修改前先用 `read_file(path=..., start_line=..., end_line=...)` 读取附近上下文，修改后再回读确认结果
        - 如果你还不知道要改哪几行，先 `search_text` 定位，再 `read_file` 看上下文，最后才 `patch_lines`

        推荐组合：
        - `search_text` -> `read_file` -> `patch_lines` -> `read_file` -> `run_shell`
        """,
    ),
    "replace_text": _doc(
        "在文件中按字面值替换文本片段。",
        """
        输入：
        - `path`: 文件路径
        - `old_text`: 旧文本
        - `new_text`: 新文本
        - `count`: 最大替换次数，`0` 表示全部
        - `encoding`: 文件编码

        调用示例：
        - `replace_text(path="config.py", old_text="DEBUG = False", new_text="DEBUG = True")`
        - `replace_text(path="package.json", old_text="\"dev\": \"vite\"", new_text="\"dev\": \"vite --host\"")`
        - `replace_text(path="settings.ini", old_text="port=8000", new_text="port=9000", count=1)`

        使用建议：
        - 适合替换稳定且可唯一定位的固定文本
        - 如果只想改第一处或前几处，显式传 `count`
        - 替换前可先用 `search_text` 确认命中位置和数量
        - 如果旧文本不稳定、出现很多次或需要按行号改，优先用 `patch_lines`

        推荐组合：
        - 先 `search_text`
        - 再 `replace_text`
        - 最后 `read_file` 回读确认
        """,
    ),
    "mkdir": _doc(
        "创建目录。",
        """
        输入：
        - `path`: 目录路径
        - `parents`: 是否连同父目录一起创建
        - `exist_ok`: 已存在时是否视为成功

        调用示例：
        - `mkdir(path="logs")`
        """,
    ),
    "move_path": _doc(
        "移动或重命名文件/目录。",
        """
        输入：
        - `source`: 源路径
        - `destination`: 目标路径
        - `overwrite`: 目标存在时是否覆盖

        调用示例：
        - `move_path(source="old.txt", destination="archive/old.txt")`
        """,
    ),
    "delete_path": _doc(
        "删除文件或目录。",
        """
        输入：
        - `path`: 要删除的路径
        - `recursive`: 删除目录时是否递归
        - `missing_ok`: 路径不存在时是否视为成功

        调用示例：
        - `delete_path(path="temp.txt")`
        - `delete_path(path="/tmp/build", recursive=True, missing_ok=True)`
        """,
    ),
    "zip_paths": _doc(
        "把一个或多个文件/目录打包成压缩文件。",
        """
        输入：
        - `paths`: 要打包的路径列表
        - `destination`: 输出归档路径
        - `archive_type`: `zip`、`tar` 或 `tar.gz`

        调用示例：
        - `zip_paths(paths=["src", "README.md"], destination="bundle.zip")`
        """,
    ),
    "extract_archive": _doc(
        "解压 zip 或 tar 类归档文件到指定目录。",
        """
        输入：
        - `archive_path`: 归档路径
        - `destination_dir`: 解压目录
        - `overwrite`: 目标目录非空时是否允许继续

        调用示例：
        - `extract_archive(archive_path="bundle.zip", destination_dir="out")`
        """,
    ),
    "list_desktop_files": _doc(
        "列出当前用户桌面目录中的文件和子目录。",
        """
        输入：
        - 无

        平台说明：
        - 自动尝试常见桌面路径，例如 `Desktop` 或中文桌面目录

        调用示例：
        - `list_desktop_files()`
        """,
    ),
    "find_files": _doc(
        "按文件名模式递归搜索文件或目录。",
        """
        输入：
        - `root`: 搜索根目录
        - `pattern`: 文件名模式，例如 `*.py`
        - `max_depth`: 最大搜索深度
        - `max_results`: 最大返回数量
        - `include_hidden`: 是否包含隐藏项

        调用示例：
        - `find_files(root=".", pattern="*.py")`
        - `find_files(root="src", pattern="*service*.*", max_results=100)`
        - `find_files(root="/home/user/project", pattern="*.md", max_depth=4)`

        使用建议：
        - 陌生项目先按 `*.py`、`*.ts`、`*test*`、`*config*` 之类模式缩小范围
        - 先定位候选文件，再配合 `search_text` 和 `read_file` 精读
        - 如果项目很大，优先限制 `max_depth` 和 `max_results`

        推荐组合：
        - 想找入口文件：`find_files(pattern="*main*")` 或 `find_files(pattern="*app*")`
        - 想找测试：`find_files(pattern="*test*")`
        - 找到后再 `search_text/read_file`
        """,
    ),
    "search_text": _doc(
        "在文本文件中搜索关键字或正则表达式。",
        """
        输入：
        - `root`: 搜索根目录或文件路径
        - `query`: 搜索字符串或正则
        - `use_regex`: 是否按正则处理
        - `case_sensitive`: 是否区分大小写
        - `file_pattern`: 只搜索匹配文件名模式的文件
        - `max_results`: 最大返回数量
        - `max_file_size_bytes`: 单文件最大扫描大小

        调用示例：
        - `search_text(root=".", query="TODO")`
        - `search_text(root="src", query="class\\s+\\w+", use_regex=True, file_pattern="*.py")`
        - `search_text(root="src", query="listen\\(", file_pattern="*.ts", max_results=50)`
        - `search_text(root=".", query="DATABASE_URL", file_pattern="*.env*", case_sensitive=False)`
        - `search_text(root="docs", query="安装", file_pattern="*.md")`

        使用建议：
        - 大代码库里优先用它定位函数名、类名、路由、配置项、报错文本，再用 `read_file` 局部读取
        - 用 `file_pattern` 限定到 `*.py`、`*.ts`、`*.md` 等目标类型，减少无关扫描
        - 文件很多或单文件较大时，按需调整 `max_results` 和 `max_file_size_bytes`
        - 先搜再读，通常比盲读整个目录快得多

        推荐组合：
        - 找函数定义：`search_text` -> `read_file`
        - 找配置值：`search_text` -> `replace_text`
        - 找报错来源：`search_text` -> `read_file` -> `patch_lines`
        """,
    ),
    "stat_path": _doc(
        "读取文件或目录的元信息。",
        """
        输入：
        - `path`: 目标路径

        返回：
        - 是否存在、是否文件/目录/符号链接、大小、时间戳

        调用示例：
        - `stat_path(path="README.md")`
        """,
    ),
    "copy_path": _doc(
        "复制文件或目录。",
        """
        输入：
        - `source`: 源路径
        - `destination`: 目标路径
        - `overwrite`: 目标已存在时是否覆盖

        调用示例：
        - `copy_path(source="a.txt", destination="backup/a.txt")`
        """,
    ),
    "hash_file": _doc(
        "计算文件哈希。",
        """
        输入：
        - `path`: 文件路径
        - `algorithm`: 哈希算法，例如 `sha256`、`md5`、`sha1`

        调用示例：
        - `hash_file(path="archive.zip")`
        """,
    ),
    "read_binary_file": _doc(
        "读取二进制文件片段，并返回 base64 或 hex 编码。",
        """
        输入：
        - `path`: 文件路径
        - `offset`: 起始偏移
        - `length`: 读取长度
        - `as_base64`: 为 `true` 时返回 base64，否则返回 hex

        调用示例：
        - `read_binary_file(path="image.png", length=256)`
        """,
    ),
    "write_binary_file": _doc(
        "写入二进制文件，输入内容可用 base64 或 hex 提供。",
        """
        输入：
        - `path`: 文件路径
        - `content`: base64 或 hex 字符串
        - `input_encoding`: `base64` 或 `hex`
        - `mode`: `overwrite` 或 `append`

        调用示例：
        - `write_binary_file(path="sample.bin", content="AAECAw==")`
        """,
    ),
    "list_recent_files": _doc(
        "列出最近修改的文件。",
        """
        输入：
        - `root`: 根目录或文件路径
        - `limit`: 返回条数上限

        调用示例：
        - `list_recent_files(root=".", limit=20)`
        """,
    ),
    "read_json_file": _doc(
        "读取 JSON 文件并返回解析后的结构化数据。",
        """
        输入：
        - `path`: JSON 文件路径

        调用示例：
        - `read_json_file(path="package.json")`
        """,
    ),
    "write_json_file": _doc(
        "把结构化数据写入 JSON 文件。",
        """
        输入：
        - `path`: 输出路径
        - `data`: 要写入的对象
        - `indent`: 缩进空格数
        - `ensure_ascii`: 是否强制 ASCII 转义

        调用示例：
        - `write_json_file(path="config.json", data={"ok": true})`
        """,
    ),
    "which_command": _doc(
        "检查某个命令在当前系统中是否存在，并返回路径。",
        """
        输入：
        - `name`: 命令名，例如 `python`、`git`、`wmctrl`

        调用示例：
        - `which_command(name="python")`
        """,
    ),
    "list_cameras": _doc(
        "枚举本机可访问的摄像头设备。",
        """
        输入：
        - `max_devices`: 最多探测多少个设备索引，默认 `8`

        平台说明：
        - 优先使用 `opencv-python`
        - Linux 下即使没有 OpenCV，也会尝试读取 `/dev/video*` 与 `/sys/class/video4linux`
        - Windows 下还会尝试通过 PowerShell / CIM 枚举摄像头
        - 返回结果里会包含当前检测到的 `available_backends`

        调用示例：
        - `list_cameras()`
        """,
    ),
    "capture_camera_photo": _doc(
        "调用指定摄像头拍摄一张照片并保存到本地。",
        """
        输入：
        - `camera_index`: 摄像头索引，默认 `0`
        - `output_path`: 可选输出路径；留空时写入临时目录
        - `return_image_content`: 若为 `true`，则在支持视觉内容的 MCP 客户端中直接返回图像内容
        - `include_image_preview_text`: 当直接返回图像内容时，是否同时附带一段文本说明

        使用建议：
        - 如果后续模型需要真正“看图”，优先把 `return_image_content` 设为 `true`
        - 如果当前客户端不支持图像内容，仍可使用返回的本地路径继续处理
        - 拍照时会把当前主机上可用的后端尽量都试一遍，而不是只试第一种；Windows 会尝试不同 OpenCV 后端以及 `ffmpeg dshow`；Linux 会尝试 OpenCV、`ffmpeg`、`libcamera-still`、`fswebcam`
        - 如果某个后端拍出来明显是黑帧，底层会把它视为失败并继续换后端
        - 返回结果里的 `attempts`、`fallback_attempts`、`attempted_backends` 会告诉你已经尝试过哪些方案

        调用示例：
        - `capture_camera_photo()`
        - `capture_camera_photo(return_image_content=True)`
        """,
    ),
    "list_windows": _doc(
        "枚举桌面窗口标题、句柄、进程信息和窗口矩形。",
        """
        输入：
        - `include_invisible`: 是否包含不可见窗口
        - `title_filter`: 标题包含过滤
        - `limit`: 返回数量上限

        返回：
        - 每个窗口的标题、句柄、PID、进程名、可见性、前台标记

        调用示例：
        - `list_windows()`
        - `list_windows(title_filter="Chrome")`
        """,
    ),
    "get_active_window": _doc(
        "读取当前前台活动窗口信息。",
        """
        输入：
        - 无

        返回：
        - 前台窗口标题、句柄、PID、进程名、窗口矩形

        调用示例：
        - `get_active_window()`
        """,
    ),
    "get_desktop_context": _doc(
        "汇总当前桌面上下文，一次返回前台窗口和后台窗口列表。",
        """
        输入：
        - `limit`: 最多返回多少个窗口，默认 `50`
        - `include_invisible`: 是否包含不可见窗口

        适用场景：
        - 模型想快速知道当前桌面前台是什么，以及后台有哪些窗口/进程标题

        调用示例：
        - `get_desktop_context()`
        """,
    ),
    "capture_screenshot": _doc(
        "截取当前桌面截图并保存到本地文件。",
        """
        输入：
        - `output_path`: 可选输出路径；留空时写入临时目录
        - `all_screens`: 是否截取所有显示器
        - `return_image_content`: 若为 `true`，则在支持视觉内容的 MCP 客户端中直接返回图像内容
        - `include_image_preview_text`: 当直接返回图像内容时，是否同时附带一段文本说明

        使用建议：
        - 如果你希望带视觉能力的模型直接理解截图内容，优先把 `return_image_content` 设为 `true`
        - 如果客户端只支持普通文本工具结果，也可以继续只拿文件路径

        调用示例：
        - `capture_screenshot()`
        - `capture_screenshot(return_image_content=True)`
        """,
    ),
    "download_file": _doc(
        "下载网络文件到本地，类似轻量版 `wget`。",
        """
        输入：
        - `url`: 下载地址
        - `destination`: 本地保存路径
        - `headers`: 可选请求头
        - `timeout_ms`: 下载超时毫秒数，模型可自行按需设定
        - `overwrite`: 目标已存在时是否覆盖

        说明：
        - 默认会带常规 `User-Agent`
        - 如果目标站点要求特殊请求头，可在 `headers` 中自行覆盖默认值

        调用示例：
        - `download_file(url="https://example.com/file.zip", destination="downloads/file.zip")`
        """,
    ),
    "http_request": _doc(
        "发起 HTTP/HTTPS 请求，适合检查本地服务、接口联通性或拉取文本内容。",
        """
        输入：
        - `url`: 请求地址
        - `method`: 请求方法
        - `headers`: 可选请求头
        - `body`: 可选字符串请求体
        - `timeout_ms`: 超时毫秒数
        - `max_body_chars`: 响应体最大返回长度
        - `save_to`: 可选文件路径，用于保存原始响应体

        说明：
        - 默认会带常规 `User-Agent`
        - 如果接口对 `User-Agent`、`Authorization`、`Cookie` 等有特殊要求，可在 `headers` 中覆盖或补充

        调用示例：
        - `http_request(url="http://127.0.0.1:8000/health")`
        """,
    ),
    "http_head": _doc(
        "对 URL 发起 HEAD 请求，只读取状态码和响应头，不下载正文。",
        """
        输入：
        - `url`: 目标地址
        - `headers`: 可选请求头
        - `timeout_ms`: 超时毫秒数

        说明：
        - 默认会带常规 `User-Agent`

        适用场景：
        - 想先看 `Content-Type`、`Content-Length`、`ETag`、`Last-Modified`
        - 想快速判断某个下载链接或接口是否存在，但不想先拉正文

        调用示例：
        - `http_head(url="https://example.com/file.zip", timeout_ms=60000)`
        - `http_head(url="https://example.com/api/health")`
        """,
    ),
    "fetch_response_headers": _doc(
        "读取 HTTP/HTTPS 响应头，适合那些不支持 HEAD 但又想先看头部信息的接口。",
        """
        输入：
        - `url`: 目标地址
        - `method`: 请求方法，默认 `GET`
        - `headers`: 可选请求头
        - `body`: 可选字符串请求体；某些接口需要带请求体才能返回目标响应头
        - `timeout_ms`: 超时毫秒数

        说明：
        - 默认会带常规 `User-Agent`

        适用场景：
        - 服务不支持 `HEAD`，但想先检查响应头
        - 想看接口返回的缓存头、跳转头、CORS 头或内容类型

        调用示例：
        - `fetch_response_headers(url="https://example.com/api/info")`
        - `fetch_response_headers(url="https://example.com/graphql", method="POST", body='{\"query\":\"{__typename}\"}', headers={"Content-Type":"application/json"})`
        """,
    ),
    "submit_web_form": _doc(
        "提交网页表单，支持 GET 查询串和 POST 普通表单，适合搜索页、登录页或普通 HTML form 调试。",
        """
        输入：
        - `url`: 表单提交地址
        - `form_fields`: 表单字段字典
        - `method`: `GET` 或 `POST`
        - `encoding`: `application/x-www-form-urlencoded` 或 `multipart/form-data`
        - `headers`: 可选请求头
        - `timeout_ms`: 超时毫秒数
        - `max_body_chars`: 最多返回多少正文字符
        - `save_to`: 可选，把响应正文保存到本地文件

        说明：
        - 默认会带常规 `User-Agent`

        适用场景：
        - 模拟网页搜索框或普通表单提交
        - 需要先试一次表单再决定是否继续抓页面元素

        调用示例：
        - `submit_web_form(url="https://example.com/search", method="GET", form_fields={"q":"mcp tools"}, timeout_ms=60000)`
        - `submit_web_form(url="https://example.com/login", method="POST", form_fields={"username":"demo","password":"demo"})`
        """,
    ),
    "upload_file": _doc(
        "把本地文件上传到网络接口，默认用 `multipart/form-data`，也支持把文件原始字节直接作为请求体上传。",
        """
        输入：
        - `url`: 上传目标地址
        - `file_path`: 本地文件路径
        - `method`: HTTP 方法，默认 `POST`
        - `upload_mode`: `multipart` 或 `raw`
        - `field_name`: `multipart` 模式下的文件字段名，默认 `file`
        - `remote_filename`: 可选，上传时对方看到的文件名
        - `content_type`: 可选，手动指定文件类型；留空时自动猜测
        - `form_fields`: 可选，`multipart` 模式下附带的普通表单字段
        - `headers`: 可选，请求头
        - `timeout_ms`: 超时毫秒数
        - `max_body_chars`: 最多返回多少响应正文字符
        - `save_to`: 可选，把服务器响应正文保存到本地文件

        说明：
        - 默认会带常规 `User-Agent`

        适用场景：
        - 向普通网页上传接口、管理后台、测试接口上传文件
        - 先用 `zip_paths` 打包多个文件，再上传压缩包
        - 某些对象存储或文件接口要求 `PUT` 原始文件流时，改用 `upload_mode="raw"`

        调用示例：
        - `upload_file(url="https://example.com/upload", file_path="dist/app.zip", form_fields={"project":"allcanuse"})`
        - `upload_file(url="https://example.com/object/my.bin", file_path="build/my.bin", method="PUT", upload_mode="raw", content_type="application/octet-stream", timeout_ms=180000)`
        """,
    ),
    "trace_http_redirects": _doc(
        "追踪一个 URL 的 HTTP 重定向链，适合排查 301/302/307/308 跳转问题。",
        """
        输入：
        - `url`: 起始地址
        - `headers`: 可选请求头
        - `timeout_ms`: 单跳超时毫秒数
        - `max_hops`: 最多追踪多少跳

        说明：
        - 默认会带常规 `User-Agent`

        适用场景：
        - 排查登录跳转、CDN 跳转、域名跳转、HTTP 到 HTTPS 跳转
        - 想知道最终落地页到底是哪一个地址
        - 目录页打不开、下载链接失效、短链接跳转异常时先确认真实落地地址

        调用示例：
        - `trace_http_redirects(url="http://example.com")`
        - `trace_http_redirects(url="https://example.com/download", max_hops=15, timeout_ms=30000)`
        - `trace_http_redirects(url="https://short.example/abc", headers={"Referer":"https://example.com"})`

        推荐组合：
        - 先 `trace_http_redirects`，再对最终地址调 `fetch_webpage_text` 或 `download_file`
        - 如果最终落地页像目录页，再继续 `extract_links_from_webpage` 或 `crawl_webpages`
        """,
    ),
    "websocket_connect": _doc(
        "连接 `ws://` 或 `wss://` WebSocket 接口，完成握手，可发送一组文本消息并读取返回消息。",
        """
        输入：
        - `url`: WebSocket 地址，例如 `ws://127.0.0.1:8765/chat`
        - `messages`: 可选，要按顺序发送的一组文本消息
        - `headers`: 可选，附加请求头
        - `subprotocols`: 可选，子协议列表
        - `origin`: 可选，手动指定 `Origin`
        - `timeout_ms`: 超时毫秒数
        - `receive_limit`: 最多读取多少条返回消息
        - `receive_max_bytes`: 单条消息最多保留多少字节

        适用场景：
        - 调试本地 WebSocket 服务是否能握手和收发消息
        - 调试实时推送、聊天、订阅或 echo 类型接口

        调用示例：
        - `websocket_connect(url="ws://127.0.0.1:8765/echo", messages=["hello"], timeout_ms=5000)`
        - `websocket_connect(url="wss://example.com/socket", subprotocols=["json"], messages=['{\"type\":\"ping\"}'], receive_limit=3, timeout_ms=15000)`
        """,
    ),
    "trace_route": _doc(
        "执行 traceroute / tracert，查看到目标主机的路由跳点。",
        """
        输入：
        - `host`: 目标域名或 IP
        - `max_hops`: 最大跳数
        - `timeout_ms`: 每跳超时毫秒数

        适用场景：
        - 排查到目标主机的链路路径
        - 想看延迟或卡在哪一跳

        平台行为：
        - Windows 下调用 `tracert`
        - Linux 下调用 `traceroute`

        调用示例：
        - `trace_route(host="example.com")`
        - `trace_route(host="10.0.0.1", max_hops=15, timeout_ms=3000)`
        """,
    ),
    "fetch_webpage_text": _doc(
        "抓取网页并提取主要可读文字内容，适合让模型快速读网页正文。",
        """
        输入：
        - `url`: 网页地址
        - `headers`: 可选请求头，例如覆盖默认 `User-Agent`
        - `timeout_ms`: 请求超时毫秒数
        - `max_text_chars`: 最多返回多少个正文字符
        - `include_title`: 是否返回网页标题

        说明：
        - 默认会带更接近普通浏览器的请求头
        - 会自动处理常见压缩响应，尽量提高普通网页兼容性

        适用场景：
        - 读取新闻、文档、博客、说明页的文字内容
        - 先快速看网页正文，再决定是否继续提取链接或特定元素
        - 网页可能较慢、较长、需要先做一次轻量正文探测

        调用示例：
        - `fetch_webpage_text(url="https://example.com")`
        - `fetch_webpage_text(url="https://example.com/docs", max_text_chars=40000, timeout_ms=60000)`
        - `fetch_webpage_text(url="https://example.com/help/install", headers={"Referer":"https://example.com/help"}, timeout_ms=90000, max_text_chars=60000)`
        - `fetch_webpage_text(url="https://example.com/article?id=123", include_title=False, max_text_chars=12000)`

        什么时候优先用它：
        - 你还不知道当前页是正文页还是目录页时，先用它快速看文字密度和页面主题
        - 你只想先知道“这页大概讲什么”，不急着抓结构化元素时

        遇到这些情况时怎么做：
        - 如果正文像目录页、索引页、导航页：继续用 `extract_links_from_webpage` 或 `crawl_webpages`
        - 如果你更在意层级和链接结构：改用 `webpage_to_markdown`
        - 如果你更在意标题、摘要、canonical、结构化数据：改用 `extract_webpage_metadata`
        """,
    ),
    "webpage_to_markdown": _doc(
        "抓取网页并转换成更适合模型阅读的 Markdown 文本。",
        """
        输入：
        - `url`: 网页地址
        - `headers`: 可选请求头
        - `timeout_ms`: 请求超时毫秒数
        - `max_markdown_chars`: 最多返回多少个 Markdown 字符

        说明：
        - 默认会带更接近普通浏览器的请求头
        - 适合比纯文本更需要层级结构的页面

        适用场景：
        - 想把网页正文转换成更干净、层次更明显的 Markdown
        - 读文档页、说明页、博客页时比纯文本更方便
        - 页面里有标题、列表、代码块式结构，想让模型更容易继续总结

        调用示例：
        - `webpage_to_markdown(url="https://example.com/docs")`
        - `webpage_to_markdown(url="https://example.com/docs", max_markdown_chars=50000, timeout_ms=60000)`
        - `webpage_to_markdown(url="https://example.com/guide/install", headers={"Referer":"https://example.com/guide"})`
        - `webpage_to_markdown(url="https://example.com/changelog", max_markdown_chars=120000, timeout_ms=120000)`

        推荐组合：
        - 先 `trace_http_redirects` 确认最终地址，再 `webpage_to_markdown`
        - 读完后如果页面只是入口页，再 `extract_links_from_webpage` 或 `crawl_webpages`
        - 如果只想精确抓某个区块，改用 `extract_webpage_elements`
        """,
    ),
    "extract_links_from_webpage": _doc(
        "提取网页中的超链接，返回链接文本、原始 href 和绝对链接。",
        """
        输入：
        - `url`: 网页地址
        - `headers`: 可选请求头
        - `timeout_ms`: 请求超时毫秒数
        - `text_filter`: 可选，只保留链接文字包含该内容的项
        - `href_filter`: 可选，只保留 href 或绝对链接包含该内容的项
        - `max_links`: 最多返回多少条链接
        - `link_text_max_chars`: 单条链接文字最大长度

        说明：
        - 默认会带更接近普通浏览器的请求头
        - 返回的 `absolute_url` 更适合直接继续递进抓取

        适用场景：
        - 想快速列出网页所有导航、文档入口、下载入口
        - 想按链接文字或链接地址筛选特定链接
        - 当前页像目录页、索引页、文档首页，想进一步找真正内容页

        调用示例：
        - `extract_links_from_webpage(url="https://example.com")`
        - `extract_links_from_webpage(url="https://example.com/docs", text_filter="API")`
        - `extract_links_from_webpage(url="https://example.com", href_filter=".pdf", max_links=50)`
        - `extract_links_from_webpage(url="https://example.com/help", text_filter="安装", max_links=100, timeout_ms=90000)`
        - `extract_links_from_webpage(url="https://example.com/docs/index", href_filter="/reference/", link_text_max_chars=500)`

        推荐组合：
        - 先 `fetch_webpage_text` 判断页面是否只是入口页，再 `extract_links_from_webpage`
        - 拿到候选链接后，继续 `fetch_webpage_text`、`webpage_to_markdown` 或 `crawl_webpages`
        - 只想找附件时，优先配合 `href_filter=".pdf"`、`.zip`、`.csv`、`.json`
        """,
    ),
    "extract_webpage_metadata": _doc(
        "提取网页标题、canonical、meta、Open Graph、Twitter 卡片和可选 JSON-LD 元数据。",
        """
        输入：
        - `url`: 网页地址
        - `headers`: 可选请求头
        - `timeout_ms`: 请求超时毫秒数
        - `include_json_ld`: 是否返回页面中的 JSON-LD 脚本块

        说明：
        - 默认会带更接近普通浏览器的请求头

        适用场景：
        - 想快速知道页面主题、摘要、canonical 地址和结构化元数据
        - 想判断一个页面到底是文章页、产品页、文档页还是索引页
        - 想先看页面摘要、站点定义和对象类型，再决定要不要继续深抓

        调用示例：
        - `extract_webpage_metadata(url="https://example.com/docs/start")`
        - `extract_webpage_metadata(url="https://example.com/article", include_json_ld=True, timeout_ms=60000)`
        - `extract_webpage_metadata(url="https://example.com/product/abc", headers={"Referer":"https://example.com/catalog"})`
        - `extract_webpage_metadata(url="https://example.com/blog/post-1", include_json_ld=False)`

        读取结果时重点看什么：
        - `title`: 当前页标题
        - `canonical_url`: 页面规范地址，适合去重和确认主地址
        - `meta_name`: 常见 `description`、`keywords`、`robots`
        - `meta_property`: 常见 `og:title`、`og:description`、`og:type`
        - `json_ld`: 文章、产品、FAQ、组织信息等结构化对象

        推荐组合：
        - 先 `extract_webpage_metadata` 判断页面类型，再决定是 `fetch_webpage_text` 还是 `crawl_webpages`
        - 如果看到 `canonical_url` 指向别的正文页，可继续抓 canonical 对应页面
        """,
    ),
    "crawl_webpages": _doc(
        "从起始网页开始做轻量递进抓取，按深度继续读取站内相关页面，适合文档站、帮助中心、博客和目录页探索。",
        """
        输入：
        - `start_url`: 起始网页地址
        - `headers`: 可选请求头
        - `timeout_ms`: 单页请求超时毫秒数
        - `max_pages`: 最多抓多少页
        - `max_depth`: 最深探索多少层链接
        - `same_domain_only`: 是否只保留同域链接
        - `include_patterns`: 可选，只抓 URL 中包含这些片段的页面
        - `exclude_patterns`: 可选，跳过 URL 中包含这些片段的页面
        - `max_text_chars_per_page`: 每页最多保留多少正文字符
        - `max_links_per_page`: 每页最多分析多少个链接

        说明：
        - 默认会优先沿更像文档页、帮助页、API 页、FAQ 页、教程页的链接继续探索
        - 这是轻量 HTML 递进抓取，不包含验证码、登录保护或浏览器自动化绕过
        - 默认更适合从目录页、文档首页、帮助中心入口页往下抓

        适用场景：
        - 文档首页下面有很多章节页，模型不想手工一页页点进去
        - 目录页、导航页、索引页只给出入口，需要继续抓多个相关子页
        - 想先小范围试抓 5 到 20 页，再决定是否要更深入探索

        调用示例：
        - `crawl_webpages(start_url="https://example.com/docs", max_pages=12, max_depth=2)`
        - `crawl_webpages(start_url="https://example.com/help", include_patterns=["/help/","/faq/"], exclude_patterns=["login","signup"], max_pages=20, timeout_ms=60000)`
        - `crawl_webpages(start_url="https://example.com/guide/index.html", same_domain_only=True, max_pages=8, max_depth=1, max_text_chars_per_page=12000)`
        - `crawl_webpages(start_url="https://example.com/docs", include_patterns=["/docs/","/reference/"], exclude_patterns=["login","register","privacy"], max_links_per_page=80)`

        参数怎么理解：
        - `max_pages`: 控制总抓取页数，避免一口气抓太多
        - `max_depth`: 控制从起始页往下点几层
        - `include_patterns`: 只保留更像目标内容的 URL 片段
        - `exclude_patterns`: 提前跳过登录、注册、隐私政策、条款、无关页面
        - `max_text_chars_per_page`: 每页正文保留上限，防止单页过长挤占上下文

        推荐组合：
        - 起始页先 `trace_http_redirects`，确认最终入口后再 `crawl_webpages`
        - 需要先判断入口页类型时，先 `extract_webpage_metadata`
        - 抓完以后，如果某一页特别重要，再对那一页单独 `webpage_to_markdown` 或 `extract_webpage_elements`
        """,
    ),
    "extract_tables_from_webpage": _doc(
        "提取网页中的 HTML 表格，并返回结构化表头和行数据。",
        """
        输入：
        - `url`: 网页地址
        - `headers`: 可选请求头
        - `timeout_ms`: 请求超时毫秒数
        - `max_tables`: 最多返回多少个表格
        - `max_rows_per_table`: 每个表格最多返回多少行

        说明：
        - 默认会带常规 `User-Agent`

        适用场景：
        - 网页里有参数表、价格表、说明表、统计表
        - 想让模型直接读取结构化表格而不是自己从正文里拆
        - 文档页正文太长，但核心信息其实藏在参数表里

        调用示例：
        - `extract_tables_from_webpage(url="https://example.com/table-page")`
        - `extract_tables_from_webpage(url="https://example.com/table-page", max_tables=10, max_rows_per_table=500)`
        - `extract_tables_from_webpage(url="https://example.com/pricing", max_tables=5, max_rows_per_table=100, timeout_ms=90000)`

        推荐组合：
        - 先 `fetch_webpage_text` 看页面是否真的有表格，再决定是否调用
        - 如果页面里表格很多，先缩小到具体文档页，再提表格
        """,
    ),
    "extract_webpage_elements": _doc(
        "按标签名和属性条件提取网页元素，适合精确抓取特定 DOM 片段。",
        """
        输入：
        - `url`: 网页地址
        - `tag`: 要提取的 HTML 标签，例如 `a`、`h1`、`title`、`meta`、`article`
        - `attr_filters`: 可选属性过滤，例如 `{\"id\": \"main\"}`、`{\"class\": \"post-title\"}`
        - `headers`: 可选请求头
        - `timeout_ms`: 请求超时毫秒数
        - `max_elements`: 最多返回多少个元素
        - `text_max_chars`: 每个元素最多返回多少个文本字符

        说明：
        - 默认会带常规 `User-Agent`

        返回：
        - 标签名、属性字典、元素文本、以及可能的 `href` / `src` 绝对地址

        适用场景：
        - 想抓某个 `article`、`main`、`h1`、`meta`、`a`
        - 想提取带特定 `id`、`class`、`name`、`property` 的元素
        - 当前页正文很多，但你只想要一个很明确的区块

        调用示例：
        - `extract_webpage_elements(url="https://example.com", tag="h1")`
        - `extract_webpage_elements(url="https://example.com", tag="meta", attr_filters={"name": "description"})`
        - `extract_webpage_elements(url="https://example.com/docs", tag="a", attr_filters={"class": "nav-link"})`
        - `extract_webpage_elements(url="https://example.com/article/1", tag="article", max_elements=3, text_max_chars=4000)`
        - `extract_webpage_elements(url="https://example.com/docs", tag="main", attr_filters={"id": "content"})`

        推荐组合：
        - 先 `extract_webpage_metadata` 看页面类型，再决定抓 `article`、`main`、`meta` 还是 `a`
        - 先 `fetch_webpage_text` 大致了解页面，再用这个工具做精确切片
        """,
    ),
    "resolve_dns_records": _doc(
        "直接查询 DNS 多种记录类型，支持 A、AAAA、CNAME、MX、TXT、NS、SRV。",
        """
        输入：
        - `hostname`: 要查询的域名
        - `record_types`: 可选记录类型列表；留空时默认查 `A`、`AAAA`、`CNAME`、`MX`、`TXT`、`NS`、`SRV`
        - `dns_server`: 可选指定 DNS 服务器 IP；留空时优先尝试系统 DNS
        - `timeout_ms`: 单次查询超时毫秒数

        适用场景：
        - 想查邮件记录、TXT 记录、别名记录，而不仅仅是 IP
        - 想指定某个 DNS 服务器直接查询

        调用示例：
        - `resolve_dns_records(hostname="example.com")`
        - `resolve_dns_records(hostname="example.com", record_types=["MX", "TXT"], timeout_ms=8000)`
        - `resolve_dns_records(hostname="example.com", dns_server="8.8.8.8")`
        """,
    ),
    "reverse_dns_lookup": _doc(
        "对 IP 地址做反向 DNS 查询。",
        """
        输入：
        - `ip_address`: 要反查的 IPv4 或 IPv6 地址

        适用场景：
        - 已知 IP，想看是否存在 PTR 或主机名

        调用示例：
        - `reverse_dns_lookup(ip_address="8.8.8.8")`
        - `reverse_dns_lookup(ip_address="127.0.0.1")`
        """,
    ),
    "dns_lookup": _doc(
        "解析域名对应的 IP 地址。",
        """
        输入：
        - `hostname`: 要解析的域名

        调用示例：
        - `dns_lookup(hostname="localhost")`
        """,
    ),
    "get_tls_certificate": _doc(
        "读取 TLS/HTTPS 证书信息，返回主题、签发者、指纹、有效期和协商协议。",
        """
        输入：
        - `host`: 目标主机
        - `port`: 端口，默认 `443`
        - `server_hostname`: 可选 SNI；留空时默认和 `host` 一样
        - `timeout_ms`: 超时毫秒数
        - `verify`: 是否按系统 CA 校验证书，默认 `false`

        适用场景：
        - 检查 HTTPS 证书是否过期
        - 查看签发者、SAN、SHA256 指纹、协商的 TLS 版本

        调用示例：
        - `get_tls_certificate(host="example.com")`
        - `get_tls_certificate(host="10.0.0.5", server_hostname="api.example.com", verify=false)`
        """,
    ),
    "ping_host": _doc(
        "对目标主机执行 ping 测试。",
        """
        输入：
        - `hostname`: 域名或 IP
        - `count`: 发包次数
        - `timeout_ms`: 超时毫秒数

        调用示例：
        - `ping_host(hostname="127.0.0.1")`
        """,
    ),
    "tcp_connect": _doc(
        "测试 TCP 端口是否可连通。",
        """
        输入：
        - `host`: 目标主机
        - `port`: 目标端口
        - `timeout_ms`: 超时毫秒数

        调用示例：
        - `tcp_connect(host="127.0.0.1", port=80)`
        """,
    ),
    "raw_tcp_exchange": _doc(
        "连接 TCP 服务后发送原始数据，再读取响应，适合做轻量版 netcat / 文本协议调试。",
        """
        输入：
        - `host`: 目标主机
        - `port`: 目标端口
        - `data`: 要发送的数据
        - `timeout_ms`: 超时毫秒数
        - `recv_max_bytes`: 最多接收多少字节
        - `input_encoding`: `utf-8`、`hex` 或 `base64`
        - `output_encoding`: `utf-8`、`hex` 或 `base64`

        适用场景：
        - 调试自定义 TCP 文本协议
        - 发送一段原始请求并查看响应

        调用示例：
        - `raw_tcp_exchange(host="127.0.0.1", port=6379, data="PING\\r\\n")`
        - `raw_tcp_exchange(host="127.0.0.1", port=9000, data="010203", input_encoding="hex", output_encoding="hex")`
        """,
    ),
    "udp_send_receive": _doc(
        "向 UDP 服务发送一段数据并等待响应。",
        """
        输入：
        - `host`: 目标主机
        - `port`: 目标端口
        - `data`: 要发送的数据
        - `timeout_ms`: 超时毫秒数
        - `recv_max_bytes`: 最多接收多少字节
        - `input_encoding`: `utf-8`、`hex` 或 `base64`
        - `output_encoding`: `utf-8`、`hex` 或 `base64`

        适用场景：
        - 调试需要响应的 UDP 服务
        - 验证某个 UDP 服务是否真的返回数据

        调用示例：
        - `udp_send_receive(host="127.0.0.1", port=5353, data="hello", timeout_ms=3000)`
        """,
    ),
    "scan_ports": _doc(
        "扫描目标主机的一组 TCP 端口或一个端口范围。",
        """
        输入：
        - `host`: 目标主机
        - `ports`: 可选，显式端口列表
        - `start_port`: 可选，起始端口
        - `end_port`: 可选，结束端口
        - `timeout_ms`: 单端口超时毫秒数
        - `open_only`: 是否只返回开放端口，默认 `true`
        - `max_results`: 最多返回多少条结果

        适用场景：
        - 快速看某台主机某几个端口是否开放
        - 对一个小范围端口做实验性扫描

        使用规则：
        - 要么传 `ports`
        - 要么同时传 `start_port` 和 `end_port`

        调用示例：
        - `scan_ports(host="127.0.0.1", ports=[22, 80, 443, 8000])`
        - `scan_ports(host="127.0.0.1", start_port=8000, end_port=8100, timeout_ms=200, open_only=true)`
        """,
    ),
    "list_established_connections": _doc(
        "列出当前主机已经建立的网络连接。",
        """
        输入：
        - `limit`: 最多返回多少条连接，默认 `200`

        返回：
        - 本地地址、远端地址、PID、进程名、连接状态

        适用场景：
        - 想看当前机器正在和哪些远端主机通信
        - 想从连接维度排查网络问题，而不仅仅看监听端口

        调用示例：
        - `list_established_connections()`
        - `list_established_connections(limit=500)`
        """,
    ),
    "list_listening_ports": _doc(
        "列出当前主机上处于监听状态的端口。",
        """
        输入：
        - 无

        返回：
        - 本地 IP、端口、PID、协议族

        调用示例：
        - `list_listening_ports()`
        """,
    ),
}


def render_overview_markdown() -> str:
    lines = [
        "# allcanuse-mcp 使用指南",
        "",
        "这个 MCP Server 面向 Windows / Linux 实验环境，帮助模型完成系统检查、文件操作、命令执行、窗口观察和网络访问。",
        "",
        "推荐工作顺序：",
        "1. 先用 `get_system_info`、`get_env`、`list_tree`、`get_desktop_context` 了解环境。",
        "2. 再用 `read_file`、`list_processes`、`get_network_config` 收集更具体上下文。",
        "3. 最后再调用 `write_file`、`patch_lines`、`run_shell`、`run_powershell`、`start_process` 等执行类工具。",
        "4. 如果工具提示缺少依赖，并且当前任务确实需要它，可以使用 shell 工具安装最小必需依赖后重试。",
        "5. 如果任务需要长时间等待、用户暂时离开或会话之后可能重连，优先把等待动作托管到 `create_background_task`，而不是只停在当前回复里。",
        "",
        "查看全部工具：",
        "- `list_all_tools()`",
        "- `list_all_tools(include_descriptions=True)`",
        "",
        "先读 guide 索引：",
        "- `resource://guides/index`",
        "",
        "读取单个工具详细说明：",
        "- `resource://guides/tools/get_system_info`",
        "- `resource://guides/tools/read_file`",
        "- `resource://guides/tools/run_powershell`",
        "",
        "读取组合工作流：",
        "- `resource://guides/workflows/web-research`",
        "- `resource://guides/workflows/code-edit`",
        "- `resource://guides/workflows/desktop-observation`",
        "- `resource://guides/workflows/network-diagnostics`",
        "",
        "已注册工具：",
        "",
    ]
    for tool_name in sorted(TOOL_DESCRIPTIONS):
        first_line = TOOL_DESCRIPTIONS[tool_name].splitlines()[0]
        lines.append(f"- `{tool_name}`: {first_line}")
    return "\n".join(lines)


def render_model_playbook_markdown() -> str:
    return "\n".join(
        [
            "# 模型操作手册",
            "",
            "建议优先按下面顺序工作：",
            "1. 先了解环境：`get_system_info`、`get_time`、`get_env`、`get_network_config`、`get_desktop_context`。",
            "2. 再看项目和文件：`list_tree`、`find_files`、`search_text`、`read_file`。",
            "3. 读代码时先定位再精读：先 `list_tree/find_files/search_text` 缩小范围，再 `read_file(start_line=..., end_line=...)` 局部读取。",
            "4. 大文件或长代码文件不要默认整文件通读；优先按 `50` 到 `200` 行分段读取，不够再扩大上下文。",
            "5. 需要修改文件时，优先用 `replace_text`、`patch_lines`；只有在必要时才用 `write_file` 整体覆盖。",
            "6. 修改前先读取目标片段，修改后再回读同一段或相邻片段确认结果，然后再跑命令验证。",
            "7. 需要系统动作时，跨平台任务优先用 `run_shell`；PowerShell 特定任务用 `run_powershell`。",
            "8. 需要只看响应头时优先用 `http_head` 或 `fetch_response_headers`，下载资源时优先用 `download_file`，上传本地文件时优先用 `upload_file`，并显式设置 `timeout_ms`。",
            "9. 需要读网页时优先用 `trace_http_redirects`、`fetch_webpage_text`、`webpage_to_markdown`，需要找链接时用 `extract_links_from_webpage`，需要抓表格时用 `extract_tables_from_webpage`，需要精确抓标签时用 `extract_webpage_elements`，需要提交表单时用 `submit_web_form`，需要传本地文件时用 `upload_file`。",
            "10. 读网页不要默认停在当前页；如果当前页像目录页、导航页、列表页、文档首页、索引页、搜索结果页或聚合页，就继续沿最相关的站内链接深入读取，直到拿到真正有信息量的内容页。",
            "11. 读网页时优先沿正文里的文档链接、章节链接、详情页、上一篇/下一篇、API 页、FAQ 页、下载页继续探索，而不是只看目录项标题就结束。",
            "12. 需要做更细的网络诊断时，优先按 `resolve_dns_records/dns_lookup` -> `ping_host/trace_route` -> `tcp_connect/raw_tcp_exchange/udp_send_receive/websocket_connect/scan_ports` -> `http_head/fetch_response_headers/http_request/get_tls_certificate` 的顺序推进。",
            "13. 需要值班、观察长期变化或在用户离线时继续推进时，优先用 `wait_for_*` 和 `create_background_task`，包括 `wait_for_window`、`wait_for_desktop_change` 这类桌面值班工具，不要只在当前回复里空等。",
            "14. 需要桌面上下文时优先用 `get_desktop_context`，而不是手工拼接多个窗口工具。",
            "",
            "值班模式的具体判断：",
            "1. 只差几秒或几十秒，并且你准备在当前回复里继续做后续步骤时，优先用 `wait` 或 `wait_until`。",
            "2. 需要等明确条件时，优先用对应的 `wait_for_*`，不要用模糊口头等待代替。",
            "3. 用户会离线、去睡觉、稍后再回来，或任务可能跨会话持续较久时，优先用 `create_background_task`。",
            "4. 后台任务一旦与后续步骤有关，尽早补 `create_task_plan`、`append_task_event`、`record_task_artifact`。",
            "5. 重新接手旧任务时，优先读 `get_task_handoff`；如果要看细节，再读 `get_background_task`。",
            "6. 等用户拍板而不是等外部条件时，优先用 `mark_task_waiting_for_user` 明确卡点。",
            "",
            "常见值班场景模板：",
            "- 盯服务恢复：`create_background_task(task_type='wait_http')` -> `create_task_plan` -> `get_task_handoff`。",
            "- 盯安装器或弹窗：`create_background_task(task_type='wait_window')` 或 `create_background_task(task_type='wait_desktop_change')` -> 必要时 `capture_screenshot`。",
            "- 盯构建产物：`create_background_task(task_type='wait_file')` -> `record_task_artifact`。",
            "- 用户说“我马上回来”：短等待优先 `wait`，不必默认切后台任务。",
            "",
            "依赖处理建议：",
            "- 如果工具明确告诉你缺少 Python 包或系统命令，并且当前任务确实依赖它，你可以安装最小必需依赖后重试。",
            "- 如果 MCP 已经提供了同类本地工具，优先直接调用工具，不要额外安装新库。",
            "",
            "代码编辑建议：",
            "- 未知代码库先 `list_tree`，再 `find_files`，再 `search_text`，最后 `read_file`。",
            "- 读大文件时优先围绕搜索命中点局部读，不要把长文件整页塞进上下文。",
            "- 固定文本替换优先 `replace_text`，已知行号范围优先 `patch_lines`，结构化 JSON 优先 `read_json_file/write_json_file`。",
            "- 只有创建新文件、生成完整小文件、或确实要整体重写时才优先 `write_file`。",
            "",
            "输出处理建议：",
            "- 命令输出太长时设置 `max_output_chars`。",
            "- 网络和长时工具优先显式传 `timeout_ms`。",
            "- 图片和照片工具返回的是文件路径，可继续交给支持视觉的模型读取。",
        ]
    )


def render_tool_quick_reference_markdown() -> str:
    return "\n".join(
        [
            "# 工具速查手册",
            "",
            "这是一份给模型直接读取的压缩版工具选择说明。",
            "",
            "先做什么：",
            "1. 想知道当前机器状态：`get_system_info`、`get_env`、`get_time`、`get_network_config`。",
            "2. 想知道当前桌面和窗口：`get_desktop_context`、`get_active_window`、`list_windows`、`capture_screenshot`。",
            "3. 想知道当前项目和文件：`list_tree`、`find_files`、`search_text`、`read_file`。",
            "",
            "按任务选工具：",
            "- 读代码或文本：`read_file`、`search_text`、`find_files`。",
            "- 改代码或文本：`patch_lines`、`replace_text`、`write_file`、`write_json_file`。",
            "- 查目录和文件：`list_tree`、`stat_path`、`list_recent_files`、`list_desktop_files`。",
            "- 复制、移动、删除、建目录：`copy_path`、`move_path`、`delete_path`、`mkdir`。",
            "- 压缩解压：`zip_paths`、`extract_archive`。",
            "- 二进制或哈希：`read_binary_file`、`write_binary_file`、`hash_file`。",
            "- 执行命令：`run_shell`，PowerShell 任务用 `run_powershell`，简单命令可用 `run_cmd`。",
            "- 进程管理：`list_processes`、`get_process_tree`、`kill_process`、`start_process`。",
            "- 查端口和网络连通性：`find_port_process`、`list_listening_ports`、`list_established_connections`、`tcp_connect`、`raw_tcp_exchange`、`udp_send_receive`、`websocket_connect`、`scan_ports`、`ping_host`、`trace_route`、`dns_lookup`、`resolve_dns_records`。",
            "- 下载或请求网页/API：`http_head`、`fetch_response_headers`、`download_file`、`http_request`、`submit_web_form`、`upload_file`、`trace_http_redirects`、`get_tls_certificate`。",
            "- 读网页正文：`fetch_webpage_text`、`webpage_to_markdown`。",
            "- 提取网页元数据：`extract_webpage_metadata`。",
            "- 抓网页链接：`extract_links_from_webpage`。",
            "- 递进抓取站内多页：`crawl_webpages`。",
            "- 抓网页表格：`extract_tables_from_webpage`。",
            "- 抓网页特定元素：`extract_webpage_elements`。",
            "- 值班和长期等待：`wait`、`wait_until`、`wait_for_file`、`wait_for_process`、`wait_for_port`、`wait_for_http`、`wait_for_window`、`wait_for_desktop_change`、`create_background_task`、`list_background_tasks`、`get_background_task`、`summarize_background_task`、`get_task_handoff`。",
            "- 摄像头：`list_cameras`、`capture_camera_photo`。",
            "",
            "读网页的推荐顺序：",
            "1. 先用 `http_head` 或 `fetch_response_headers` 看头部，再用 `fetch_webpage_text` 或 `webpage_to_markdown` 读当前页正文。",
            "2. 需要先判断页面定位时，用 `extract_webpage_metadata` 看标题、canonical、meta 和结构化信息。",
            "3. 再用 `extract_links_from_webpage` 找文档链接、章节链接、详情页、下载链接、上一篇/下一篇、目录入口。",
            "4. 如果当前页明显只是目录页、导航页、索引页、列表页、聚合页或文档首页，不要停在这一页，应继续进入最相关的站内链接；需要批量递进时直接用 `crawl_webpages`。",
            "5. 沿关键链接继续读取多个相关页面，优先正文页而不是只看链接标题；必要时配合 `extract_webpage_elements` 或 `extract_tables_from_webpage` 做精确提取。",
            "6. 需要精确提取 `h1`、`meta`、`article`、`a`、`main` 时，再用 `extract_webpage_elements`。",
            "",
            "值班任务的推荐顺序：",
            "1. 短等待优先用 `wait` 或 `wait_until`。",
            "2. 等具体条件优先用 `wait_for_file`、`wait_for_process`、`wait_for_port`、`wait_for_http`、`wait_for_window`、`wait_for_desktop_change`。",
            "3. 用户长时间离开时优先用 `create_background_task` 托管。",
            "4. 给后台任务补 `create_task_plan`、`append_task_event`、`record_task_artifact` 方便交接。",
            "5. 重新接手时先调 `get_background_task`、`summarize_background_task` 或 `get_task_handoff`。",
            "6. 等用户拍板时优先 `mark_task_waiting_for_user`，等外部条件时优先 `mark_task_waiting_for_condition`。",
            "",
            "什么时候切到值班模式：",
            "- 用户明确说要离开、去睡觉、稍后回来、今晚全程值班。",
            "- 等待时长不可控，可能从几分钟拖到几小时。",
            "- 任务可能跨会话、跨重连，需要后面继续接手。",
            "- 你已经知道后续要观察什么条件，但当前不值得一直占着同步回复空等。",
            "",
            "读代码和大文件的推荐顺序：",
            "1. 先 `list_tree` 看目录，再 `find_files` 找候选文件。",
            "2. 再用 `search_text` 定位函数名、类名、配置项、报错文本或关键字。",
            "3. 命中后用 `read_file(path=..., start_line=..., end_line=...)` 分段读上下文，优先每段 `50` 到 `200` 行。",
            "4. 第一段不够就围绕命中点向前后扩读，不要默认整文件读取。",
            "5. 修改后再 `read_file` 回读结果，最后用 `run_shell/run_cmd/run_powershell` 验证。",
            "",
            "修改文件的推荐顺序：",
            "1. 未知项目先 `list_tree` 或 `find_files`，不要直接猜文件路径。",
            "2. 先 `search_text` 定位，再 `read_file` 读局部上下文。",
            "3. 小范围改动优先 `patch_lines` 或 `replace_text`。",
            "4. 只有在确实需要整段重写时再用 `write_file`。",
            "5. 配置是 JSON 时优先 `read_json_file` 和 `write_json_file`。",
            "",
            "执行命令的推荐顺序：",
            "1. 跨平台优先 `run_shell`。",
            "2. PowerShell 特定任务用 `run_powershell`。",
            "3. 需要长期运行的程序用 `start_process`。",
            "",
            "超时建议：",
            "- 网络工具和长时工具尽量显式传 `timeout_ms`。",
            "- 命令输出过长时尽量设置 `max_output_chars`。",
            "",
            "缺依赖时：",
            "- 如果工具已明确提示缺少什么，并且当前任务确实需要它，可以用现有命令工具安装最小必需依赖后重试。",
            "",
            "完整工具清单：",
            "- 调 `list_all_tools()`",
            "- 调 `list_all_tools(include_descriptions=True)`",
            "- 读 `resource://guides/tools/{tool_name}`",
        ]
    )


def render_guides_index_markdown() -> str:
    return "\n".join(
        [
            "# Guide 与 Prompt 索引",
            "",
            "这是一份总入口索引，用来告诉模型当前 MCP 内置了哪些 guide resources 和 prompts。",
            "",
            "建议读取顺序：",
            "1. 先读 `resource://guides/overview` 了解整体能力。",
            "2. 再读 `resource://guides/tool-quick-reference` 快速选工具。",
            "3. 需要更细工作方式时读 `resource://guides/model-playbook`。",
            "4. 需要按任务类型串联多个工具时读对应 workflow。", 
            "5. 需要某个单独工具的详细参数与示例时读 `resource://guides/tools/{tool_name}`。",
            "",
            "可读的 guide resources：",
            "- `resource://guides/index`: 当前这份索引。",
            "- `resource://guides/overview`: MCP 总览。",
            "- `resource://guides/model-playbook`: 模型操作手册。",
            "- `resource://guides/tool-quick-reference`: 工具速查手册。",
            "- `resource://guides/workflows/web-research`: 网页阅读工作流。",
            "- `resource://guides/workflows/code-edit`: 代码修改工作流。",
            "- `resource://guides/workflows/desktop-observation`: 桌面观察工作流。",
            "- `resource://guides/workflows/network-diagnostics`: 网络排查工作流。",
            "- `resource://guides/workflows/duty-watch`: 值班与交接工作流。",
            "- `resource://guides/tools/{tool_name}`: 某个单独工具的详细说明。",
            "",
            "可用的 prompts：",
            "- `workspace_operator(task)`: 通用工作站操作提示。",
            "- `multi_tool_executor(task)`: 强调主动组合多个工具推进任务。",
            "- `duty_shift_operator(task, situation='')`: 值班、托管、交接专用提示。",
            "- `web_research_operator(task, url='')`: 网页阅读、抓取、提取专用提示。",
            "- `code_fix_operator(task, root='')`: 代码修复与开发专用提示。",
            "- `network_diagnostics_operator(task, target='')`: 网络排查专用提示。",
            "",
            "如何选择：",
            "- 任务很泛：先读 `overview` 或直接用 `workspace_operator`。",
            "- 想尽快开工：读 `tool-quick-reference`。",
            "- 想让模型主动多步推进：用 `multi_tool_executor`。",
            "- 任务是网页、代码、桌面、网络之一：优先读对应 workflow，必要时再用对应 prompt。",
            "- 任务涉及长期等待、用户离线、断线恢复、交接：优先读 `resource://guides/workflows/duty-watch` 或直接用 `duty_shift_operator`。",
            "",
            "补充：",
            "- 运行时完整工具列表仍以 `list_all_tools(include_descriptions=True)` 为准。",
            "- 这些 guides 和 prompts 的目的都是让模型更主动、更合理地使用工具，而不是减少工具调用。",
        ]
    )


def render_workflow_web_research_markdown() -> str:
    return "\n".join(
        [
            "# 网页阅读工作流",
            "",
            "适用场景：",
            "- 想快速读一个网页的正文",
            "- 想从网页里继续找文档链接、下载链接、跳转链接",
            "- 想提取某个标题、描述、文章主体、特定链接块",
            "- 当前页只是目录页、导航页、索引页或文档首页，需要继续深入站内内容页",
            "",
            "推荐顺序：",
            "1. 先调 `trace_http_redirects(url=...)` 看最终落地页和跳转链。",
            "2. 再调 `http_head(url=...)` 或 `fetch_response_headers(url=...)` 看 `Content-Type`、`Content-Length` 和缓存头。",
            "3. 然后调 `fetch_webpage_text(url=..., timeout_ms=...)` 或 `webpage_to_markdown(url=...)` 读取主要正文。",
            "4. 再调 `extract_links_from_webpage(url=...)`，找文档链接、章节链接、详情页、下载链接、上一篇/下一篇和目录入口。",
            "5. 如果当前页明显只是目录页、导航页、索引页、列表页、搜索结果页、聚合页或文档首页，不要停在表面，应继续进入其中最相关的站内链接。",
            "6. 沿关键链接继续读多个相关页面，优先真正有正文的内容页，而不是只停在链接标题、目录项标题或页面摘要。",
            "7. 想快速看页面元数据、canonical、Open Graph 或 JSON-LD 时，调 `extract_webpage_metadata(url=...)`。",
            "8. 如果页面里有表格，再调 `extract_tables_from_webpage(url=...)`。",
            "9. 如果要精确抓取 `h1`、`meta`、`article`、`a`、`main`，再调 `extract_webpage_elements(url=..., tag=..., attr_filters=...)`。",
            "10. 如果需要提交网页搜索表单或普通表单，再调 `submit_web_form(url=..., form_fields=..., method=...)`。",
            "11. 如果需要把本地文件发到网页或接口，再调 `upload_file(url=..., file_path=..., timeout_ms=...)`；多文件时可先 `zip_paths(...)` 再上传。",
            "12. 如果网页里存在下载链接，再用 `download_file(url=..., destination=..., timeout_ms=...)`。",
            "",
            "常见组合：",
            "- 只读正文：`http_head` -> `fetch_webpage_text` 或 `webpage_to_markdown`",
            "- 读正文 + 找 PDF：`http_head` -> `fetch_webpage_text` -> `extract_links_from_webpage(href_filter='.pdf')`",
            "- 文档首页继续深挖：`trace_http_redirects` -> `fetch_webpage_text` -> `extract_links_from_webpage` -> 继续读取章节页 / API 页 / FAQ 页",
            "- 想批量沿站内继续读：`crawl_webpages(start_url=..., max_pages=..., max_depth=...)`",
            "- 先判断页面类型：`extract_webpage_metadata` -> 再决定 `fetch_webpage_text` 或 `crawl_webpages`",
            "- 目录页继续进详情：`fetch_webpage_text` -> `extract_links_from_webpage` -> 进入详情页后再 `fetch_webpage_text` 或 `webpage_to_markdown`",
            "- 抓网页表格：`extract_tables_from_webpage`",
            "- 取网页标题和描述：`extract_webpage_elements(tag='title')` + `extract_webpage_elements(tag='meta', attr_filters={'name': 'description'})`",
            "",
            "建议：",
            "- 长网页尽量显式传 `max_text_chars`。",
            "- 网络较慢时显式传更大的 `timeout_ms`。",
            "- 不要因为第一页能看到目录项就停止；只要任务目标仍未满足，就继续沿相关站内链接深入读取。",
        ]
    )


def render_workflow_code_edit_markdown() -> str:
    return "\n".join(
        [
            "# 代码修改工作流",
            "",
            "适用场景：",
            "- 阅读项目结构并定位目标文件",
            "- 搜索函数、类、配置项或报错文本",
            "- 做小范围精确修改或整段重写",
            "- 面对大文件、长代码文件、陌生代码库时分段读取与局部修改",
            "",
            "推荐顺序：",
            "1. 先用 `list_tree(root=...)` 或 `find_files(root=..., pattern=...)` 找文件。",
            "2. 再用 `search_text(root=..., query=..., file_pattern=...)` 定位符号、报错、配置项或文本片段。",
            "3. 命中后用 `read_file(path=..., start_line=..., end_line=...)` 读取局部上下文，不要默认整文件通读。",
            "4. 大文件优先按 `50` 到 `200` 行分段读取；如果上下文不够，再围绕命中行向前后扩读。",
            "5. 小范围修改优先用 `patch_lines` 或 `replace_text`。",
            "6. 只有在确实需要整段覆盖时再用 `write_file` 或 `write_json_file`。",
            "7. 修改后先回读已修改片段，再用 `run_shell`、`run_cmd`、`run_powershell` 执行测试、lint 或检查命令。",
            "",
            "常见组合：",
            "- 定位函数定义：`search_text` -> `read_file`",
            "- 读大文件中的单个函数：`search_text(query='def foo', file_pattern='*.py')` -> `read_file(start_line=命中行-20, end_line=命中行+80)`",
            "- 未知仓库里找入口：`list_tree` -> `find_files(pattern='*.py' 或 '*.ts')` -> `search_text(query='main|app|server', use_regex=True)`",
            "- 改少量行：`read_file` -> `patch_lines`",
            "- 改固定配置值：`search_text` -> `replace_text`",
            "- 改 JSON：`read_json_file` -> `write_json_file`",
            "",
            "建议：",
            "- 改动前先读文件，不要盲写。",
            "- 除非文件很短或任务明确要求，否则不要把整个大文件一次性读入上下文。",
            "- `search_text` 时优先加 `file_pattern`，必要时调小或调大 `max_results`、`max_file_size_bytes`。",
            "- `patch_lines` 适合已知行号范围，`replace_text` 适合稳定固定文本，`write_file` 适合新建或整体重写。",
            "- 改完至少做一次回读；如果仓库支持验证命令，尽量执行验证。",
            "- 输出很长时给命令设置 `max_output_chars`。",
        ]
    )


def render_workflow_desktop_observation_markdown() -> str:
    return "\n".join(
        [
            "# 桌面观察工作流",
            "",
            "适用场景：",
            "- 想知道当前前台窗口是什么",
            "- 想看后台还有哪些窗口",
            "- 想结合截图理解当前桌面状态",
            "",
            "推荐顺序：",
            "1. 先调 `get_desktop_context()`，一次拿到前台和后台窗口概况。",
            "2. 如果只关心当前活动窗口，再调 `get_active_window()`。",
            "3. 如果想按标题筛选特定窗口，再调 `list_windows(title_filter=...)`。",
            "4. 如果需要视觉确认，优先调 `capture_screenshot(return_image_content=true)`，这样支持视觉内容的客户端会直接把截图送给模型；不支持时再退回到保存路径模式。",
            "",
            "常见组合：",
            "- 了解当前桌面：`get_desktop_context`",
            "- 看某个应用是否打开：`list_windows(title_filter='Chrome')`",
            "- 看窗口信息 + 截图：`get_active_window` -> `capture_screenshot(return_image_content=true)`",
            "",
            "建议：",
            "- 如果窗口很多，可在 `get_desktop_context` 或 `list_windows` 中设置 `limit`。",
            "- 支持视觉内容的客户端里，优先给截图和拍照工具传 `return_image_content=true`，让模型直接拿到图像；如果客户端不支持，工具仍会返回保存路径和结构化信息。",
        ]
    )


def render_workflow_network_diagnostics_markdown() -> str:
    return "\n".join(
        [
            "# 网络排查工作流",
            "",
            "适用场景：",
            "- 想确认当前机器网络配置",
            "- 想测某个域名是否能解析",
            "- 想测某个主机、端口、接口是否可达",
            "- 想查本机是谁在监听某个端口",
            "",
            "推荐顺序：",
            "1. 先调 `get_network_config(timeout_ms=...)` 看整体网络信息。",
            "2. 看适配器细节时调 `list_network_adapters()`。",
            "3. 测域名解析时先调 `resolve_dns_records(hostname=...)`，需要快速看 IP 时再调 `dns_lookup(hostname=...)`。",
            "4. 已知 IP 想反查主机名时调 `reverse_dns_lookup(ip_address=...)`。",
            "5. 测主机可达时调 `ping_host(hostname=..., timeout_ms=...)`。",
            "6. 看链路路径时调 `trace_route(host=...)`。",
            "7. 测 TCP 端口时调 `tcp_connect(host=..., port=..., timeout_ms=...)`；需要直接发协议数据时调 `raw_tcp_exchange(...)`。",
            "8. 测 UDP 服务是否回包时调 `udp_send_receive(...)`。",
            "9. 小范围端口扫描时调 `scan_ports(host=..., start_port=..., end_port=...)` 或 `scan_ports(host=..., ports=[...])`。",
            "10. 测 HTTP/HTTPS 接口时先调 `http_head(url=...)` 或 `fetch_response_headers(url=...)`，需要真正发请求体时再调 `http_request(url=..., timeout_ms=...)`，需要上传本地文件时调 `upload_file(url=..., file_path=..., timeout_ms=...)`，需要看跳转链时调 `trace_http_redirects(url=...)`。",
            "11. 测 WebSocket 接口时调 `websocket_connect(url=..., messages=[...], timeout_ms=...)`。",
            "12. 需要看 TLS 证书时调 `get_tls_certificate(host=...)`。",
            "13. 查本机监听端口时调 `list_listening_ports()` 或 `find_port_process(port=...)`；查已建立连接时调 `list_established_connections()`。",
            "",
            "常见组合：",
            "- 排查服务打不开：`resolve_dns_records` -> `ping_host` -> `tcp_connect` -> `http_head` -> `http_request`",
            "- 看某台主机一小段端口范围：`scan_ports(host='127.0.0.1', start_port=8000, end_port=8100)`",
            "- 查本地 8000 端口是谁占用：`find_port_process(port=8000)`",
            "- 看机器网卡信息：`get_network_config` -> `list_network_adapters`",
            "- 看当前机器正在连哪些远端：`list_established_connections()`",
            "",
            "建议：",
            "- 网络慢时显式传更大的 `timeout_ms`。",
            "- 先分层定位：解析、主机可达、端口可达、HTTP 可达，不要混在一起猜。",
        ]
    )


def render_workflow_duty_watch_markdown() -> str:
    return "\n".join(
        [
            "# 值班与交接工作流",
            "",
            "适用场景：",
            "- 用户离开电脑后，模型还需要持续观察文件、端口、网页、窗口或桌面变化。",
            "- 会话可能中断、重连，模型需要回来后继续接手。",
            "- 任务周期较长，需要把步骤、事件和产物记清楚。",
            "- 用户一句话让模型自己做一件事持续一小时、半小时或更久。",
            "",
            "先判断是否真的要进入值班模式：",
            "1. 如果只差几秒或几十秒，并且你会在当前回复里继续推进，优先 `wait` 或 `wait_until`。",
            "2. 如果等待对象很明确，但用户暂时不离线，也可以先同步用 `wait_for_*` 看一小段时间。",
            "3. 如果用户会离开、睡觉、稍后回来，或者任务可能跨会话持续较久，优先立即切到后台值班，不要在当前回复里空等。",
            "4. 如果用户直接说“你自己做一个小时”“帮我盯一小时”，默认应先创建后台任务，再补步骤计划和交接摘要，而不是同步空等一个小时。",
            "",
            "推荐顺序：",
            "1. 短等待先用 `wait` 或 `wait_until`。",
            "2. 等明确条件时优先用 `wait_for_file`、`wait_for_process`、`wait_for_port`、`wait_for_http`、`wait_for_window`、`wait_for_desktop_change`。",
            "3. 用户可能离线较久时，把等待动作托管给 `create_background_task`，不要只在当前回复里空等。",
            "4. 托管一小时这类任务时，先创建后台任务，再立刻补 `create_task_plan`，让任务有清晰步骤。",
            "5. 接着用 `append_task_event` 记录“当前已经做了什么、现在在等什么、下一步准备做什么”。",
            "6. 只要有文件、截图、日志、压缩包等结果，就马上 `record_task_artifact`。",
            "7. 任务运行期间，定期用 `get_background_task` 或 `list_background_tasks` 看进度；如果当前会话还在线，也可以短暂 `wait_for_background_task`。",
            "8. 如果到了用户约定的时间点，用 `wait_until` + `get_scheduler_time` 配合检查，然后视情况 `summarize_background_task` 或 `get_task_handoff`。",
            "9. 需要给新会话或用户交接时优先用 `get_task_handoff`，必要时再补 `summarize_background_task`。",
            "",
            "值班时建议记录的东西：",
            "- 当前到底在等什么条件。",
            "- 条件满足后准备继续做哪一步。",
            "- 哪些文件、截图、日志、打包结果需要作为产物保留。",
            "- 哪些地方需要用户拍板，而不是继续自动执行。",
            "- 任务是不是已经提前完成，还是仍然要等到约定时间。",
            "",
            "遇到用户离线时的做法：",
            "- 不要因为用户暂时不回消息就停在原地；只要后续步骤能被条件化，就应转成后台任务。",
            "- 如果必须等用户决定，先 `mark_task_waiting_for_user`，把具体问题写清楚，再等待下次接手。",
            "- 如果只是等条件成熟，优先 `mark_task_waiting_for_condition` 或直接让后台任务继续轮询。",
            "- 如果用户给的是“做一个小时”这类明确时长，建议把 `timeout_ms` 设成对应时长，并在计划里写明到点后的收口动作。",
            "- 如果任务提前完成，不要空转到超时；先记录完成、产物和总结，再决定是否继续关联检查。",
            "",
            "常见组合：",
            "- 等服务恢复：`create_background_task(task_type='wait_http')` -> `create_task_plan` -> `append_task_event` -> `get_task_handoff`",
            "- 等安装器弹窗：`create_background_task(task_type='wait_window')` -> `wait_for_background_task` -> `capture_screenshot`",
            "- 盯桌面状态变化：`wait_for_desktop_change` 或 `create_background_task(task_type='wait_desktop_change')` -> `get_background_task`",
            "- 等用户第二天回复后再继续：`create_background_task(task_type='sleep' 或明确条件)` + `mark_task_waiting_for_user` + `get_task_handoff`",
            "- 先短等，再转后台：先 `wait_for_http(..., timeout_ms=30000)`，若仍未恢复再 `create_background_task(task_type='wait_http')`",
            "- 用户说“你自己做一个小时”：`create_background_task` -> `create_task_plan` -> `append_task_event` -> `record_task_artifact` -> `get_task_handoff` -> 到点后 `summarize_background_task`",
            "",
            "建议：",
            "- 长时任务尽量显式传 `timeout_ms` 和 `poll_interval_ms`。",
            "- 需要后续交接时，越早记录步骤和事件，后面越容易恢复上下文。",
            "- 如果你已经预计稍后会断线或用户会离开，尽量在离开前先生成一次 `get_task_handoff`。",
            "- 到点时先看 `get_scheduler_time`，再按任务状态决定是总结、继续、暂停还是取消。",
        ]
    )
