# Demo Video Script (≤3 min)

## Frame

Splunk Agentic Ops hackathon judging rubric weights: Tech / Design / Impact / Idea. Lead with **honesty + structured output** as the differentiator vs vanilla LLM-on-SOC demos.

## Storyboard

### 0:00–0:20 — Hook

**Screen**: split — left = a typical SOAR playbook YAML; right = our triage card JSON.

**VO**:
> Traditional SOAR runs a fixed playbook on every alert. When the alert is ambiguous, the playbook either escalates everything or suppresses everything. Analysts get drowned. We built an IR triage agent that thinks like a tier-1 analyst — and surfaces what it doesn't know.

### 0:20–0:40 — Setup

**Screen**: Splunk Web → Apps → Splunk MCP Server dashboard. Highlight:
- "Server is active" badge
- Endpoint: `https://localhost:8089/services/mcp`
- 10 tools exposed (zoom into the dashboard / `tools/list` curl output)

**VO**:
> Splunk just shipped an official MCP server as a Splunkbase app. It exposes 10 read-mostly tools — run SPL, fetch indexes, walk metadata, query knowledge objects. We give those tools to a Gemini 2.5 Flash agent via function calling.

### 0:40–1:30 — Agent run #1 (brute-force)

**Screen**: terminal — `python -m splunk_ir_agent samples/alert_brute_force.json` with `AGENT_DEBUG=1`.

Show the trace:
```
[turn 0] calls=['splunk_run_query']
[turn 1] calls=['splunk_run_query']
[turn 2] calls=[] text='{ "classification": "Excessive Failed Logins" ... }'
```

Then the full triage card JSON.

**VO**:
> Alert fires: 38 failed logins for user jsmith from 203.0.113.47. The agent autonomously queries Splunk for surrounding events on that user, that IP, and historical firings of the same alert. Two tool calls. Empty result set. Conclusion: investigate, confidence 0.7, three honest uncertainty flags — no corroborating events, no historical signal, source IP attribution unknown.

### 1:30–2:10 — Agent run #2 (encoded PowerShell)

**Screen**: `python -m splunk_ir_agent samples/alert_suspicious_powershell.json`.

Highlight that the agent did 5 parallel tool calls in 2 turns this time.

**VO**:
> Different alert, different strategy. Encoded PowerShell on a workstation. The agent fires five parallel context queries in two turns. Again, empty Splunk data — and again the agent does the right thing: classifies the alert as high severity, recommends investigate with confidence 0.6, and flags that it couldn't prove anything either way.

### 2:10–2:40 — Differentiator

**Screen**: side by side — vanilla LLM ("Critical attack detected, isolate host immediately!") vs ours (structured JSON with uncertainty_flags array).

**VO**:
> Most LLM-on-SOC demos hallucinate findings. Ask GPT to triage with no data and it will invent a story. Ours emits a strict JSON schema with discrete recommended_action values — escalate, contain, investigate, suppress — plus confidence and uncertainty_flags. An honest "I don't know" beats a confident lie. A SOC analyst can trust this output enough to wire it into PagerDuty without a human pre-filter.

### 2:40–3:00 — Tech sketch + close

**Screen**: ARCHITECTURE.md mermaid sequence diagram, then GitHub repo URL.

**VO**:
> Splunk MCP Server exposes the tools. Gemini handles ambiguity reasoning. Triage card output is downstream-system-ready. Code is open source, MIT licensed. We targeted the Security track and Best Use of MCP Server niche. Thanks for watching.

## Recording checklist

- [ ] Splunk Web logged in, MCP app dashboard open in tab 1
- [ ] Terminal in repo dir, `.env` loaded, agent runs verified
- [ ] OBS or built-in Win+G recorder set to record at 1920x1080
- [ ] Microphone tested
- [ ] 1 dry run before final take
- [ ] Cut for ≤3:00 total

## Upload

- YouTube unlisted (per Devpost rules — public host required)
- Title: "Splunk IR Triage Agent — MCP Server + Gemini"
- Description: paste 1-paragraph project summary + GitHub URL
- Add YouTube URL to Devpost submission field
