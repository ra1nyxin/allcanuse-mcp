from __future__ import annotations

import asyncio
import unittest

from allcanuse_mcp.server import create_server


class ServerToolTests(unittest.TestCase):
    def test_list_all_tools_contains_expected_entries(self) -> None:
        server = create_server()
        result = None
        for tool in server._tool_manager._tools.values():
            if tool.name == "list_all_tools":
                result = tool.fn(include_descriptions=False)
                break
        self.assertIsNotNone(result)
        names = [item["name"] for item in result["tools"]]
        self.assertIn("list_all_tools", names)
        self.assertIn("read_file", names)
        self.assertIn("tcp_connect", names)
        self.assertIn("wait", names)
        self.assertIn("wait_for_file", names)
        self.assertIn("wait_for_window", names)
        self.assertIn("wait_for_desktop_change", names)
        self.assertIn("create_background_task", names)
        self.assertIn("list_background_tasks", names)
        self.assertIn("summarize_background_task", names)
        self.assertIn("get_task_handoff", names)
        self.assertIn("http_head", names)
        self.assertIn("fetch_response_headers", names)
        self.assertIn("fetch_webpage_text", names)
        self.assertIn("extract_webpage_metadata", names)
        self.assertIn("crawl_webpages", names)
        self.assertIn("submit_web_form", names)
        self.assertIn("upload_file", names)
        self.assertIn("extract_links_from_webpage", names)
        self.assertIn("extract_webpage_elements", names)
        self.assertIn("websocket_connect", names)
        self.assertIn("scan_suspicious_files", names)
        self.assertIn("deploy_and_update_service", names)
        self.assertIn("extract_sqlite_content", names)
        self.assertIn("extract_postgresql_content", names)
        self.assertIn("extract_mysql_content", names)
        self.assertIn("audit_seo", names)
        self.assertIn("optimize_images_for_memory", names)
        self.assertIn("detect_c_toolchains", names)
        self.assertIn("compile_c_program", names)
        self.assertIn("check_c_syntax", names)
        self.assertIn("preprocess_c_source", names)
        self.assertIn("inspect_c_source", names)
        self.assertIn("scan_c_memory_risks", names)
        self.assertIn("scan_c_numeric_risks", names)
        self.assertIn("evaluate_c_math_expression", names)
        self.assertIn("generate_c_numeric_test_harness", names)
        self.assertIn("generate_c_math_utils_header", names)
        self.assertIn("generate_c_vector_math_header", names)
        self.assertIn("generate_c_lookup_table_header", names)
        self.assertIn("generate_c_polynomial_eval_header", names)
        self.assertIn("generate_c_matrix_math_header", names)
        self.assertIn("generate_c_statistics_header", names)
        self.assertIn("generate_c_fixed_point_header", names)
        self.assertIn("generate_c_build_files", names)
        self.assertIn("format_c_code", names)
        categories = {item["name"]: item["category"] for item in result["tools"]}
        self.assertEqual(categories["scan_suspicious_files"], "security")
        self.assertEqual(categories["deploy_and_update_service"], "deployment")
        self.assertEqual(categories["extract_sqlite_content"], "database")
        self.assertEqual(categories["compile_c_program"], "code")
        self.assertEqual(categories["audit_seo"], "seo")
        self.assertEqual(categories["optimize_images_for_memory"], "optimization")
        self.assertEqual(categories["scan_c_memory_risks"], "code")
        self.assertEqual(categories["scan_c_numeric_risks"], "code")
        self.assertEqual(categories["generate_c_vector_math_header"], "code")
        self.assertEqual(categories["generate_c_matrix_math_header"], "code")

    def test_quick_reference_resource_registered(self) -> None:
        server = create_server()
        resources = server._resource_manager._resources
        templates = server._resource_manager._templates

        index_resource = resources.get("resource://guides/index")
        self.assertIsNotNone(index_resource)
        index_content = asyncio.run(index_resource.read())
        self.assertIn("Guide 与 Prompt 索引", index_content)
        self.assertIn("resource://guides/tool-quick-reference", index_content)
        self.assertIn("multi_tool_executor", index_content)
        self.assertIn("resource://guides/workflows/duty-watch", index_content)
        self.assertIn("duty_shift_operator", index_content)

        direct_resource = resources.get("resource://guides/tool-quick-reference")
        self.assertIsNotNone(direct_resource)
        content = asyncio.run(direct_resource.read())
        self.assertIn("工具速查手册", content)
        self.assertIn("fetch_webpage_text", content)
        self.assertIn("run_shell", content)

        self.assertIn("resource://guides/tools/{tool_name}", templates)

    def test_workflow_resources_registered(self) -> None:
        server = create_server()
        resources = server._resource_manager._resources

        web = resources.get("resource://guides/workflows/web-research")
        code = resources.get("resource://guides/workflows/code-edit")
        desktop = resources.get("resource://guides/workflows/desktop-observation")
        network = resources.get("resource://guides/workflows/network-diagnostics")
        duty = resources.get("resource://guides/workflows/duty-watch")

        self.assertIsNotNone(web)
        self.assertIsNotNone(code)
        self.assertIsNotNone(desktop)
        self.assertIsNotNone(network)
        self.assertIsNotNone(duty)

        self.assertIn("fetch_webpage_text", asyncio.run(web.read()))
        self.assertIn("crawl_webpages", asyncio.run(web.read()))
        self.assertIn("patch_lines", asyncio.run(code.read()))
        self.assertIn("get_desktop_context", asyncio.run(desktop.read()))
        self.assertIn("tcp_connect", asyncio.run(network.read()))
        self.assertIn("get_task_handoff", asyncio.run(duty.read()))
        self.assertIn("一小时", asyncio.run(duty.read()))
        self.assertIn("get_scheduler_time", asyncio.run(duty.read()))

    def test_specialized_prompts_registered(self) -> None:
        server = create_server()
        prompts = server._prompt_manager._prompts

        self.assertIn("workspace_operator", prompts)
        self.assertIn("multi_tool_executor", prompts)
        self.assertIn("duty_shift_operator", prompts)
        self.assertIn("web_research_operator", prompts)
        self.assertIn("code_fix_operator", prompts)
        self.assertIn("network_diagnostics_operator", prompts)

        multi_tool = prompts["multi_tool_executor"].fn("修复项目中的错误")
        duty_prompt = prompts["duty_shift_operator"].fn("盯服务恢复后继续测试", "用户今晚不在线")
        web_prompt = prompts["web_research_operator"].fn("阅读这个网页", "https://example.com")
        code_prompt = prompts["code_fix_operator"].fn("修复登录逻辑", "src")
        network_prompt = prompts["network_diagnostics_operator"].fn("排查接口无法访问", "api.example.com:443")

        self.assertIn("主动使用多个相关工具推进", multi_tool[0]["content"])
        self.assertIn("create_background_task", duty_prompt[0]["content"])
        self.assertIn("get_task_handoff", duty_prompt[0]["content"])
        self.assertIn("fetch_webpage_text", web_prompt[0]["content"])
        self.assertIn("crawl_webpages", web_prompt[0]["content"])
        self.assertIn("不要停在这一页", web_prompt[0]["content"])
        self.assertIn("继续进入其中最相关的站内链接", web_prompt[0]["content"])
        self.assertIn("patch_lines", code_prompt[0]["content"])
        self.assertIn("tcp_connect", network_prompt[0]["content"])
        self.assertIn("7890", network_prompt[0]["content"])
        self.assertIn("list_listening_ports", network_prompt[0]["content"])
        self.assertIn("list_processes", network_prompt[0]["content"])
        self.assertIn("代理软件", network_prompt[0]["content"])
        self.assertIn("start_managed_process", multi_tool[0]["content"])
        self.assertIn("create_background_task", duty_prompt[0]["content"])
        self.assertIn("create_task_plan", duty_prompt[0]["content"])
        self.assertIn("get_task_handoff", duty_prompt[0]["content"])
        self.assertIn("一小时", duty_prompt[0]["content"])


if __name__ == "__main__":
    unittest.main()
