# server.py
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Mapping, Optional, Sequence


def _normalize_path(path: str | os.PathLike[str]) -> str:
    try:
        return os.path.normcase(str(Path(path).resolve(strict=False)))
    except Exception:
        return os.path.normcase(str(path))


def _repo_venv_python(script_path: str | os.PathLike[str] | None = None) -> Path:
    root = Path(script_path or __file__).resolve().parent
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def _launch_repo_venv_if_needed(
    *,
    script_path: str | os.PathLike[str] | None = None,
    argv: Sequence[str] | None = None,
    current_executable: str | os.PathLike[str] | None = None,
    environ: Mapping[str, str] | None = None,
    run_cmd: Callable[..., int] | None = None,
) -> Optional[int]:
    """
    If `server.py` is launched outside the repo venv, re-run it using the
    checked-in `.venv` interpreter so `python server.py` works as expected.
    """
    target = _repo_venv_python(script_path)
    if not target.exists():
        return None

    current = _normalize_path(current_executable or sys.executable)
    if current == _normalize_path(target):
        return None

    source_env = os.environ if environ is None else environ
    if source_env.get("JARVIN_ALREADY_REEXECED") == "1":
        return None

    cmd_runner = subprocess.call if run_cmd is None else run_cmd
    child_env = dict(source_env)
    child_env["JARVIN_ALREADY_REEXECED"] = "1"

    child_argv = list(argv or sys.argv)
    return int(cmd_runner([str(target), *child_argv], env=child_env))


_reexec_code = _launch_repo_venv_if_needed()
if _reexec_code is not None:
    raise SystemExit(_reexec_code)

import uvicorn

import config as cfg
from backend.util.logging_setup import init_logging
from backend.api.app import create_app as create_fastapi_app


def main() -> int:
    s = cfg.settings
    init_logging(s.log_level)

    host = s.server_host
    port = int(s.server_port)
    reload_flag = s.uvicorn_reload_windows if os.name == "nt" else s.uvicorn_reload_others

    app = create_fastapi_app()

    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        reload=reload_flag,
        log_level=s.log_level,
        access_log=s.uvicorn_access_log,
        timeout_graceful_shutdown=3,  # short, clean shutdown
        timeout_keep_alive=1,         # drop idle keep-alives quickly
    )
    server = uvicorn.Server(config)
    setattr(app.state, "uvicorn_server", server)

    try:
        server.run()
        return 0
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
