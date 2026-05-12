#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
PYTHON = ROOT_DIR / "venv" / "bin" / "python"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PatentEasy backend quality gates.")
    parser.add_argument("--live-kipris", action="store_true", help="Run tests that call the real KIPRIS API.")
    parser.add_argument("--live-llm", action="store_true", help="Run tests that call the real LLM provider API.")
    parser.add_argument(
        "--live-summary",
        action="store_true",
        help="Run the combined KIPRIS + LLM summary live test.",
    )
    args = parser.parse_args()

    python = str(PYTHON if PYTHON.exists() else Path(sys.executable))
    commands = [[python, "-m", "pytest"]]

    if args.live_kipris:
        commands.append([python, "-m", "pytest", "tests/test_search_live.py", "-m", "live_kipris", "-s"])
    if args.live_llm:
        commands.append([python, "-m", "pytest", "tests/test_llm_client_live.py", "-m", "live_llm", "-s"])
    if args.live_summary:
        commands.append(
            [
                python,
                "-m",
                "pytest",
                "tests/test_summary_live.py",
                "-m",
                "live_kipris and live_llm",
                "-s",
            ]
        )

    env = os.environ.copy()
    if args.live_kipris or args.live_summary:
        env["RUN_LIVE_KIPRIS"] = "1"
    if args.live_llm or args.live_summary:
        env["RUN_LIVE_LLM"] = "1"

    for command in commands:
        print("+", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT_DIR, env=env, check=False)
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
