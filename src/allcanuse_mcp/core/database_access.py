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


def _cursor_column_names(description: Any) -> list[str]:
    columns: list[str] = []
    for column in description or []:
        name = getattr(column, "name", None)
        if name is None:
            try:
                name = column[0]
            except Exception:
                name = str(column)
        columns.append(str(name))
    return columns


def _sqlite_read_query(connection: sqlite3.Connection, query: str, params: list[Any] | tuple[Any, ...] | None, limit: int) -> dict[str, Any]:
    connection.execute("PRAGMA query_only = ON")
    cursor = connection.cursor()
    cursor.execute(query, params or [])
    if cursor.description is None:
        return {"row_count": 0, "columns": [], "rows": []}
    data = _rows_from_cursor(cursor, limit)
    return {
        "row_count": len(data["rows"]),
        "columns": data["columns"],
        "rows": data["rows"],
    }


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

    attempts: list[dict[str, Any]] = []
    try:
        uri = f"file:{path.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        try:
            data = _sqlite_read_query(connection, query, params, limit)
            attempts.append({"backend": "sqlite-uri-readonly", "ok": True})
            return {
                "ok": True,
                "backend": "sqlite-uri-readonly",
                "path": str(path),
                "attempts": attempts,
                **data,
            }
        finally:
            connection.close()
    except sqlite3.Error as exc:
        attempts.append({"backend": "sqlite-uri-readonly", "ok": False, "error": str(exc)})

    try:
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
        data = _sqlite_read_query(connection, query, params, limit)
        attempts.append({"backend": "sqlite-direct-readonly-transaction", "ok": True})
        return {
            "ok": True,
            "backend": "sqlite-direct-readonly-transaction",
            "path": str(path),
            "attempts": attempts,
            **data,
        }
    except sqlite3.Error as exc:
        attempts.append({"backend": "sqlite-direct-readonly-transaction", "ok": False, "error": str(exc)})
        return {"ok": False, "error": str(exc), "path": str(path), "attempts": attempts}
    finally:
        try:
            connection.close()
        except Exception:
            pass


def _extract_postgresql_with_psycopg(
    dsn: str,
    query: str,
    params: list[Any] | tuple[Any, ...] | None,
    limit: int,
) -> dict[str, Any]:
    import psycopg

    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            if cursor.description is None:
                return {"row_count": 0, "columns": [], "rows": []}
            columns = _cursor_column_names(cursor.description)
            rows = cursor.fetchmany(max(1, limit))
            return {
                "columns": columns,
                "row_count": len(rows),
                "rows": [dict(zip(columns, row, strict=False)) for row in rows],
            }


def _extract_postgresql_with_psycopg2(
    dsn: str,
    query: str,
    params: list[Any] | tuple[Any, ...] | None,
    limit: int,
) -> dict[str, Any]:
    import psycopg2

    connection = psycopg2.connect(dsn)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            if cursor.description is None:
                return {"row_count": 0, "columns": [], "rows": []}
            columns = _cursor_column_names(cursor.description)
            rows = cursor.fetchmany(max(1, limit))
            return {
                "columns": columns,
                "row_count": len(rows),
                "rows": [dict(zip(columns, row, strict=False)) for row in rows],
            }
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

    attempts: list[dict[str, Any]] = []
    for backend, extractor in (
        ("psycopg", _extract_postgresql_with_psycopg),
        ("psycopg2", _extract_postgresql_with_psycopg2),
    ):
        try:
            data = extractor(dsn, query, params, limit)
        except Exception as exc:
            attempts.append({"backend": backend, "ok": False, "error": str(exc)})
            continue
        attempts.append({"backend": backend, "ok": True})
        return {"ok": True, "backend": backend, "attempts": attempts, **data}

    error = attempts[-1]["error"] if attempts else "No PostgreSQL backend was available."
    return {"ok": False, "error": error, "attempts": attempts}


def _mysql_connect_kwargs(dsn: str | dict[str, Any]) -> dict[str, Any]:
    return json.loads(dsn) if isinstance(dsn, str) else dict(dsn)


def _extract_mysql_with_connector(
    dsn: str | dict[str, Any],
    query: str,
    params: list[Any] | tuple[Any, ...] | None,
    limit: int,
) -> dict[str, Any]:
    import mysql.connector

    connection = mysql.connector.connect(**_mysql_connect_kwargs(dsn))
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, params or [])
        rows = cursor.fetchmany(max(1, limit))
        return {
            "columns": list(rows[0].keys()) if rows else _cursor_column_names(getattr(cursor, "description", None)),
            "row_count": len(rows),
            "rows": rows,
        }
    finally:
        cursor.close()
        connection.close()


def _extract_mysql_with_pymysql(
    dsn: str | dict[str, Any],
    query: str,
    params: list[Any] | tuple[Any, ...] | None,
    limit: int,
) -> dict[str, Any]:
    import pymysql
    import pymysql.cursors

    connection = pymysql.connect(**_mysql_connect_kwargs(dsn), cursorclass=pymysql.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            rows = cursor.fetchmany(max(1, limit))
            return {
                "columns": list(rows[0].keys()) if rows else _cursor_column_names(getattr(cursor, "description", None)),
                "row_count": len(rows),
                "rows": rows,
            }
    finally:
        connection.close()


def _extract_mysql_with_mysqldb(
    dsn: str | dict[str, Any],
    query: str,
    params: list[Any] | tuple[Any, ...] | None,
    limit: int,
) -> dict[str, Any]:
    import MySQLdb
    import MySQLdb.cursors

    connection = MySQLdb.connect(**_mysql_connect_kwargs(dsn), cursorclass=MySQLdb.cursors.DictCursor)
    try:
        with connection.cursor() as cursor:
            cursor.execute(query, params or [])
            rows = cursor.fetchmany(max(1, limit))
            return {
                "columns": list(rows[0].keys()) if rows else _cursor_column_names(getattr(cursor, "description", None)),
                "row_count": len(rows),
                "rows": rows,
            }
    finally:
        connection.close()


def extract_mysql_content(
    dsn: str | dict[str, Any],
    query: str,
    *,
    limit: int = 1000,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> dict[str, Any]:
    if not _is_read_only_query(query):
        return {"ok": False, "error": "Only read-only database extraction queries are allowed."}

    attempts: list[dict[str, Any]] = []
    for backend, extractor in (
        ("mysql.connector", _extract_mysql_with_connector),
        ("pymysql", _extract_mysql_with_pymysql),
        ("MySQLdb", _extract_mysql_with_mysqldb),
    ):
        try:
            data = extractor(dsn, query, params, limit)
        except Exception as exc:
            attempts.append({"backend": backend, "ok": False, "error": str(exc)})
            continue
        attempts.append({"backend": backend, "ok": True})
        return {"ok": True, "backend": backend, "attempts": attempts, **data}

    error = attempts[-1]["error"] if attempts else "No MySQL backend was available."
    return {"ok": False, "error": error, "attempts": attempts}
