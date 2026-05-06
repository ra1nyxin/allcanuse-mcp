from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from allcanuse_mcp.descriptions import SERVER_INSTRUCTIONS
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS
from allcanuse_mcp.descriptions import build_server_instructions
from allcanuse_mcp.descriptions import render_runtime_context_text
from allcanuse_mcp.descriptions import render_guides_index_markdown
from allcanuse_mcp.descriptions import render_model_playbook_markdown
from allcanuse_mcp.descriptions import render_overview_markdown
from allcanuse_mcp.descriptions import render_tool_quick_reference_markdown
from allcanuse_mcp.descriptions import render_workflow_code_edit_markdown
from allcanuse_mcp.descriptions import render_workflow_desktop_observation_markdown
from allcanuse_mcp.descriptions import render_workflow_duty_watch_markdown
from allcanuse_mcp.descriptions import render_workflow_network_diagnostics_markdown
from allcanuse_mcp.descriptions import render_workflow_web_research_markdown
from allcanuse_mcp.tools import device as device_tools
from allcanuse_mcp.tools import code as code_tools
from allcanuse_mcp.tools import duty as duty_tools
from allcanuse_mcp.tools import exec as exec_tools
from allcanuse_mcp.tools import files as file_tools
from allcanuse_mcp.tools import network as network_tools
from allcanuse_mcp.tools import optimization as optimization_tools
from allcanuse_mcp.tools import system as system_tools
from allcanuse_mcp.tools import windows as window_tools


def _tool_category(tool_name: str) -> str:
    categories = {
        "system": {
            "list_all_tools",
            "get_system_info",
            "get_env",
            "get_time",
            "get_disk_usage",
            "get_network_config",
            "get_ipconfig",
            "list_network_adapters",
        },
        "exec": {
            "run_shell",
            "run_cmd",
            "run_powershell",
            "start_process",
            "start_managed_process",
            "list_managed_processes",
            "get_managed_process",
            "note_managed_process",
            "stop_managed_process",
            "kill_process",
            "list_processes",
            "get_process_tree",
            "find_port_process",
        },
        "files": {
            "list_tree",
            "read_file",
            "write_file",
            "patch_lines",
            "replace_text",
            "mkdir",
            "move_path",
            "delete_path",
            "zip_paths",
            "extract_archive",
            "list_desktop_files",
            "find_files",
            "search_text",
            "stat_path",
            "copy_path",
            "hash_file",
            "read_binary_file",
            "write_binary_file",
            "list_recent_files",
            "read_json_file",
            "write_json_file",
            "which_command",
        },
        "security": {
            "scan_suspicious_files",
        },
        "deployment": {
            "deploy_and_update_service",
        },
        "database": {
            "extract_sqlite_content",
            "extract_postgresql_content",
            "extract_mysql_content",
        },
        "code": {
            "detect_c_toolchains",
            "compile_c_program",
            "check_c_syntax",
            "preprocess_c_source",
            "inspect_c_source",
            "scan_c_memory_risks",
            "scan_c_numeric_risks",
            "evaluate_c_math_expression",
            "generate_c_numeric_test_harness",
            "generate_c_math_utils_header",
            "generate_c_vector_math_header",
            "generate_c_lookup_table_header",
            "generate_c_polynomial_eval_header",
            "generate_c_matrix_math_header",
            "generate_c_statistics_header",
            "generate_c_fixed_point_header",
            "generate_c_build_files",
            "format_c_code",
        },
        "seo": {
            "audit_seo",
        },
        "optimization": {
            "optimize_images_for_memory",
        },
        "device": {"list_cameras", "capture_camera_photo"},
        "duty": {
            "wait",
            "wait_until",
            "get_scheduler_time",
            "wait_for_file",
            "wait_for_process",
            "wait_for_port",
            "wait_for_http",
            "wait_for_window",
            "wait_for_desktop_change",
            "create_background_task",
            "list_background_tasks",
            "get_background_task",
            "cancel_background_task",
            "pause_background_task",
            "resume_background_task",
            "wait_for_background_task",
            "create_task_plan",
            "update_task_step",
            "append_task_event",
            "record_task_artifact",
            "summarize_background_task",
            "get_task_handoff",
            "mark_task_waiting_for_user",
            "mark_task_waiting_for_condition",
        },
        "window": {"list_windows", "get_active_window", "get_desktop_context", "capture_screenshot"},
        "network": {
            "download_file",
            "http_request",
            "http_head",
            "fetch_response_headers",
            "submit_web_form",
            "upload_file",
            "fetch_webpage_text",
            "webpage_to_markdown",
            "extract_links_from_webpage",
            "extract_webpage_metadata",
            "extract_tables_from_webpage",
            "extract_webpage_elements",
            "crawl_webpages",
            "trace_http_redirects",
            "websocket_connect",
            "trace_route",
            "resolve_dns_records",
            "reverse_dns_lookup",
            "dns_lookup",
            "get_tls_certificate",
            "ping_host",
            "tcp_connect",
            "raw_tcp_exchange",
            "udp_send_receive",
            "scan_ports",
            "list_established_connections",
            "list_listening_ports",
        },
    }
    for category, names in categories.items():
        if tool_name in names:
            return category
    return "other"


