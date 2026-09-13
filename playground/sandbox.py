"""Runs untrusted Regards programs in a separate process with a time limit."""

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import regards

RUNNER = Path(__file__).with_name("runner.py")
STATUSES = {0: "sent", 1: "regards", 2: "error", 3: "internal", 4: "output_limit"}


def run_program(source="", stdin="", eml=None, timeout=5):
    """Returns the program's output, warnings and errors, exit code and status."""
    request = {"stdin": stdin}
    if eml is not None:
        request["eml"] = base64.b64encode(eml).decode("ascii")
    else:
        request["source"] = source
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(Path(regards.__file__).resolve().parent),
        "PYTHONIOENCODING": "utf-8:replace",
    }
    started = time.monotonic()
    with tempfile.TemporaryDirectory() as folder:
        try:
            done = subprocess.run([sys.executable, str(RUNNER)], input=json.dumps(request).encode("utf-8"),
                                  capture_output=True, cwd=folder, env=env, timeout=timeout)
            stdout, stderr, code = done.stdout, done.stderr, done.returncode
            status = STATUSES.get(code, "internal")
        except subprocess.TimeoutExpired as e:
            stdout, stderr, code, status = e.stdout or b"", e.stderr or b"", None, "timeout"
    return {
        "stdout": stdout.decode("utf-8", "replace"),
        "stderr": stderr.decode("utf-8", "replace"),
        "exit_code": code,
        "status": status,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }
