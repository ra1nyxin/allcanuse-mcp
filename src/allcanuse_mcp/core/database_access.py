from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any


READ_ONLY_QUERY_RE = re.compile(r"^\s*(?:select|with|pragma|show|describe|desc|explain)\b", re.IGNORECASE | re.DOTALL)


def _is_read_only_query(query: str) -> bool:
    return bool(READ_ONLY_QUERY_RE.search(query or ""))


def _rows_from_cursor(cursor: sqlite3.Cursor, limit: int) -> dict[str, Any]:
    columns = [column[0] for column in cursor.description or []]
    rows = cursor.fetchmany(max(1, limit))
    records = [dict(zip(columns, row, strict=False)) for row in rows]
    return {"columns": columns, "rows": records}


def extract_sqlite_content(
    database_path: str,
    query: str,
    *,
    limit: int = 1000,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    if not _is_read_only_query(query):
        return {"ok": False, "error": "Only read-only database extraction queries are allowed."}
    path = Path(database_path).expanduser().resolve()
    if not path.exists():
        return {"ok": False, "error": f"SQLite database not found: {path}"}

    try:
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc)}

    try:
        cursor = connection.cursor()
        cursor.execute(query, params or [])
        if cursor.description is None:
            return {"ok": True, "path": str(path), "row_count": 0, "columns": [], "rows": []}
        data = _rows_from_cursor(cursor, limit)
        return {
            "ok": True,
            "path": str(path),
            "row_count": len(data["rows"]),
            "columns": data["columns"],
            "rows": data["rows"],
        }
    except sqlite3.Error as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}
    finally:
        connection.close()


def extract_postgresql_content(
    dsn: str,
    query: str,
    *,
    limit: int = 1000,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    if not _is_read_only_query(query):
        return {"ok": False, "error": "Only read-only database extraction queries are allowed."}
    try:
        import psycopg
    except ImportError:
        return {"ok": False, "error": "psycopg is not installed."}

    try:
        with psycopg.connect(dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or [])
                if cursor.description is None:
                    return {"ok": True, "row_count": 0, "columns": [], "rows": []}
                columns = [column.name for column in cursor.description]
                rows = cursor.fetchmany(max(1, limit))
                return {
                    "ok": True,
                    "columns": columns,
                    "row_count": len(rows),
                    "rows": [dict(zip(columns, row, strict=False)) for row in rows],
                }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def extract_mysql_content(
    dsn: str | dict[str, Any],
    query: str,
    *,
    limit: int = 1000,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    if not _is_read_only_query(query):
        return {"ok": False, "error": "Only read-only database extraction queries are allowed."}
    try:
        import mysql.connector
    except ImportError:
        return {"ok": False, "error": "mysql-connector-python is not installed."}

    try:
        connect_kwargs = json.loads(dsn) if isinstance(dsn, str) else dict(dsn)
        connection = mysql.connector.connect(**connect_kwargs)
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params or [])
        rows = cursor.fetchmany(max(1, limit))
        return {
            "ok": True,
            "columns": list(rows[0].keys()) if rows else [],
            "row_count": len(rows),
            "rows": rows,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            connection.close()
        except Exception:
            pass
