"""Build the demo video.

Pipeline:
1. Generate per-scene narration MP3 via edge-tts.
2. Generate per-scene visual PNG (HTML rendered via Playwright).
3. ffmpeg each scene into MP4 (image + audio).
4. Concat into final demo.mp4.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from pathlib import Path

import edge_tts
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "demo"
VOICE = "en-US-AriaNeural"


SCENES: list[dict] = [
    {
        "id": "01_hook",
        "narration": (
            "Traditional security automation runs static playbooks. "
            "When the alert is ambiguous, the playbook either escalates everything or suppresses everything, "
            "and analysts get drowned. We built an incident response triage agent that pulls context from Splunk "
            "the way a human analyst would, and surfaces what it does not know."
        ),
        "html": """<div style="font-family:system-ui;color:#fff;background:#0c1724;height:100vh;display:flex;flex-direction:column;justify-content:center;padding:60px">
            <h1 style="font-size:64px;margin:0;color:#ed0080">Splunk IR Triage Agent</h1>
            <p style="font-size:32px;margin-top:24px">LLM agent over Splunk MCP Server</p>
            <p style="font-size:24px;margin-top:48px;color:#9aa0a6">Structured JSON triage cards with explicit uncertainty flags &mdash; honest gaps over hallucinated findings.</p>
        </div>""",
    },
    {
        "id": "02_mcp_server",
        "narration": (
            "Splunk ships an official MCP server as a Splunkbase app. It exposes ten read-mostly tools at "
            "the management port: run SPL queries, fetch indexes, walk metadata, query knowledge objects. "
            "We give those tools to a Gemini agent via function calling."
        ),
        "html": """<div style="font-family:system-ui;color:#0c1724;background:#fff;height:100vh;padding:40px">
            <h1 style="font-size:42px;color:#ed0080;margin:0">Splunk MCP Server (App #7931)</h1>
            <p style="font-size:22px;margin-top:8px;color:#444">Splunkbase &middot; v1.1.3 &middot; Server is active</p>
            <p style="font-size:20px;margin-top:24px;font-family:monospace;background:#f1f3f4;padding:12px;border-radius:6px">Endpoint: https://localhost:8089/services/mcp</p>
            <h2 style="font-size:28px;margin-top:32px;color:#0c1724">10 tools exposed</h2>
            <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:16px;font-family:monospace;font-size:18px">
                <div>&middot; splunk_run_query</div>
                <div>&middot; splunk_get_indexes</div>
                <div>&middot; splunk_get_index_info</div>
                <div>&middot; splunk_get_metadata</div>
                <div>&middot; splunk_get_knowledge_objects</div>
                <div>&middot; splunk_run_saved_search</div>
                <div>&middot; splunk_get_info</div>
                <div>&middot; splunk_get_user_info</div>
                <div>&middot; splunk_get_user_list</div>
                <div>&middot; splunk_get_kv_store_collections</div>
            </div>
        </div>""",
    },
    {
        "id": "03_alert_in",
        "narration": (
            "Alert fires. Thirty eight failed logins for user jsmith from a single source IP "
            "in fifteen minutes. The agent receives the alert payload as JSON."
        ),
        "html": """<div style="font-family:system-ui;color:#fff;background:#0c1724;height:100vh;padding:40px">
            <h1 style="font-size:36px;color:#ed0080;margin:0">Input: Splunk alert payload</h1>
            <pre style="font-size:18px;background:#1e2a3a;padding:24px;border-radius:8px;margin-top:24px;color:#e8eaed;line-height:1.5">{
  &quot;name&quot;: &quot;Excessive Failed Logins - Single User&quot;,
  &quot;sid&quot;: &quot;scheduler__admin__search__RMD5d34_at_...&quot;,
  &quot;search&quot;: &quot;index=main sourcetype=linux_secure
            action=failure user=jsmith earliest=-15m
          | stats count by user, src&quot;,
  &quot;result&quot;: {
    &quot;user&quot;: &quot;jsmith&quot;,
    &quot;src&quot;: &quot;203.0.113.47&quot;,
    &quot;count&quot;: 38
  }
}</pre>
        </div>""",
    },
    {
        "id": "04_agent_loop",
        "narration": (
            "The agent autonomously queries Splunk for surrounding events on that user, that IP, "
            "and historical firings of the same alert. Two turns. Empty result set. The agent does not "
            "fabricate findings."
        ),
        "html": """<div style="font-family:system-ui;color:#fff;background:#0c1724;height:100vh;padding:40px">
            <h1 style="font-size:36px;color:#ed0080;margin:0">Agent loop (Gemini + function calling)</h1>
            <pre style="font-size:22px;background:#1e2a3a;padding:24px;border-radius:8px;margin-top:32px;color:#e8eaed;line-height:1.8;font-family:'Cascadia Code',monospace">$ python -m splunk_ir_agent samples/alert_brute_force.json

[turn 0] calls=[<span style="color:#34a853">splunk_run_query</span>] text=''
[turn 1] calls=[<span style="color:#34a853">splunk_run_query</span>] text=''
[turn 2] calls=[] text='&#123; "classification":
          "Excessive Failed Logins" ... &#125;'</pre>
        </div>""",
    },
    {
        "id": "05_triage_card",
        "narration": (
            "Output: a strict JSON triage card. Classification, severity, recommended action, "
            "and a confidence score from zero to one. Plus an explicit uncertainty flags array. "
            "An honest I don't know beats a confident lie. A SOC analyst can trust this output "
            "enough to wire it directly into downstream automation."
        ),
        "html": """<div style="font-family:system-ui;color:#fff;background:#0c1724;height:100vh;padding:32px">
            <h1 style="font-size:34px;color:#ed0080;margin:0">Output: triage card JSON</h1>
            <pre style="font-size:16px;background:#1e2a3a;padding:20px;border-radius:8px;margin-top:20px;color:#e8eaed;line-height:1.5">{
  &quot;classification&quot;: &quot;Excessive Failed Logins&quot;,
  &quot;severity&quot;: &quot;high&quot;,
  &quot;entity_context&quot;: &quot;No additional events found for user 'jsmith' or
                       source IP '203.0.113.47' in the surrounding 35-minute window...&quot;,
  &quot;historical_pattern&quot;: &quot;No previous firings of this alert in 30d.&quot;,
  &quot;recommended_action&quot;: <span style="color:#fbbc04">&quot;investigate&quot;</span>,
  &quot;reasoning&quot;: &quot;38 failed login attempts within 15m is high volume suggesting
                  brute-force or account lockout. Lacking corroborating context, analyst
                  review required before automated containment.&quot;,
  &quot;confidence&quot;: <span style="color:#34a853">0.7</span>,
  &quot;uncertainty_flags&quot;: [
    &quot;No additional events for user/IP in surrounding window&quot;,
    &quot;No historical firings of this alert signature&quot;,
    &quot;Cannot determine if IP is internal/external without further enrichment&quot;
  ]
}</pre>
        </div>""",
    },
    {
        "id": "06_differentiator",
        "narration": (
            "Most LLM-on-SOC demos hallucinate findings. Ask a vanilla model to triage with no data "
            "and it will invent a story. Ours emits a strict schema with four discrete recommended actions "
            "and explicit uncertainty. Downstream systems do not need a human pre-filter."
        ),
        "html": """<div style="font-family:system-ui;color:#0c1724;background:#fff;height:100vh;padding:40px">
            <h1 style="font-size:42px;color:#ed0080;margin:0">Vanilla LLM &nbsp;vs&nbsp; This agent</h1>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-top:32px">
                <div style="background:#fce8e6;border-left:6px solid #ea4335;padding:24px;border-radius:6px">
                    <h3 style="margin:0;color:#ea4335;font-size:22px">Hallucinated</h3>
                    <p style="font-size:20px;margin-top:16px">"Critical attack detected.<br>Isolate host immediately!"</p>
                    <p style="font-size:16px;margin-top:24px;color:#666">Confident free-text. No schema. No uncertainty. Analyst must re-verify everything.</p>
                </div>
                <div style="background:#e6f4ea;border-left:6px solid #34a853;padding:24px;border-radius:6px">
                    <h3 style="margin:0;color:#34a853;font-size:22px">Structured + honest</h3>
                    <p style="font-size:20px;margin-top:16px;font-family:monospace">action: "investigate"<br>confidence: 0.7<br>flags: [3 items]</p>
                    <p style="font-size:16px;margin-top:24px;color:#666">Strict JSON. Discrete actions. Calibrated confidence. Wires into PagerDuty without pre-filter.</p>
                </div>
            </div>
        </div>""",
    },
    {
        "id": "07_close",
        "narration": (
            "Splunk MCP Server exposes the tools. Gemini handles ambiguity reasoning. "
            "Triage card output slots into existing SOC workflows. Open source, MIT licensed. "
            "Security track and Best Use of Splunk MCP Server. Thanks for watching."
        ),
        "html": """<div style="font-family:system-ui;color:#fff;background:#0c1724;height:100vh;display:flex;flex-direction:column;justify-content:center;padding:60px">
            <h1 style="font-size:54px;margin:0;color:#ed0080">Splunk IR Triage Agent</h1>
            <p style="font-size:28px;margin-top:24px">github.com/run58669-maker/splunk-ir-triage-agent</p>
            <p style="font-size:22px;margin-top:48px;color:#9aa0a6">Security track &middot; Best Use of Splunk MCP Server</p>
            <p style="font-size:18px;margin-top:32px;color:#9aa0a6">Built with Splunk Enterprise &middot; Splunk MCP Server &middot; Gemini 2.5 Flash via Vertex AI &middot; Python</p>
        </div>""",
    },
]


async def gen_audio():
    for scene in SCENES:
        out = OUT / f"{scene['id']}.mp3"
        comm = edge_tts.Communicate(scene["narration"], VOICE, rate="+0%")
        await comm.save(str(out))
        print(f"  audio: {out.name} ({out.stat().st_size//1024}KB)")


def gen_images():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = ctx.new_page()
        for scene in SCENES:
            html = f"<!doctype html><html><body style='margin:0'>{scene['html']}</body></html>"
            page.set_content(html)
            page.wait_for_timeout(200)
            out = OUT / f"{scene['id']}.png"
            page.screenshot(path=str(out), full_page=False)
            print(f"  image: {out.name}")
        browser.close()


def get_duration(audio_path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def render_scenes():
    list_file = OUT / "concat.txt"
    list_lines = []
    for scene in SCENES:
        img = OUT / f"{scene['id']}.png"
        aud = OUT / f"{scene['id']}.mp3"
        mp4 = OUT / f"{scene['id']}.mp4"
        dur = get_duration(aud) + 0.4
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-loop", "1", "-i", str(img),
             "-i", str(aud),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-tune", "stillimage",
             "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-t", str(dur),
             "-vf", "scale=1920:1080",
             str(mp4)],
            check=True,
        )
        list_lines.append(f"file '{mp4.name}'")
        print(f"  scene mp4: {mp4.name} ({dur:.1f}s)")
    list_file.write_text("\n".join(list_lines), encoding="utf-8")
    final = OUT / "demo.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", str(list_file),
         "-c", "copy", str(final)],
        check=True,
    )
    print(f"\nFinal: {final} ({final.stat().st_size // 1024}KB)")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("=== 1. Generating narration audio (edge-tts) ===")
    asyncio.run(gen_audio())
    print("\n=== 2. Generating scene images (Playwright) ===")
    gen_images()
    print("\n=== 3. Rendering scenes + concatenating (ffmpeg) ===")
    render_scenes()


if __name__ == "__main__":
    main()
