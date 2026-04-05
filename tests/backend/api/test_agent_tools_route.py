from __future__ import annotations

import pytest

from backend.api.schemas import (
    AgentCommandRequest,
    AgentListRequest,
    AgentReadRequest,
    AgentSearchRequest,
    AgentWriteRequest,
)
import backend.api.routes.agent_tools as agent_tools_mod
from backend.agent.host_tool_runtime import CommandResult, ReadResult, SearchMatch, SearchResult, WriteResult


@pytest.mark.asyncio
async def test_agent_tools_manifest(monkeypatch):
    monkeypatch.setattr(
        agent_tools_mod.tools,
        "manifest",
        lambda: {
            "enabled": True,
            "workspace_root": "D:/Projects/Jarvin",
            "commands": ["/tool help"],
            "allowed_commands": ["rg ..."],
            "writes_enabled": True,
            "commands_enabled": True,
        },
        raising=True,
    )

    resp = await agent_tools_mod.agent_tools_manifest()
    assert resp.enabled is True
    assert resp.commands == ["/tool help"]


@pytest.mark.asyncio
async def test_agent_tools_list(monkeypatch):
    monkeypatch.setattr(agent_tools_mod.tools, "list_directory", lambda path, max_entries=200: ["backend/", "README.md"], raising=True)

    resp = await agent_tools_mod.agent_tools_list(AgentListRequest(path="."))
    assert resp.path == "."
    assert resp.entries == ["backend/", "README.md"]


@pytest.mark.asyncio
async def test_agent_tools_search(monkeypatch):
    monkeypatch.setattr(
        agent_tools_mod.tools,
        "search_workspace",
        lambda query, path=".", glob=None, max_results=None: SearchResult(
            query=query,
            matches=[SearchMatch(path="backend/api/app.py", line=12, text="include_router(agent_tools_router)")],
            truncated=False,
        ),
        raising=True,
    )

    resp = await agent_tools_mod.agent_tools_search(AgentSearchRequest(query="agent_tools_router"))
    assert resp.query == "agent_tools_router"
    assert resp.matches[0].path == "backend/api/app.py"


@pytest.mark.asyncio
async def test_agent_tools_read(monkeypatch):
    monkeypatch.setattr(
        agent_tools_mod.tools,
        "read_file",
        lambda path, start_line=1, end_line=None: ReadResult(
            path=path,
            start_line=start_line,
            end_line=end_line or start_line,
            text="1: hello",
            truncated=False,
        ),
        raising=True,
    )

    resp = await agent_tools_mod.agent_tools_read(AgentReadRequest(path="README.md"))
    assert resp.path == "README.md"
    assert resp.text == "1: hello"


@pytest.mark.asyncio
async def test_agent_tools_write(monkeypatch):
    monkeypatch.setattr(
        agent_tools_mod.tools,
        "write_file",
        lambda path, content, append=False: WriteResult(path=path, bytes_written=len(content.encode("utf-8")), append=append),
        raising=True,
    )

    resp = await agent_tools_mod.agent_tools_write(AgentWriteRequest(path="notes.txt", content="hello"))
    assert resp.path == "notes.txt"
    assert resp.bytes_written == 5


@pytest.mark.asyncio
async def test_agent_tools_run(monkeypatch):
    monkeypatch.setattr(
        agent_tools_mod.tools,
        "run_safe_command",
        lambda command: CommandResult(command=command, returncode=0, stdout="ok", stderr="", timed_out=False),
        raising=True,
    )

    resp = await agent_tools_mod.agent_tools_run(AgentCommandRequest(command="git status"))
    assert resp.command == "git status"
    assert resp.stdout == "ok"

