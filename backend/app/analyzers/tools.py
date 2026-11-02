"""Wrappers around external analysis tools (Ruff, Bandit, Radon, node, gofmt).

All tools only *parse* the submitted code; nothing is ever executed.
Each wrapper returns None when the tool is unavailable so callers can fall back.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from typing import Any, Iterator

log = logging.getLogger(__name__)
TIMEOUT = 30


@contextmanager
def temp_source(code: str, suffix: str) -> Iterator[str]:
    d = tempfile.mkdtemp(prefix="devpilot_")
    path = os.path.join(d, f"snippet.{suffix}")
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(code)
        yield path
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _run(args: list[str], cwd: str | None = None) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=TIMEOUT, cwd=cwd,
            encoding="utf-8", errors="replace",
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as exc:
        log.warning("Tool %s failed: %s", args[:3], exc)
        return None


def _python_tool(module: str) -> list[str] | None:
    exe_dir = os.path.dirname(sys.executable)
    for cand in (os.path.join(exe_dir, module + ".exe"), os.path.join(exe_dir, module)):
        if os.path.isfile(cand):
            return [cand]
    found = shutil.which(module)
    if found:
        return [found]
    return [sys.executable, "-m", module]


RUFF_SELECT = "E9,F,B,N8,UP,SIM,C4,PERF,PLR1714,PLR5501,PLW0120,PLW0602,PLW2901,E711,E712,E713,E714,E721,E722,E731,E741,RET,PIE,ERA001"


def ruff_check(code: str) -> list[dict[str, Any]] | None:
    base = _python_tool("ruff")
    with temp_source(code, "py") as path:
        proc = _run(base + ["check", "--no-cache", "--isolated", "--output-format", "json",
                            "--select", RUFF_SELECT, "--line-length", "120", path])
    if proc is None or proc.returncode not in (0, 1):
        return None
    try:
        return json.loads(proc.stdout or "[]")
    except json.JSONDecodeError:
        return None


def ruff_fix(code: str, fmt: bool = True) -> str | None:
    """Apply Ruff's *safe* autofixes (and optionally formatting) to a copy of the code."""
    base = _python_tool("ruff")
    with temp_source(code, "py") as path:
        p1 = _run(base + ["check", "--no-cache", "--isolated", "--fix-only", "--select",
                          "F401,E711,E712,E713,E714,UP,SIM,C4,PIE,RET505,I", path])
        if p1 is None:
            return None
        if fmt:
            p2 = _run(base + ["format", "--no-cache", "--isolated", "--line-length", "100", path])
            if p2 is None or p2.returncode != 0:
                return None
        with open(path, encoding="utf-8") as fh:
            return fh.read()


def bandit_check(code: str) -> list[dict[str, Any]] | None:
    base = _python_tool("bandit")
    with temp_source(code, "py") as path:
        proc = _run(base + ["-f", "json", "-q", path])
    if proc is None or not proc.stdout.strip():
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    return data.get("results", [])


def radon_complexity(code: str) -> list[tuple[str, int, int]] | None:
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return None
    try:
        blocks = cc_visit(code)
    except Exception:  # radon raises on syntax errors
        return None
    # cc_visit returns functions, classes and methods; classes aggregate their
    # methods, so only keep function/method blocks.
    return [(getattr(b, "fullname", b.name), b.lineno, b.complexity)
            for b in blocks if not hasattr(b, "methods")]


def node_syntax_check(code: str, suffix: str = "mjs") -> tuple[int, str] | None | bool:
    """Returns True if OK, (line, message) on syntax error, None if node unavailable."""
    node = shutil.which("node")
    if not node:
        return None
    with temp_source(code, suffix) as path:
        proc = _run([node, "--check", path])
    if proc is None:
        return None
    if proc.returncode == 0:
        return True
    err = proc.stderr
    import re

    m = re.search(r"snippet\.\w+:(\d+)", err)
    line = int(m.group(1)) if m else 0
    msg = next((ln.strip() for ln in err.splitlines() if "Error" in ln), err.strip().splitlines()[-1] if err.strip() else "Syntax error")
    return line, msg


def gofmt_check(code: str) -> tuple[int, str] | None | bool:
    gofmt = shutil.which("gofmt")
    if not gofmt:
        return None
    with temp_source(code, "go") as path:
        proc = _run([gofmt, "-e", "-l", path])
    if proc is None:
        return None
    if proc.returncode == 0 and not proc.stderr.strip():
        return True
    import re

    m = re.search(r"snippet\.go:(\d+):\d+:\s*(.*)", proc.stderr)
    if not m:
        return True
    return int(m.group(1)), m.group(2)


def tool_available(name: str) -> bool:
    if name in ("ruff", "bandit"):
        exe_dir = os.path.dirname(sys.executable)
        return any(os.path.isfile(os.path.join(exe_dir, name + ext)) for ext in (".exe", "")) or bool(shutil.which(name))
    return bool(shutil.which(name))
