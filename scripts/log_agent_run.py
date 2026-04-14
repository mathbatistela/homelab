#!/usr/bin/env python3
"""
Append a structured log entry to logs/agent-runs.jsonl.

Usage:
  python scripts/log_agent_run.py <target> [status]
  python scripts/log_agent_run.py play-infra started
  python scripts/log_agent_run.py add-vm done
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "agent-runs.jsonl"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: log_agent_run.py <target> [status]")
        return 1

    target = sys.argv[1]
    status = sys.argv[2] if len(sys.argv) > 2 else "unknown"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "status": status,
    }

    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Logged: {target} -> {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
