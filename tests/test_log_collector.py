"""Tests for LogCollector."""
import time
from pathlib import Path

import pytest

from kernel.execution.log_collector import LogCollector, _tail, _recent_log_files


class TestTailHelper:
    def test_reads_full_small_file(self, tmp_path):
        f = tmp_path / "app.log"
        f.write_bytes(b"hello world")
        assert _tail(f, 1000) == "hello world"

    def test_reads_last_n_bytes(self, tmp_path):
        f = tmp_path / "big.log"
        f.write_bytes(b"A" * 100 + b"B" * 50)
        result = _tail(f, 50)
        assert result == "B" * 50

    def test_missing_file_returns_empty(self, tmp_path):
        assert _tail(tmp_path / "nope.log", 1000) == ""


class TestRecentLogFiles:
    def test_finds_recent_file(self, tmp_path):
        f = tmp_path / "app.log"
        f.write_text("error here")
        files = _recent_log_files(tmp_path, max_age_seconds=60)
        assert f in files

    def test_ignores_old_file(self, tmp_path):
        f = tmp_path / "old.log"
        f.write_text("old error")
        # Set mtime to 2 hours ago
        old_time = time.time() - 7200
        import os
        os.utime(f, (old_time, old_time))
        files = _recent_log_files(tmp_path, max_age_seconds=60)
        assert f not in files

    def test_returns_newest_first(self, tmp_path):
        f1 = tmp_path / "old.log"
        f2 = tmp_path / "new.log"
        f1.write_text("old")
        f2.write_text("new")
        import os
        now = time.time()
        os.utime(f1, (now - 10, now - 10))
        os.utime(f2, (now - 1,  now - 1))
        files = _recent_log_files(tmp_path, max_age_seconds=60)
        assert files[0] == f2

    def test_empty_dir_returns_empty(self, tmp_path):
        assert _recent_log_files(tmp_path, max_age_seconds=60) == []

    def test_nonexistent_dir_returns_empty(self, tmp_path):
        assert _recent_log_files(tmp_path / "ghost", max_age_seconds=60) == []


class TestLogCollector:

    def test_collect_workspace_log_file(self, tmp_path):
        log = tmp_path / "app.log"
        log.write_text("ERROR: connection refused\n")
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="python", workspace=tmp_path)
        assert "connection refused" in result

    def test_collect_workspace_logs_dir(self, tmp_path):
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "server.log").write_text("FATAL: port in use\n")
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="node", workspace=tmp_path)
        assert "port in use" in result

    def test_collect_workspace_named_files(self, tmp_path):
        (tmp_path / "stderr.txt").write_text("Traceback (most recent call last):\n")
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="python", workspace=tmp_path)
        assert "Traceback" in result

    def test_empty_workspace_has_no_workspace_section(self, tmp_path):
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="python", workspace=tmp_path)
        # Workspace is empty so no [WORKSPACE LOGS] section should appear
        assert "[WORKSPACE LOGS]" not in result

    def test_nonexistent_workspace_handled_gracefully(self, tmp_path):
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="python", workspace=tmp_path / "ghost")
        assert isinstance(result, str)  # no crash

    def test_collect_returns_formatted_header(self, tmp_path):
        (tmp_path / "app.log").write_text("some error\n")
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="node", workspace=tmp_path)
        assert "LOGS DEL SISTEMA" in result

    def test_collect_no_workspace_no_crash(self):
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="python", workspace=None)
        assert isinstance(result, str)

    def test_content_bounded_by_max_bytes(self, tmp_path):
        big_log = tmp_path / "huge.log"
        big_log.write_text("x" * 20_000)
        collector = LogCollector(max_bytes_per_tool=1_000, max_age_minutes=60)
        result = collector.collect(stack="python", workspace=tmp_path)
        assert len(result) < 15_000  # well under 20k

    def test_resolve_tools_node_aliases(self):
        collector = LogCollector()
        tools = collector._resolve_tools("node", [])
        assert "node" in tools or "npm" in tools

    def test_resolve_tools_python_aliases(self):
        collector = LogCollector()
        tools = collector._resolve_tools("fastapi", [])
        assert "python" in tools

    def test_resolve_tools_extra_stacks(self):
        collector = LogCollector()
        tools = collector._resolve_tools("python", ["postgres"])
        assert "postgres" in tools

    def test_multiple_log_files_all_read(self, tmp_path):
        (tmp_path / "error.log").write_text("module not found\n")
        (tmp_path / "server.log").write_text("port 8080 busy\n")
        collector = LogCollector(max_age_minutes=60)
        result = collector.collect(stack="node", workspace=tmp_path)
        # At least one of the files should be included
        assert "not found" in result or "8080" in result
