from __future__ import annotations

from allcanuse_mcp.core.filesystem import build_tree
from allcanuse_mcp.core.filesystem import copy_path as copy_path_impl
from allcanuse_mcp.core.filesystem import delete_path as delete_path_impl
from allcanuse_mcp.core.filesystem import extract_archive as extract_archive_impl
from allcanuse_mcp.core.filesystem import find_files as find_files_impl
from allcanuse_mcp.core.filesystem import hash_file as hash_file_impl
from allcanuse_mcp.core.filesystem import list_desktop_files as list_desktop_files_impl
from allcanuse_mcp.core.filesystem import list_recent_files as list_recent_files_impl
from allcanuse_mcp.core.filesystem import mkdir_path as mkdir_path_impl
from allcanuse_mcp.core.filesystem import move_path as move_path_impl
from allcanuse_mcp.core.filesystem import patch_lines_in_file
from allcanuse_mcp.core.filesystem import read_binary_file as read_binary_file_impl
from allcanuse_mcp.core.filesystem import read_json_file as read_json_file_impl
from allcanuse_mcp.core.filesystem import read_text_file
from allcanuse_mcp.core.filesystem import replace_text_in_file
from allcanuse_mcp.core.filesystem import stat_path as stat_path_impl
from allcanuse_mcp.core.filesystem import search_text as search_text_impl
from allcanuse_mcp.core.filesystem import which_command as which_command_impl
from allcanuse_mcp.core.filesystem import write_binary_file as write_binary_file_impl
from allcanuse_mcp.core.filesystem import write_json_file as write_json_file_impl
from allcanuse_mcp.core.filesystem import write_text_file
from allcanuse_mcp.core.filesystem import zip_paths as zip_paths_impl
from allcanuse_mcp.descriptions import TOOL_DESCRIPTIONS


