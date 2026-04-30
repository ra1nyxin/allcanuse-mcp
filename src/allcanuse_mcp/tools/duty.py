from __future__ import annotations

from allcanuse_mcp.core.duty import get_background_task_manager
from allcanuse_mcp.core.duty import get_scheduler_time as get_scheduler_time_impl
from allcanuse_mcp.core.duty import wait as wait_impl
from allcanuse_mcp.core.duty import wait_for_background_task as wait_for_background_task_impl
from allcanuse_mcp.core.duty import wait_for_desktop_change as wait_for_desktop_change_impl
from allcanuse_mcp.core.duty import wait_for_file as wait_for_file_impl
from allcanuse_mcp.core.duty import wait_for_http as wait_for_http_impl
from allcanuse_mcp.core.duty import wait_for_port as wait_for_port_impl
from allcanuse_mcp.core.duty import wait_for_process as wait_for_process_impl
from allcanuse_mcp.core.duty import wait_for_window as wait_for_window_impl
from allcanuse_mcp.core.duty import wait_until as wait_until_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    manager = get_background_task_manager()

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait"])
    def wait(duration_ms: int, reason: str | None = None) -> dict:
        return wait_impl(duration_ms=duration_ms, reason=reason)

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_until"])
    def wait_until(timestamp: str, reason: str | None = None) -> dict:
        return wait_until_impl(timestamp=timestamp, reason=reason)

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_scheduler_time"])
    def get_scheduler_time() -> dict:
        return get_scheduler_time_impl(manager=manager)

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_for_file"])
    def wait_for_file(
        path: str,
        state: str = "exists",
        timeout_ms: int = 60_000,
        poll_interval_ms: int = 1000,
        min_size_bytes: int | None = None,
        text_contains: str | None = None,
        encoding: str = "utf-8",
    ) -> dict:
        return wait_for_file_impl(
            path=path,
            state=state,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
            min_size_bytes=min_size_bytes,
            text_contains=text_contains,
            encoding=encoding,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_for_process"])
    def wait_for_process(
        pid: int | None = None,
        name: str | None = None,
        state: str = "running",
        timeout_ms: int = 60_000,
        poll_interval_ms: int = 1000,
    ) -> dict:
        return wait_for_process_impl(
            pid=pid,
            name=name,
            state=state,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_for_port"])
    def wait_for_port(
        host: str,
        port: int,
        state: str = "open",
        timeout_ms: int = 60_000,
        poll_interval_ms: int = 1000,
        connect_timeout_ms: int = 1500,
    ) -> dict:
        return wait_for_port_impl(
            host=host,
            port=port,
            state=state,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
            connect_timeout_ms=connect_timeout_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_for_http"])
    def wait_for_http(
        url: str,
        expected_statuses: list[int] | None = None,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 60_000,
        poll_interval_ms: int = 2000,
        request_timeout_ms: int = 5000,
        text_contains: str | None = None,
    ) -> dict:
        return wait_for_http_impl(
            url=url,
            expected_statuses=expected_statuses,
            method=method,
            headers=headers,
            body=body,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
            request_timeout_ms=request_timeout_ms,
            text_contains=text_contains,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_for_window"])
    def wait_for_window(
        title_filter: str | None = None,
        hwnd: str | int | None = None,
        process_name: str | None = None,
        state: str = "appeared",
        include_invisible: bool = False,
        limit: int = 500,
        timeout_ms: int = 60_000,
        poll_interval_ms: int = 1000,
    ) -> dict:
        return wait_for_window_impl(
            title_filter=title_filter,
            hwnd=hwnd,
            process_name=process_name,
            state=state,
            include_invisible=include_invisible,
            limit=limit,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_for_desktop_change"])
    def wait_for_desktop_change(
        include_invisible: bool = False,
        limit: int = 50,
        baseline_snapshot: dict | None = None,
        timeout_ms: int = 60_000,
        poll_interval_ms: int = 1000,
    ) -> dict:
        return wait_for_desktop_change_impl(
            include_invisible=include_invisible,
            limit=limit,
            baseline_snapshot=baseline_snapshot,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["create_background_task"])
    def create_background_task(
        title: str,
        goal: str,
        task_type: str,
        condition: dict,
        poll_interval_ms: int = 5000,
        timeout_ms: int | None = None,
        priority: int = 50,
        owner: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
    ) -> dict:
        return manager.create_task(
            title=title,
            goal=goal,
            task_type=task_type,
            condition=condition,
            poll_interval_ms=poll_interval_ms,
            timeout_ms=timeout_ms,
            priority=priority,
            owner=owner,
            tags=tags,
            notes=notes,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_background_tasks"])
    def list_background_tasks(statuses: list[str] | None = None, limit: int = 100) -> dict:
        return manager.list_tasks(statuses=statuses, limit=limit)

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_background_task"])
    def get_background_task(task_id: str) -> dict:
        return manager.get_task(task_id)

    @mcp.tool(description=TOOL_DESCRIPTIONS["cancel_background_task"])
    def cancel_background_task(task_id: str, reason: str | None = None) -> dict:
        return manager.cancel_task(task_id, reason=reason)

    @mcp.tool(description=TOOL_DESCRIPTIONS["pause_background_task"])
    def pause_background_task(task_id: str, reason: str | None = None) -> dict:
        return manager.pause_task(task_id, reason=reason)

    @mcp.tool(description=TOOL_DESCRIPTIONS["resume_background_task"])
    def resume_background_task(task_id: str, reason: str | None = None) -> dict:
        return manager.resume_task(task_id, reason=reason)

    @mcp.tool(description=TOOL_DESCRIPTIONS["wait_for_background_task"])
    def wait_for_background_task(
        task_id: str,
        target_statuses: list[str] | None = None,
        timeout_ms: int = 60_000,
        poll_interval_ms: int = 1000,
    ) -> dict:
        return wait_for_background_task_impl(
            manager=manager,
            task_id=task_id,
            target_statuses=target_statuses,
            timeout_ms=timeout_ms,
            poll_interval_ms=poll_interval_ms,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["create_task_plan"])
    def create_task_plan(task_id: str, steps: list[str]) -> dict:
        return manager.create_plan(task_id, steps)

    @mcp.tool(description=TOOL_DESCRIPTIONS["update_task_step"])
    def update_task_step(task_id: str, step_index: int, status: str, note: str | None = None) -> dict:
        return manager.update_task_step(task_id, step_index, status, note=note)

    @mcp.tool(description=TOOL_DESCRIPTIONS["append_task_event"])
    def append_task_event(
        task_id: str,
        message: str,
        event_type: str = "info",
        data: dict | None = None,
    ) -> dict:
        return manager.append_task_event(task_id, event_type=event_type, message=message, data=data)

    @mcp.tool(description=TOOL_DESCRIPTIONS["record_task_artifact"])
    def record_task_artifact(task_id: str, path: str, description: str | None = None) -> dict:
        return manager.record_artifact(task_id, path=path, description=description)

    @mcp.tool(description=TOOL_DESCRIPTIONS["summarize_background_task"])
    def summarize_background_task(task_id: str, include_recent_events: int = 10) -> dict:
        return manager.summarize_task(task_id, include_recent_events=include_recent_events)

    @mcp.tool(description=TOOL_DESCRIPTIONS["get_task_handoff"])
    def get_task_handoff(task_id: str, include_recent_events: int = 10) -> dict:
        return manager.get_task_handoff(task_id, include_recent_events=include_recent_events)

    @mcp.tool(description=TOOL_DESCRIPTIONS["mark_task_waiting_for_user"])
    def mark_task_waiting_for_user(task_id: str, question: str) -> dict:
        return manager.mark_waiting_for_user(task_id, question)

    @mcp.tool(description=TOOL_DESCRIPTIONS["mark_task_waiting_for_condition"])
    def mark_task_waiting_for_condition(task_id: str, note: str) -> dict:
        return manager.mark_waiting_for_condition(task_id, note)
