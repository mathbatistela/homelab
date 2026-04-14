#!/usr/bin/env python3
"""
Append a structured decision log entry to logs/agent-decisions.jsonl.

Usage:
  python scripts/log_agent_decision.py --decision "Chose fragment mode" --reason "Custom middleware needed" [--impact "config/fragments/traefik/myapp.yml"]
  make agent-decision DECISION="Chose fragment mode" REASON="Custom middleware needed"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = ROOT / "logs" / "agent-decisions.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description="Log an agent decision")
    parser.add_argument("--decision", required=True, help="Short summary of the decision")
    parser.add_argument("--reason", required=True, help="Why this decision was made")
    parser.add_argument("--impact", default=None, help="Files or systems impacted")
    args = parser.parse_args()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "decision": args.decision,
        "reason": args.reason,
    }
    if args.impact:
        entry["impact"] = args.impact

    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Logged decision: {args.decision}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
