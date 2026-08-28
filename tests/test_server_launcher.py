from __future__ import annotations

from pathlib import Path
import sys

import server


def _create_repo_venv_python(tmp_path: Path) -> Path:
    target = server._repo_venv_python(tmp_path / "server.py")
    target.parent.mkdir(parents=True)
    target.write_text("")
    return target


def test_launch_repo_venv_reexecs_when_current_python_is_not_repo_venv(tmp_path):
    target = _create_repo_venv_python(tmp_path)

    captured: dict[str, object] = {}

    def fake_run(cmd, env):
        captured["cmd"] = cmd
        captured["env"] = env
        return 17

    rc = server._launch_repo_venv_if_needed(
        script_path=tmp_path / "server.py",
        argv=["server.py"],
        current_executable=tmp_path / "system-python",
        environ={},
        run_cmd=fake_run,
    )

    assert rc == 17
    assert captured["cmd"] == [str(target), "server.py"]
    assert captured["env"]["JARVIN_ALREADY_REEXECED"] == "1"


def test_launch_repo_venv_skips_when_already_using_repo_venv(tmp_path):
    target = _create_repo_venv_python(tmp_path)

    rc = server._launch_repo_venv_if_needed(
        script_path=tmp_path / "server.py",
        argv=["server.py"],
        current_executable=target,
        environ={},
        run_cmd=lambda *args, **kwargs: 99,
    )

    assert rc is None


def test_launch_repo_venv_skips_when_repo_venv_is_missing(tmp_path):
    rc = server._launch_repo_venv_if_needed(
        script_path=tmp_path / "server.py",
        argv=["server.py"],
        current_executable=Path(sys.executable),
        environ={},
        run_cmd=lambda *args, **kwargs: 99,
    )

    assert rc is None


def test_launch_repo_venv_treats_keyboard_interrupt_as_clean_exit(tmp_path):
    _create_repo_venv_python(tmp_path)

    def interrupted_run(cmd, env):
        raise KeyboardInterrupt()

    rc = server._launch_repo_venv_if_needed(
        script_path=tmp_path / "server.py",
        argv=["server.py"],
        current_executable=tmp_path / "system-python",
        environ={},
        run_cmd=interrupted_run,
    )

    assert rc == 0