def register(mcp) -> None:
    @mcp.tool(description=TOOL_DESCRIPTIONS["list_tree"])
    def list_tree(
        root: str = ".",
        max_depth: int = 3,
        max_entries: int = 400,
        include_files: bool = True,
        include_dirs: bool = True,
        show_hidden: bool = False,
    ) -> dict:
        return build_tree(
            root,
            max_depth=max_depth,
            max_entries=max_entries,
            include_files=include_files,
            include_dirs=include_dirs,
            show_hidden=show_hidden,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["read_file"])
    def read_file(
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        encoding: str = "utf-8",
    ) -> dict:
        return read_text_file(path, encoding=encoding, start_line=start_line, end_line=end_line)

    @mcp.tool(description=TOOL_DESCRIPTIONS["write_file"])
    def write_file(
        path: str,
        content: str,
        encoding: str = "utf-8",
        mode: str = "overwrite",
        create_dirs: bool = True,
    ) -> dict:
        if mode not in {"overwrite", "append"}:
            raise ValueError("mode must be overwrite or append")
        return write_text_file(path, content, encoding=encoding, mode=mode, create_dirs=create_dirs)

    @mcp.tool(description=TOOL_DESCRIPTIONS["patch_lines"])
    def patch_lines(
        path: str,
        start_line: int,
        end_line: int,
        new_text: str,
        encoding: str = "utf-8",
    ) -> dict:
        return patch_lines_in_file(
            path,
            start_line=start_line,
            end_line=end_line,
            new_text=new_text,
            encoding=encoding,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["replace_text"])
    def replace_text(
        path: str,
        old_text: str,
        new_text: str,
        count: int = 0,
        encoding: str = "utf-8",
    ) -> dict:
        return replace_text_in_file(
            path,
            old_text=old_text,
            new_text=new_text,
            count=count,
            encoding=encoding,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["mkdir"])
    def mkdir(path: str, parents: bool = True, exist_ok: bool = True) -> dict:
        return mkdir_path_impl(path, parents=parents, exist_ok=exist_ok)

    @mcp.tool(description=TOOL_DESCRIPTIONS["move_path"])
    def move_path(source: str, destination: str, overwrite: bool = False) -> dict:
        return move_path_impl(source, destination, overwrite=overwrite)

    @mcp.tool(description=TOOL_DESCRIPTIONS["delete_path"])
    def delete_path(path: str, recursive: bool = False, missing_ok: bool = False) -> dict:
        return delete_path_impl(path, recursive=recursive, missing_ok=missing_ok)

    @mcp.tool(description=TOOL_DESCRIPTIONS["zip_paths"])
    def zip_paths(paths: list[str], destination: str, archive_type: str = "zip") -> dict:
        return zip_paths_impl(paths, destination, archive_type=archive_type)

    @mcp.tool(description=TOOL_DESCRIPTIONS["extract_archive"])
    def extract_archive(archive_path: str, destination_dir: str, overwrite: bool = False) -> dict:
        return extract_archive_impl(archive_path, destination_dir, overwrite=overwrite)

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_desktop_files"])
    def list_desktop_files() -> dict:
        return list_desktop_files_impl()

    @mcp.tool(description=TOOL_DESCRIPTIONS["find_files"])
    def find_files(
        root: str = ".",
        pattern: str = "*",
        max_depth: int = 5,
        max_results: int = 200,
        include_hidden: bool = False,
    ) -> dict:
        return find_files_impl(
            root,
            pattern=pattern,
            max_depth=max_depth,
            max_results=max_results,
            include_hidden=include_hidden,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["search_text"])
    def search_text(
        root: str,
        query: str,
        use_regex: bool = False,
        case_sensitive: bool = False,
        file_pattern: str = "*",
        max_results: int = 200,
        max_file_size_bytes: int = 1_000_000,
        include_hidden: bool = False,
    ) -> dict:
        return search_text_impl(
            root,
            query=query,
            use_regex=use_regex,
            case_sensitive=case_sensitive,
            file_pattern=file_pattern,
            max_results=max_results,
            max_file_size_bytes=max_file_size_bytes,
            include_hidden=include_hidden,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["stat_path"])
    def stat_path(path: str) -> dict:
        return stat_path_impl(path)

    @mcp.tool(description=TOOL_DESCRIPTIONS["copy_path"])
    def copy_path(source: str, destination: str, overwrite: bool = False) -> dict:
        return copy_path_impl(source, destination, overwrite=overwrite)

    @mcp.tool(description=TOOL_DESCRIPTIONS["hash_file"])
    def hash_file(path: str, algorithm: str = "sha256") -> dict:
        return hash_file_impl(path, algorithm=algorithm)

    @mcp.tool(description=TOOL_DESCRIPTIONS["read_binary_file"])
    def read_binary_file(path: str, offset: int = 0, length: int = 4096, as_base64: bool = True) -> dict:
        return read_binary_file_impl(path, offset=offset, length=length, as_base64=as_base64)

    @mcp.tool(description=TOOL_DESCRIPTIONS["write_binary_file"])
    def write_binary_file(
        path: str,
        content: str,
        input_encoding: str = "base64",
        mode: str = "overwrite",
        create_dirs: bool = True,
    ) -> dict:
        return write_binary_file_impl(
            path,
            content,
            input_encoding=input_encoding,
            mode=mode,
            create_dirs=create_dirs,
        )

    @mcp.tool(description=TOOL_DESCRIPTIONS["list_recent_files"])
    def list_recent_files(root: str = ".", limit: int = 50) -> dict:
        return list_recent_files_impl(root, limit=limit)

    @mcp.tool(description=TOOL_DESCRIPTIONS["read_json_file"])
    def read_json_file(path: str) -> dict:
        return read_json_file_impl(path)

    @mcp.tool(description=TOOL_DESCRIPTIONS["write_json_file"])
    def write_json_file(path: str, data: object, indent: int = 2, ensure_ascii: bool = False) -> dict:
        return write_json_file_impl(path, data, indent=indent, ensure_ascii=ensure_ascii)

    @mcp.tool(description=TOOL_DESCRIPTIONS["which_command"])
    def which_command(name: str) -> dict:
        return which_command_impl(name)