def create_server(*, host: str = "127.0.0.1", port: int = 8000) -> FastMCP:
    mcp = FastMCP(
        name="allcanuse-mcp",
        instructions=build_server_instructions(),
        host=host,
        port=port,
    )

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_all_tools"])
    def list_all_tools(include_descriptions: bool = False) -> dict:
        items = []
        for tool_name in sorted(TOOL_DESCRIPTIONS):
            first_line = TOOL_DESCRIPTIONS[tool_name].splitlines()[0]
            item = {
                "name": tool_name,
                "category": _tool_category(tool_name),
                "summary": first_line,
            }
            if include_descriptions:
                item["description"] = TOOL_DESCRIPTIONS[tool_name]
            items.append(item)
        return {"count": len(items), "tools": items}

    system_tools.register(mcp)
    exec_tools.register(mcp)
    file_tools.register(mcp)
    code_tools.register(mcp)
    device_tools.register(mcp)
    duty_tools.register(mcp)
    window_tools.register(mcp)
    network_tools.register(mcp)
    optimization_tools.register(mcp)

    @mcp.resource(
        "resource://guides/index",
        name="allcanuse-guides-index",
        title="Guide 与 Prompt 索引",
        mime_type="text/markdown",
        description="列出当前 MCP 内置的 guides、workflows 和 prompts，方便模型先发现有哪些内置说明可用。",
    )
    def guide_index() -> str:
        return render_guides_index_markdown()

    @mcp.resource(
        "resource://guides/overview",
        name="allcanuse-guide-overview",
        title="allcanuse 使用总览",
        mime_type="text/markdown",
        description="面向模型的总览指南，介绍如何在这个 MCP Server 中选择工具。",
    )
    def guide_overview() -> str:
        return render_overview_markdown()

    @mcp.resource(
        "resource://guides/model-playbook",
        name="allcanuse-model-playbook",
        title="模型操作手册",
        mime_type="text/markdown",
        description="给中小模型的详细工作手册，解释如何选择和组合工具。",
    )
    def guide_model_playbook() -> str:
        return render_model_playbook_markdown()

    @mcp.resource(
        "resource://guides/tool-quick-reference",
        name="allcanuse-tool-quick-reference",
        title="工具速查手册",
        mime_type="text/markdown",
        description="给模型的压缩版工具速查资源，适合先快速决定该用哪些工具。",
    )
    def guide_tool_quick_reference() -> str:
        return render_tool_quick_reference_markdown()

    @mcp.resource(
        "resource://guides/workflows/web-research",
        name="allcanuse-workflow-web-research",
        title="网页阅读工作流",
        mime_type="text/markdown",
        description="给模型的网页阅读工作流，说明如何组合网页正文、链接和元素提取工具。",
    )
    def guide_workflow_web_research() -> str:
        return render_workflow_web_research_markdown()

    @mcp.resource(
        "resource://guides/workflows/code-edit",
        name="allcanuse-workflow-code-edit",
        title="代码修改工作流",
        mime_type="text/markdown",
        description="给模型的代码修改工作流，说明如何组合文件搜索、读取、修改和验证工具。",
    )
    def guide_workflow_code_edit() -> str:
        return render_workflow_code_edit_markdown()

    @mcp.resource(
        "resource://guides/workflows/desktop-observation",
        name="allcanuse-workflow-desktop-observation",
        title="桌面观察工作流",
        mime_type="text/markdown",
        description="给模型的桌面观察工作流，说明如何组合窗口和截图工具。",
    )
    def guide_workflow_desktop_observation() -> str:
        return render_workflow_desktop_observation_markdown()

    @mcp.resource(
        "resource://guides/workflows/network-diagnostics",
        name="allcanuse-workflow-network-diagnostics",
        title="网络排查工作流",
        mime_type="text/markdown",
        description="给模型的网络排查工作流，说明如何组合网络配置、连通性和接口工具。",
    )
    def guide_workflow_network_diagnostics() -> str:
        return render_workflow_network_diagnostics_markdown()

    @mcp.resource(
        "resource://guides/workflows/duty-watch",
        name="allcanuse-workflow-duty-watch",
        title="值班与交接工作流",
        mime_type="text/markdown",
        description="给模型的值班工作流，说明如何组合等待、后台任务、事件记录和任务交接工具。",
    )
    def guide_workflow_duty_watch() -> str:
        return render_workflow_duty_watch_markdown()

    @mcp.resource(
        "resource://guides/tools/{tool_name}",
        name="allcanuse-tool-guide",
        title="单个工具说明",
        mime_type="text/markdown",
        description="读取某个工具的详细说明和调用示例。",
    )
    def guide_tool(tool_name: str) -> str:
        if tool_name not in TOOL_DESCRIPTIONS:
            known = ", ".join(sorted(TOOL_DESCRIPTIONS))
            return f"# 未知工具\n\n`{tool_name}` 不存在。\n\n可用工具：\n{known}"
        return f"# {tool_name}\n\n{TOOL_DESCRIPTIONS[tool_name]}"

    @mcp.prompt(
        name="workspace_operator",
        title="工作站操作提示",
        description="给中小模型一段更直接的工具使用提示，帮助其在 Windows 或 Linux 实验环境中工作。",
    )
    def workspace_operator(task: str) -> list[dict]:
        time_hint = render_runtime_context_text()
        return [
            {
                "role": "user",
                "content": (
                    f"当前时间上下文：{time_hint}"
                    "你可以使用当前 MCP Server 暴露的工具完成这项任务。"
                    "这些工具就是你的手、眼睛和操作能力；需要观察、读取、判断、修改、验证时，直接用工具。"
                    "不要无谓回避工具，也不要只给口头建议而不动手。"
                "优先按“观察 -> 判断 -> 执行 -> 验证”的顺序推进。"
                "能用多个相关工具组合完成时，就合理组合，例如："
                "代码任务先看目录和文件，再修改，再跑命令验证；"
                    "网页任务先读正文，再提取链接或元素；如果当前页像目录页、导航页、列表页、文档首页或索引页，就继续进入其中最相关的站内链接，不要只停一页；需要批量递进时直接用 `crawl_webpages`；"
                "网络任务先看配置，再测 DNS、ping、TCP、HTTP。"
                    "如果访问海外网站、执行 `git clone`、`git push`、`pip install`、`npm install`、`apt install` 或其他海外网络相关动作时出现超时、连接失败或拉取失败，先检查本机是否已有代理可复用：优先看 `list_listening_ports` 或 `find_port_process` 是否有 `7890`、`7897`、`46464` 之类监听端口，再看 `list_processes` 是否有 `v2rayN`、`Clash for Windows`、`clash`、`clash-core-service` 等进程，必要时再看 `get_env` 里的代理环境变量。"
                    "如果已经发现可用代理，就直接带代理重试当前网络任务；如果仍失败，或根本没发现代理，再询问用户是否开启了代理软件，并请用户帮忙打开后继续。"
                    "如果任务涉及较长等待、用户离线、稍后回来、今晚值班、断线后继续接手，优先切到值班模式：短等用 `wait`，明确条件用 `wait_for_*`，长期托管用 `create_background_task`，交接用 `get_task_handoff`。"
                    "如果用户一句话要求你自己做一小时左右的事情，默认先创建后台任务，再补任务计划、事件和产物记录，不要同步空等一小时。"
                    "如果任务是长时间训练、长时间推理、长时间实验或需要持续跑几个小时到几天的进程，不要只用普通 `start_process`；优先用 `start_managed_process` 把它登记成受监视、受保护的长时进程，后续只监视、记录和汇报，除非用户明确要求停止，否则不要主动 `kill_process`。"
                    "如果任务涉及麦克风录音，当前仓库里可直接调用本地二进制 `src\\allcanuse_mcp\\tools\\micrecording.exe`；它无参数运行时会先输出完整使用示例，不会直接开始录音。模型应先看帮助，再带 `-t` 和可选 `-o` 参数正式调用。"
                    "优先使用结构化工具，而不是把所有事情都交给 shell。"
                    "如果当前任务依赖缺失，并且工具或命令已经明确提示缺少什么，"
                    "你可以先安装最小必需依赖后继续。"
                    f"当前任务：{task}"
                ),
            }
        ]

    @mcp.prompt(
        name="multi_tool_executor",
        title="多工具执行提示",
        description="要求模型主动组合多个工具推进任务，而不是停留在单步建议上。",
    )
    def multi_tool_executor(task: str) -> list[dict]:
        time_hint = render_runtime_context_text()
        return [
            {
                "role": "user",
                "content": (
                    f"当前时间上下文：{time_hint}"
                    "你现在应把 MCP 工具当作自己的手和眼睛。"
                    "这个任务默认不是只靠语言分析完成，而是要主动使用多个相关工具推进。"
                    "优先按“观察 -> 判断 -> 执行 -> 验证”的顺序工作。"
                    "不要无谓回避工具；如果某一步需要事实、状态、文件内容、网页内容、窗口状态或网络结果，就直接调用工具获取。"
                    "如果任务涉及代码，先找文件并读取，再修改，再执行验证命令。"
                    "如果任务涉及网页，先读正文，再找链接或抓元素；如果当前页明显只是目录页、导航页、列表页、文档首页、索引页或搜索结果页，就沿最相关的站内链接继续深入，不要只读一页；需要批量推进时优先 `crawl_webpages`。"
                    "如果任务涉及网络，先看配置，再测 DNS、ping、TCP、HTTP。"
                    "如果海外网络访问受阻，或 `git clone`、`git push`、`pip install`、`npm install`、`apt install` 等动作因超时、连接失败、握手失败而卡住，先检查本机是否已有代理：用 `list_listening_ports` / `find_port_process` 看 `7890`、`7897`、`46464` 等端口，用 `list_processes` 看 `v2rayN`、`Clash for Windows`、`clash`、`clash-core-service` 等进程，必要时再看 `get_env` 里的代理变量。"
                    "如果确认本机已有代理，就直接改用代理重试；如果没有发现代理，或者带代理仍失败，再询问用户是否开启代理软件并请用户协助开启。"
                    "如果任务涉及桌面，先看桌面上下文，再看活动窗口或截图。"
                    "如果任务涉及较长等待、用户离线、稍后回来、需要跨会话继续，主动考虑值班工具：短等用 `wait`，明确条件用 `wait_for_*`，长期托管用 `create_background_task`，恢复交接用 `get_task_handoff`。"
                    "如果用户说的是“自己做一个小时”“帮我盯一小时”“到点再汇报”，直接按后台值班流程处理：先 `create_background_task`，再 `create_task_plan`，再 `append_task_event`，有产物就 `record_task_artifact`，到点后 `summarize_background_task` 或 `get_task_handoff`。"
                    "如果任务会启动一个长时间运行的实验、训练、推理或后台服务，优先用 `start_managed_process` 而不是普通 `start_process`，并配合 `get_managed_process`、`list_managed_processes`、`note_managed_process`、`wait_for_process` 或 `create_background_task` 长期监视；未经用户明确要求，不要主动结束这类进程。"
                    "如果任务需要麦克风录音，可直接用 `run_shell` 或 `run_cmd` 调用 `src\\allcanuse_mcp\\tools\\micrecording.exe`；先无参数看示例，再正式带 `-t`、`-o` 参数执行。"
                    "如果工具已经足够，不要额外安装同类依赖；只有在工具明确提示缺依赖且当前任务确实需要时，才安装最小必需依赖。"
                    f"当前任务：{task}"
                ),
            }
        ]

    @mcp.prompt(
        name="duty_shift_operator",
        title="值班与交接提示",
        description="指导模型在长期等待、用户离线、断线重连和跨会话交接场景下合理使用值班工具。",
    )
    def duty_shift_operator(task: str, situation: str = "") -> list[dict]:
        situation_hint = f"当前场景：{situation}。" if situation else ""
        time_hint = render_runtime_context_text()
        return [
            {
                "role": "user",
                "content": (
                    f"当前时间上下文：{time_hint}"
                    "你正在处理一个可能需要值班、等待、托管或交接的任务。"
                    "值班工具不是装饰，而是你在用户离线、会话中断、等待时间较长时继续推进任务的主要手段。"
                    "如果用户要求你在接下来一小时内自己做事、自己盯、自己等，优先把任务建立成后台任务，并把计划、事件、产物、交接摘要一次写齐。"
                    "先判断场景：如果只是几秒到几十秒的短等待，并且你会在当前回复里继续处理，优先用 `wait` 或 `wait_until`；"
                    "如果等待对象很明确，优先用 `wait_for_file`、`wait_for_process`、`wait_for_port`、`wait_for_http`、`wait_for_window`、`wait_for_desktop_change`；"
                    "如果用户会离开、睡觉、稍后回来，或者任务可能跨会话持续较久，优先立刻用 `create_background_task` 托管，不要只停在口头等待。"
                    "后台任务创建后，尽早补 `create_task_plan`、`append_task_event`、`record_task_artifact`，让后续接手时能看懂。"
                    "如果任务提前完成，不要继续空等到原定时间；先补总结和交接，然后根据需要继续下一个相关动作。"
                    "如果当前必须等用户决定，优先用 `mark_task_waiting_for_user` 把问题写清楚；如果只是等外部条件成熟，可用 `mark_task_waiting_for_condition` 或直接继续轮询。"
                    "重新接手旧任务、断线恢复、跨模型交接时，优先用 `get_task_handoff`，必要时再读 `get_background_task` 或 `summarize_background_task`。"
                    "典型场景：盯服务恢复用 `wait_http` 或后台 `wait_http`；盯安装器或弹窗用 `wait_window` 或 `wait_desktop_change`；盯构建产物用 `wait_file`。"
                    "不要因为用户暂时不在线就停在原地，只要能条件化，就应托管给值班工具继续推进。"
                    "一个可执行模板：先建后台任务，再创建 3 到 6 个步骤计划，再记录首条事件，再登记产物，再在到点前后用 `get_scheduler_time`、`get_background_task`、`summarize_background_task`、`get_task_handoff` 做收口。"
                    f"{situation_hint}"
                    f"当前任务：{task}"
                ),
            }
        ]

    @mcp.prompt(
        name="web_research_operator",
        title="网页研究提示",
        description="指导模型如何组合网页正文、链接、元素和下载工具完成网页阅读或资料抓取。",
    )
    def web_research_operator(task: str, url: str = "") -> list[dict]:
        url_hint = f"目标网页：{url}。" if url else ""
        time_hint = render_runtime_context_text()
        return [
            {
                "role": "user",
                "content": (
                    f"当前时间上下文：{time_hint}"
                    "你正在执行网页阅读或网页资料抓取任务。"
                    "工具就是你的浏览与抓取能力，应主动使用。"
                    "推荐顺序：先用 `trace_http_redirects`、`fetch_webpage_text` 或 `webpage_to_markdown` 读取当前页；"
                    "需要先判断页面性质时，用 `extract_webpage_metadata` 看标题、canonical、meta 和 JSON-LD；"
                    "再用 `extract_links_from_webpage` 找文档入口、章节链接、详情页、下载链接、上一篇/下一篇、跳转链接；"
                    "如果当前页明显只是目录页、导航页、列表页、索引页、搜索结果页或文档首页，不要停在这一页，而要继续进入其中最相关的站内链接。"
                    "如果需要一口气沿站内继续抓多页，优先用 `crawl_webpages`，而不是手工重复一页页调用。"
                    "阅读网页时不要只看目录项标题或链接文字，应该继续点进真正有正文的内容页。"
                    "示例一：如果用户让你读一个文档首页，先 `trace_http_redirects`，再 `extract_webpage_metadata`，再 `fetch_webpage_text`，如果发现它只是目录页，就 `extract_links_from_webpage` 或 `crawl_webpages` 继续抓章节页。"
                    "示例二：如果用户让你找下载附件，先 `fetch_webpage_text` 判断页面作用，再 `extract_links_from_webpage(href_filter='.pdf' 或 '.zip')` 找附件入口，必要时再 `download_file`。"
                    "示例三：如果用户让你收集某个帮助中心内容，不要只读首页摘要，应继续沿 FAQ、guide、manual、install、reference 这类链接深入。"
                    "需要精确抓取标题、描述、文章区块、特定链接时，再用 `extract_webpage_elements`。"
                    "如果需要保存文件，再用 `download_file`。"
                    "网络较慢或页面较大时，主动调大 `timeout_ms` 或 `max_text_chars`。"
                    "如果任务目标还没满足，就继续沿相关链接探索更多页面，而不是过早停止。"
                    "不要只凭 URL 猜内容，先读网页再下结论。"
                    f"{url_hint}"
                    f"当前任务：{task}"
                ),
            }
        ]

    @mcp.prompt(
        name="code_fix_operator",
        title="代码修复提示",
        description="指导模型如何组合文件搜索、读取、修改和验证工具完成代码修复或开发任务。",
    )
    def code_fix_operator(task: str, root: str = "") -> list[dict]:
        root_hint = f"优先检查目录：{root}。" if root else ""
        time_hint = render_runtime_context_text()
        return [
            {
                "role": "user",
                "content": (
                    f"当前时间上下文：{time_hint}"
                    "你正在执行代码修复或开发任务。"
                    "工具就是你的读代码、改代码、验证代码的能力，应主动使用。"
                    "推荐顺序：先用 `list_tree`、`find_files`、`search_text`、`read_file` 获取上下文；"
                    "再用 `patch_lines`、`replace_text`、`write_file`、`write_json_file` 做修改；"
                    "修改后用 `run_shell`、`run_cmd` 或 `run_powershell` 执行验证。"
                    "不要跳过读取上下文直接盲改；不要只给修复建议而不动手。"
                    "面对大文件或长代码文件时，先 `search_text` 定位，再用 `read_file(start_line=..., end_line=...)` 分段读取，优先每段 50 到 200 行。"
                    "如果第一段上下文不够，再围绕命中位置继续扩读，不要默认整文件通读。"
                    "小范围改动优先精确修改工具，只有在必要时才整体重写。"
                    "修改前先读局部上下文，修改后再回读目标片段确认结果。"
                    f"{root_hint}"
                    f"当前任务：{task}"
                ),
            }
        ]

    @mcp.prompt(
        name="network_diagnostics_operator",
        title="网络排查提示",
        description="指导模型如何组合网络配置、解析、连通性、HTTP 和端口工具完成网络排查。",
    )
    def network_diagnostics_operator(task: str, target: str = "") -> list[dict]:
        target_hint = f"重点目标：{target}。" if target else ""
        time_hint = render_runtime_context_text()
        return [
            {
                "role": "user",
                "content": (
                    f"当前时间上下文：{time_hint}"
                    "你正在执行网络排查任务。"
                    "工具就是你的观测和诊断能力，应主动分层排查。"
                    "推荐顺序：先用 `get_network_config` 和 `list_network_adapters` 看本机网络状态；"
                    "再用 `dns_lookup` 看解析；"
                    "再用 `ping_host` 看主机可达；"
                    "再用 `tcp_connect` 看端口可达；"
                    "最后用 `http_request` 看应用层接口是否正常。"
                    "如果要查本机监听或端口占用，再用 `list_listening_ports` 或 `find_port_process`。"
                    "如果目标是海外网络，或者 `git`、`pip`、`npm`、`apt` 等联网动作因超时、连接失败、TLS 握手失败而受阻，不要只报失败。先检查本机是否已有代理：看 `list_listening_ports` / `find_port_process` 是否存在 `7890`、`7897`、`46464` 等常见代理端口，再看 `list_processes` 是否存在 `v2rayN`、`Clash for Windows`、`clash`、`clash-core-service` 等进程，必要时再看 `get_env` 里的代理环境变量。"
                    "如果已经发现代理存在，就直接通过代理重试原任务；如果没有发现，或者代理重试后仍失败，再询问用户是否已开启代理软件，并请用户协助打开。"
                    "不要把解析、主机、端口、HTTP 混在一起猜，应按层逐步验证。"
                    "网络工具默认要主动考虑 `timeout_ms`。"
                    f"{target_hint}"
                    f"当前任务：{task}"
                ),
            }
        ]

    return mcp
