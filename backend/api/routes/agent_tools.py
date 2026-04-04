from __future__ import annotations

from fastapi import APIRouter

from backend.agent import tools
from backend.api.schemas import (
    AgentCommandRequest,
    AgentCommandResponse,
    AgentListRequest,
    AgentListResponse,
    AgentReadRequest,
    AgentReadResponse,
    AgentSearchMatch,
    AgentSearchRequest,
    AgentSearchResponse,
    AgentToolsManifestResponse,
    AgentWriteRequest,
    AgentWriteResponse,
    ErrorResponse,
)

router = APIRouter(tags=["agent-tools"])


@router.get("/agent/tools", response_model=AgentToolsManifestResponse | ErrorResponse)
async def agent_tools_manifest() -> AgentToolsManifestResponse | ErrorResponse:
    try:
        return AgentToolsManifestResponse(**tools.manifest())
    except Exception as exc:
        return ErrorResponse(error=str(exc))


@router.post("/agent/tools/list", response_model=AgentListResponse | ErrorResponse)
async def agent_tools_list(payload: AgentListRequest) -> AgentListResponse | ErrorResponse:
    try:
        entries = tools.list_directory(payload.path, max_entries=payload.max_entries or 200)
        return AgentListResponse(path=payload.path, entries=entries)
    except Exception as exc:
        return ErrorResponse(error=str(exc))


@router.post("/agent/tools/search", response_model=AgentSearchResponse | ErrorResponse)
async def agent_tools_search(payload: AgentSearchRequest) -> AgentSearchResponse | ErrorResponse:
    try:
        result = tools.search_workspace(
            payload.query,
            path=payload.path,
            glob=payload.glob,
            max_results=payload.max_results,
        )
        return AgentSearchResponse(
            query=result.query,
            matches=[AgentSearchMatch(path=item.path, line=item.line, text=item.text) for item in result.matches],
            truncated=result.truncated,
        )
    except Exception as exc:
        return ErrorResponse(error=str(exc))


@router.post("/agent/tools/read", response_model=AgentReadResponse | ErrorResponse)
async def agent_tools_read(payload: AgentReadRequest) -> AgentReadResponse | ErrorResponse:
    try:
        result = tools.read_file(payload.path, start_line=payload.start_line, end_line=payload.end_line)
        return AgentReadResponse(
            path=result.path,
            start_line=result.start_line,
            end_line=result.end_line,
            text=result.text,
            truncated=result.truncated,
        )
    except Exception as exc:
        return ErrorResponse(error=str(exc))


@router.post("/agent/tools/write", response_model=AgentWriteResponse | ErrorResponse)
async def agent_tools_write(payload: AgentWriteRequest) -> AgentWriteResponse | ErrorResponse:
    try:
        result = tools.write_file(payload.path, payload.content, append=payload.append)
        return AgentWriteResponse(path=result.path, bytes_written=result.bytes_written, append=result.append)
    except Exception as exc:
        return ErrorResponse(error=str(exc))


@router.post("/agent/tools/run", response_model=AgentCommandResponse | ErrorResponse)
async def agent_tools_run(payload: AgentCommandRequest) -> AgentCommandResponse | ErrorResponse:
    try:
        result = tools.run_safe_command(payload.command)
        return AgentCommandResponse(
            command=result.command,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
        )
    except Exception as exc:
        return ErrorResponse(error=str(exc))
