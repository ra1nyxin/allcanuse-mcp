from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from allcanuse_mcp.core.database_access import extract_mysql_content
from allcanuse_mcp.core.database_access import extract_postgresql_content
from allcanuse_mcp.core.database_access import extract_sqlite_content
from allcanuse_mcp.core.deployment import deploy_and_update_service


class DeploymentAndDatabaseTests(unittest.TestCase):
    def test_extract_sqlite_content_returns_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp, "sample.db")
            connection = sqlite3.connect(str(db_path))
            try:
                connection.execute("create table users (id integer primary key, name text)")
                connection.execute("insert into users (name) values (?)", ("alice",))
                connection.execute("insert into users (name) values (?)", ("bob",))
                connection.commit()
            finally:
                connection.close()

            result = extract_sqlite_content(str(db_path), "select id, name from users order by id", limit=10)
            blocked = extract_sqlite_content(str(db_path), "delete from users")

        self.assertTrue(result["ok"])
        self.assertEqual(result["columns"], ["id", "name"])
        self.assertEqual(result["backend"], "sqlite-uri-readonly")
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["rows"][0]["name"], "alice")
        self.assertFalse(blocked["ok"])
        self.assertIn("read-only", blocked["error"])

    def test_extract_sqlite_content_falls_back_to_direct_connection(self) -> None:
        real_connect = sqlite3.connect

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp, "sample.db")
            connection = real_connect(str(db_path))
            try:
                connection.execute("create table users (id integer primary key, name text)")
                connection.execute("insert into users (name) values (?)", ("alice",))
                connection.commit()
            finally:
                connection.close()

            def fake_connect(database, *args, **kwargs):
                if kwargs.get("uri"):
                    raise sqlite3.OperationalError("uri open failed")
                return real_connect(database, *args, **kwargs)

            with patch("allcanuse_mcp.core.database_access.sqlite3.connect", side_effect=fake_connect):
                result = extract_sqlite_content(str(db_path), "select name from users")

        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "sqlite-direct-readonly-transaction")
        self.assertEqual(result["attempts"][0]["backend"], "sqlite-uri-readonly")
        self.assertFalse(result["attempts"][0]["ok"])

    def test_extract_postgresql_content_falls_back_to_psycopg2(self) -> None:
        def fake_psycopg(*_args, **_kwargs):
            raise RuntimeError("psycopg unavailable")

        def fake_psycopg2(*_args, **_kwargs):
            return {"columns": ["name"], "row_count": 1, "rows": [{"name": "alice"}]}

        with patch("allcanuse_mcp.core.database_access._extract_postgresql_with_psycopg", side_effect=fake_psycopg), patch(
            "allcanuse_mcp.core.database_access._extract_postgresql_with_psycopg2",
            side_effect=fake_psycopg2,
        ):
            result = extract_postgresql_content("postgresql://example/db", "select name from users")

        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "psycopg2")
        self.assertEqual(result["attempts"][0]["backend"], "psycopg")
        self.assertFalse(result["attempts"][0]["ok"])

    def test_extract_mysql_content_falls_back_to_pymysql(self) -> None:
        def fake_connector(*_args, **_kwargs):
            raise RuntimeError("connector unavailable")

        def fake_pymysql(*_args, **_kwargs):
            return {"columns": ["name"], "row_count": 1, "rows": [{"name": "alice"}]}

        with patch("allcanuse_mcp.core.database_access._extract_mysql_with_connector", side_effect=fake_connector), patch(
            "allcanuse_mcp.core.database_access._extract_mysql_with_pymysql",
            side_effect=fake_pymysql,
        ):
            result = extract_mysql_content({"host": "127.0.0.1", "user": "root"}, "select name from users")

        self.assertTrue(result["ok"])
        self.assertEqual(result["backend"], "pymysql")
        self.assertEqual(result["attempts"][0]["backend"], "mysql.connector")
        self.assertFalse(result["attempts"][0]["ok"])

    def test_deploy_and_update_service_runs_expected_stages(self) -> None:
        calls: list[list[str]] = []

        def fake_which(name: str) -> str:
            return f"/usr/bin/{name}"

        def fake_run(command: list[str], *, timeout_ms: int = 300_000):
            calls.append(command)
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "project")
            source.mkdir()
            (source / "app.py").write_text("print('ok')\n", encoding="utf-8")

            with (
                patch("allcanuse_mcp.core.deployment._resolve_executable", side_effect=fake_which),
                patch("allcanuse_mcp.core.deployment._run_command_capture", side_effect=fake_run),
                patch(
                    "allcanuse_mcp.core.deployment.run_shell",
                    return_value={"ok": True, "stdout": "built", "stderr": "", "returncode": 0},
                ),
            ):
                result = deploy_and_update_service(
                    source_path=str(source),
                    remote_host="example.internal",
                    remote_user="deploy",
                    remote_path="/srv/app",
                    build_command="python -m py_compile app.py",
                    restart_command="systemctl restart app",
                    health_check_command="systemctl is-active app",
                    release_name="test-release",
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["release_name"], "test-release")
        self.assertEqual(result["remote_release_dir"], "/srv/app/releases/test-release")
        self.assertTrue(any(command[0].endswith("scp") for command in calls))
        self.assertTrue(any("systemctl restart app" in " ".join(command) for command in calls))
        self.assertTrue(any("systemctl is-active app" in " ".join(command) for command in calls))

    def test_deploy_and_update_service_falls_back_to_rsync_upload(self) -> None:
        calls: list[list[str]] = []

        def fake_which(name: str) -> str | None:
            if name == "scp":
                return None
            return f"/usr/bin/{name}"

        def fake_run(command: list[str], *, timeout_ms: int = 300_000):
            calls.append(command)
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp, "project")
            source.mkdir()
            (source / "app.py").write_text("print('ok')\n", encoding="utf-8")

            with (
                patch("allcanuse_mcp.core.deployment._resolve_executable", side_effect=fake_which),
                patch("allcanuse_mcp.core.deployment._run_command_capture", side_effect=fake_run),
            ):
                result = deploy_and_update_service(
                    source_path=str(source),
                    remote_host="example.internal",
                    remote_user="deploy",
                    remote_path="/srv/app",
                    release_name="test-release",
                )

        self.assertTrue(result["ok"])
        self.assertEqual(result["upload_result"]["backend"], "rsync")
        self.assertTrue(any(command[0].endswith("rsync") for command in calls))


if __name__ == "__main__":
    unittest.main()
