# server.py
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Callable, Mapping, Optional, Sequence
from urllib.parse import urlunparse


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
import gradio as gr
from fastapi.responses import RedirectResponse

import config as cfg
from backend.util.logging_setup import init_logging
from backend.api.app import create_app as create_fastapi_app
from ui.app import create_app as create_gradio_blocks


def _set_gradio_env() -> None:
    s = cfg.settings
    os.environ["GRADIO_USE_CDN"] = "true" if s.gradio_use_cdn else "false"
    os.environ["GRADIO_ANALYTICS_ENABLED"] = "true" if s.gradio_analytics_enabled else "false"


def build_app_with_ui():
    """
    Compose FastAPI + mount Gradio Blocks at configured path.
    Assumes Gradio env vars are already set by caller.
    """
    s = cfg.settings

    fastapi_app = create_fastapi_app()

    blocks = create_gradio_blocks()
    mount_path = s.gradio_mount_path.rstrip("/") or "/"
    gr.mount_gradio_app(app=fastapi_app, blocks=blocks, path=mount_path)

    if mount_path != "/":
        @fastapi_app.get("/")
        def _root_redirect():
            return RedirectResponse(url=mount_path, status_code=307)
    return fastapi_app


def _browser_url(host: str, port: int, path: str) -> str:
    client_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    netloc = f"{client_host}:{port}"
    p = path if path.startswith("/") else f"/{path}"
    return urlunparse(("http", netloc, p, "", "", ""))


def _open_browser_later(url: str, delay: float) -> None:
    def _worker():
        time.sleep(max(0.0, delay))
        try:
            # No-op in headless/CI environments
            webbrowser.open(url, new=2)
        except Exception:
            pass

    t = threading.Thread(target=_worker, name="OpenBrowser", daemon=True)
    t.start()


def main() -> int:
    s = cfg.settings
    init_logging(s.log_level)
    _set_gradio_env()  # set once here

    host = s.server_host
    port = int(s.server_port)
    mount_path = s.gradio_mount_path.rstrip("/") or "/"
    reload_flag = s.uvicorn_reload_windows if os.name == "nt" else s.uvicorn_reload_others

    # Build app first so we can stash a server reference in app.state
    app = build_app_with_ui()

    if s.gradio_auto_open:
        url = _browser_url(host, port, mount_path)
        _open_browser_later(url, delay=s.gradio_open_delay_sec)

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
