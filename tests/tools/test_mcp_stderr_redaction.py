"""Fixture-only regression for the stdio MCP stderr write boundary."""

from __future__ import annotations

import os
import time

from tools import mcp_tool


def test_mcp_stderr_pipe_scrubs_before_append(tmp_path, monkeypatch):
    fixture = "fixture-mcp-query-value"
    raw_path = tmp_path / "old-direct-write.log"
    raw_path.write_text(
        f"request=/rpc?apiKey={fixture}&transport=stdio\n",
        encoding="utf-8",
    )
    assert fixture in raw_path.read_text(encoding="utf-8")

    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setattr(mcp_tool, "_mcp_stderr_log_fh", None)

    sink = mcp_tool._get_mcp_stderr_log()
    assert sink.fileno() >= 0
    os.write(
        sink.fileno(),
        f"request=/rpc?apiKey={fixture}&transport=stdio\n".encode(),
    )

    log_path = tmp_path / "logs" / "mcp-stderr.log"
    deadline = time.monotonic() + 2.0
    contents = ""
    while time.monotonic() < deadline:
        if log_path.exists():
            contents = log_path.read_text(encoding="utf-8")
            if "transport=stdio" in contents:
                break
        time.sleep(0.01)

    assert fixture not in contents
    assert "request=/rpc?apiKey=***&transport=stdio" in contents
