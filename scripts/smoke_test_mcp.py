"""Smoke test: list Splunk MCP tools, optionally invoke get_splunk_info.

Run after SETUP.md step 5 to verify the MCP endpoint is reachable + token works.
Does NOT call the LLM — pure HTTP probe.
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

# Allow running without install via PYTHONPATH=src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from splunk_ir_agent.splunk_mcp_client import SplunkMCPClient  # noqa: E402


def main() -> int:
    load_dotenv()
    mcp = SplunkMCPClient.from_env()

    print(f"Endpoint: {mcp.base_url}")
    print("Listing tools...")
    tools = mcp.list_tools()
    print(f"  -> {len(tools)} tools found")
    for t in tools:
        print(f"  - {t['name']}: {t.get('description', '')[:80]}")

    if any(t["name"] == "splunk_get_info" for t in tools):
        print("\nInvoking splunk_get_info...")
        info = mcp.call_tool("splunk_get_info", {})
        print(json.dumps(info, indent=2)[:800])

    return 0


if __name__ == "__main__":
    sys.exit(main())
