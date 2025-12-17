# audio/utils.py
from __future__ import annotations
import os
import sys
import contextlib


@contextlib.contextmanager
def suppress_alsa_warnings_if_linux():
    """
    On Linux, temporarily redirect stderr to /dev/null while opening PyAudio streams
    to suppress benign ALSA warnings. Guard against environments where fileno()
    is unavailable (e.g., some notebook/stdout captures).
    """
    if not sys.platform.startswith("linux"):
        yield
        return

    # Best-effort: if fileno() is unavailable, just yield without suppression.
    try:
        stderr_fileno = sys.stderr.fileno()
    except Exception:
        yield
        return

    with open(os.devnull, "w") as devnull:
        old_stderr = os.dup(stderr_fileno)
        try:
            os.dup2(devnull.fileno(), stderr_fileno)
            yield
        finally:
            try:
                os.dup2(old_stderr, stderr_fileno)
            finally:
                os.close(old_stderr)
