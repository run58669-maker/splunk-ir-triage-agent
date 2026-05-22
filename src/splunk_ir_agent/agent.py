"""Gemini agent loop: receives Splunk alert, calls Splunk MCP tools, emits triage card."""
from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

from .splunk_mcp_client import SplunkMCPClient
from .triage import TRIAGE_SYSTEM_PROMPT, format_alert_for_triage

MAX_TURNS = 12
MAX_TOOL_RESULT_CHARS = 6000


def _clean_schema(schema: dict) -> dict:
    """Strip JSON Schema keys Gemini doesn't accept (pattern, examples, etc)."""
    if not isinstance(schema, dict):
        return schema
    strip = {"pattern", "examples", "default", "$schema", "$id", "title"}
    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k in strip:
            continue
        if isinstance(v, dict):
            out[k] = _clean_schema(v)
        elif isinstance(v, list):
            out[k] = [_clean_schema(x) if isinstance(x, dict) else x for x in v]
        else:
            out[k] = v
    return out


def mcp_tools_to_gemini_schema(mcp_tools: list[dict[str, Any]]) -> list[types.Tool]:
    decls = [
        types.FunctionDeclaration(
            name=t["name"],
            description=t.get("description", "")[:1024],
            parameters=_clean_schema(t.get("inputSchema") or {"type": "object", "properties": {}}),
        )
        for t in mcp_tools
    ]
    return [types.Tool(function_declarations=decls)]


def triage_alert(alert: dict) -> dict:
    load_dotenv()
    mcp = SplunkMCPClient.from_env()
    if os.environ.get("GCP_PROJECT"):
        client = genai.Client(
            vertexai=True,
            project=os.environ["GCP_PROJECT"],
            location=os.environ.get("GCP_LOCATION", "us-central1"),
        )
    else:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    tools = mcp_tools_to_gemini_schema(mcp.list_tools())

    config = types.GenerateContentConfig(
        tools=tools,
        system_instruction=TRIAGE_SYSTEM_PROMPT,
        temperature=0.1,
    )

    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part.from_text(text=format_alert_for_triage(alert))])
    ]

    for turn in range(MAX_TURNS):
        resp = client.models.generate_content(model=model, contents=contents, config=config)
        cand = resp.candidates[0]
        parts = cand.content.parts or []

        function_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]
        if os.environ.get("AGENT_DEBUG"):
            text_preview = "".join(getattr(p, "text", "") or "" for p in parts)[:200]
            print(f"[turn {turn}] calls={[fc.name for fc in function_calls]} text={text_preview!r}")

        if not function_calls:
            text = "".join(getattr(p, "text", "") or "" for p in parts)
            return _parse_triage_json(text)

        contents.append(cand.content)
        response_parts = []
        for fc in function_calls:
            try:
                result = mcp.call_tool(fc.name, dict(fc.args or {}))
                payload = {"content": json.dumps(result)[:MAX_TOOL_RESULT_CHARS]}
            except Exception as e:
                payload = {"error": str(e)[:500]}
            response_parts.append(
                types.Part.from_function_response(name=fc.name, response=payload)
            )
        contents.append(types.Content(role="user", parts=response_parts))

    raise RuntimeError(f"Triage exceeded {MAX_TURNS} turns without completing")


def _parse_triage_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in response: {text[:200]!r}")
    return json.loads(text[start : end + 1])
