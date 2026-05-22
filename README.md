# Splunk IR Triage Agent

**Hackathon**: [Splunk Agentic Ops](https://splunk.devpost.com/) — submission DDL 2026-06-15 9am PDT.

**Tracks targeted**:
- Security (main) — $3K
- Best Use of Splunk MCP Server (niche) — $1K

## Concept

LLM agent + Splunk MCP Server. On alert fire:

1. **Splunk MCP Server** (Splunkbase app #7931, installed on Splunk Enterprise) exposes 10 tools at `https://<host>:8089/services/mcp`: `splunk_run_query`, `splunk_get_indexes`, `splunk_get_index_info`, `splunk_get_metadata`, `splunk_get_knowledge_objects`, `splunk_run_saved_search`, `splunk_get_info`, `splunk_get_user_info`, `splunk_get_user_list`, `splunk_get_kv_store_collections`.
2. **Agent** (Gemini 2.5 Flash via Vertex AI, function-calling loop) receives an alert payload, autonomously pulls context: surrounding events, entity history (host/user/process), historical occurrences of the same alert signature.
3. Agent emits an analyst-facing **triage card** (strict JSON):
   - `classification` + `severity`
   - `entity_context` summary
   - `historical_pattern` comparison
   - `recommended_action`: one of `escalate` / `contain` / `investigate` / `suppress`
   - `reasoning` + `confidence` + `uncertainty_flags`

**Differentiator**: traditional SOAR runs static playbooks. We put an LLM as the ambiguity / context-aggregation layer between alert and analyst, with explicit uncertainty surfacing.

## Stack

- **Splunk Enterprise 10.4.0** (60-day trial, local install)
- **Splunk MCP Server v1.1.3** (Splunkbase #7931, supports Splunk 9.2–10.4)
- **Gemini 2.5 Flash via Vertex AI** (Python SDK `google-genai` ≥0.5)
- **Python 3.11+** for agent orchestration
- Direct HTTP to Splunk's `/services/mcp` (MCP streamable HTTP); no `mcp-remote` proxy needed

## Quick start

```powershell
# 1. Install Splunk Enterprise + Splunk MCP Server app (see SETUP.md)
# 2. Generate MCP encrypted token via the Splunk MCP Server app UI
# 3. gcloud auth application-default login   (Vertex AI ADC)

pip install -e .
cp .env.example .env   # fill SPLUNK_MCP_TOKEN, GCP_PROJECT, etc.
python -m splunk_ir_agent samples/alert_brute_force.json
```

## Status

- [x] Splunk Enterprise 10.4.0 installed + Splunk MCP Server v1.1.3 active
- [x] MCP encrypted token + `tools/list` smoke test → HTTP 200 + 10 tools
- [x] Agent loop end-to-end on 3 sample alerts → valid triage cards
- [x] README / SETUP.md / ARCHITECTURE.md / LICENSE / DEMO_SCRIPT.md
- [x] Code repository created
- [ ] Demo video recorded + uploaded
- [ ] Devpost submission

## Sample output

Run on `samples/alert_brute_force.json` (38 failed logins for user `jsmith` from `203.0.113.47`):

```json
{
  "classification": "Excessive Failed Logins",
  "severity": "high",
  "entity_context": "No additional events were found for user 'jsmith' or source IP '203.0.113.47' in the surrounding 35-minute window. Failed login attempts are isolated.",
  "historical_pattern": "No previous firings of this alert in the last 30 days.",
  "recommended_action": "investigate",
  "reasoning": "38 failed login attempts within 15m is high volume suggesting brute-force or account lockout. Lacking corroborating context, analyst review required before automated containment.",
  "confidence": 0.7,
  "uncertainty_flags": [
    "No additional events for user/IP in surrounding window",
    "No historical firings of this alert signature",
    "Cannot determine if IP is internal/external without further enrichment"
  ]
}
```

## Submission requirements (verified)

- [x] Code repository + MIT license + README
- [x] Architecture diagram (`ARCHITECTURE.md`, Mermaid)
- [ ] ≤3min demo video (YouTube/Vimeo/Youku)
- [x] Text description
- [x] Splunk integration (MCP Server qualifies)
