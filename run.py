#!/usr/bin/env python3
"""
Entry point for running this project without installing the package (optional).

  python run.py                  # full benchmark — same as: llm-local-perf
  python run.py --simple         # microbenchmarks only
  python run.py cursor [args]    # same as: cursor-ollama

Requires dependencies from pyproject.toml (e.g. psutil); use a venv and pip install -e .
if imports fail.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_src_path() -> None:
    root = Path(__file__).resolve().parent
    src = root / "src"
    if src.is_dir():
        s = str(src)
        if s not in sys.path:
            sys.path.insert(0, s)


def main() -> None:
    _ensure_src_path()
    argv = sys.argv[:]

    if len(argv) > 1 and argv[1] == "cursor":
        sys.argv = [argv[0]] + argv[2:]
        from llm_local_perf.cursor_ollama import main as run_other

        run_other()
        return

    if len(argv) > 1 and argv[1] == "perf":
        sys.argv = [argv[0]] + argv[2:]

    from llm_local_perf.__main__ import main as run_perf

    run_perf()


if __name__ == "__main__":
    main()
