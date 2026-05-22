"""CLI entry: python -m splunk_ir_agent <alert.json>

Reads a Splunk alert payload (JSON file or stdin), runs triage, prints the
triage card JSON to stdout.
"""
from __future__ import annotations

import argparse
import json
import sys

from rich import print_json

from .agent import triage_alert


def main() -> int:
    parser = argparse.ArgumentParser(prog="splunk-ir-agent")
    parser.add_argument(
        "alert",
        nargs="?",
        type=argparse.FileType("r", encoding="utf-8"),
        default=sys.stdin,
        help="Path to alert JSON file (default: stdin)",
    )
    args = parser.parse_args()

    alert = json.load(args.alert)
    card = triage_alert(alert)
    print_json(data=card)
    return 0


if __name__ == "__main__":
    sys.exit(main())
