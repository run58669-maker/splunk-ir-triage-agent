"""Thin HTTP client for Splunk MCP Server REST endpoint.

Splunk MCP Server (app 7931) exposes MCP over Splunk's mgmt port at
`/services/mcp`. We talk to it directly via streamable HTTP rather than
going through `mcp-remote` so the agent can introspect / batch tools.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class SplunkMCPClient:
    base_url: str
    token: str
    verify: bool = False
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "SplunkMCPClient":
        url = os.environ["SPLUNK_MCP_URL"]
        token = os.environ["SPLUNK_MCP_TOKEN"]
        verify = os.environ.get("TLS_VERIFY", "0") == "1"
        return cls(base_url=url.rstrip("/"), token=token, verify=verify)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def list_tools(self) -> list[dict[str, Any]]:
        r = httpx.post(
            f"{self.base_url}/",
            headers=self._headers(),
            verify=self.verify,
            timeout=self.timeout,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        r.raise_for_status()
        return r.json().get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        r = httpx.post(
            f"{self.base_url}/",
            headers=self._headers(),
            verify=self.verify,
            timeout=self.timeout,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments},
            },
        )
        r.raise_for_status()
        result = r.json()
        if "error" in result:
            raise RuntimeError(f"MCP tool error: {result['error']}")
        return result.get("result", {})
