# Splunk Enterprise + MCP Server — Local Setup Runbook

Step-by-step from a clean Windows machine to a working MCP endpoint plus a Gemini agent that calls it.

## 1. Install Splunk Enterprise 10.4.0 (Windows MSI)

```powershell
msiexec /i "<path-to>\splunk-10.4.0-windows-x64.msi" `
  /qn `
  AGREETOLICENSE=Yes `
  SPLUNKDB="C:\Program Files\Splunk\var\lib\splunk" `
  SPLUNKUSERNAME=admin `
  SPLUNKPASSWORD=<YOUR_ADMIN_PASSWORD> `
  LAUNCHSPLUNK=1
```

> The host's computer name must be ASCII letters/numbers/underscore only (no dashes, no non-ASCII). Splunk's first-time-run rejects everything else.

After install:
- Splunk Web: `http://localhost:8000`
- Splunk management port: `https://localhost:8089`
- Service auto-starts as `Splunkd Service`

## 2. Enable token authentication

Splunk Web → Settings → Tokens → toggle "Enable Token Authentication", save.

CLI alternative:
```powershell
& "C:\Program Files\Splunk\bin\splunk.exe" enable token-auth -auth admin:<YOUR_ADMIN_PASSWORD>
```

## 3. Install Splunk MCP Server app (Splunkbase app 7931)

Splunk Web → Apps → Find more apps → search "MCP Server" → Install (sign in with your splunk.com account) → accept the license → restart Splunk when prompted.

CLI alternative:
```powershell
& "C:\Program Files\Splunk\bin\splunk.exe" install app <path>\splunk-mcp-server.tgz -auth admin:<YOUR_ADMIN_PASSWORD>
```

## 4. Generate an encrypted MCP token

Splunk Web → Apps → **Splunk MCP Server** → click **Create MCP Encrypted Token**:
- User: `admin` (or any user that should authenticate to the MCP server)
- Audience: `mcp` (fixed)
- Expiration: up to `+180d`
- Copy the token (shown ONCE) and store it as a secret on your machine — do NOT commit it.

## 5. Smoke test the MCP endpoint

```powershell
$token = '<paste-token-here>'
curl -k -X POST `
  -H "Authorization: Bearer $token" `
  -H "Content-Type: application/json" `
  -H "Accept: application/json,text/event-stream" `
  -d '{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/list\"}' `
  https://localhost:8089/services/mcp
```

Expected: HTTP 200 with a JSON-RPC envelope listing 10 tools — `splunk_run_query`, `splunk_get_indexes`, `splunk_get_metadata`, etc.

## 6. Run the agent

```powershell
# Project deps
pip install -e .

# Authenticate to Vertex AI (preferred — uses Gemini via GCP)
gcloud auth application-default login

# Configure
cp .env.example .env
# Edit .env: set GCP_PROJECT, SPLUNK_MCP_URL, SPLUNK_MCP_TOKEN

python -m splunk_ir_agent samples/alert_brute_force.json
```

You should see the agent issue a couple of `splunk_run_query` calls and emit a triage card JSON to stdout.

## Verification checklist

- [ ] `Get-Service Splunkd` → Status: Running
- [ ] Splunk Web loads at http://localhost:8000
- [ ] Splunk MCP Server app shows under Apps menu
- [ ] `/services/mcp` tools/list returns 200 + 10 tools with valid token
- [ ] `python -m splunk_ir_agent samples/alert_brute_force.json` prints a valid triage card JSON
