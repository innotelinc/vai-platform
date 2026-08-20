#!/usr/bin/env python3
"""Trigger the full interview grading chain on demand and verify the grade.

Exercises the real production path end to end:

  workflow run (api db_client)
    -> transcript uploaded to MinIO (production artifact uploader)
    -> public download token + URL
    -> n8n webhook -> transcript fetch -> Ollama (llama3.2:1b)
    -> JSON parse -> Grist Interviews row

It does NOT fake or mock any stage: the webhook POST, the transcript fetch,
the Ollama inference, and the Grist write all happen against the running
stack, exactly as they do for a real completed call.

Run inside the API container (the script imports api.* and reaches n8n and
Grist by service name). GRIST_DOC_ID and GRIST_API_KEY must be in the
environment:

  docker cp deploy/interview-stack/smoke_test_grader.py vai-platform-api-1:/tmp/
  docker exec -e GRIST_DOC_ID=<doc-id> -e GRIST_API_KEY=<api-key> \\
    vai-platform-api-1 python /tmp/smoke_test_grader.py

Exit code 0 = full chain verified (a grade row landed in Grist and its
transcript matches the fixture); non-zero = a stage failed.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request

BACKEND_API_ENDPOINT = os.environ.get("BACKEND_API_ENDPOINT", "http://localhost:8000")
N8N_WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL", "http://n8n:5678/webhook/interview-graded"
)
GRIST_BASE_URL = os.environ.get("GRIST_BASE_URL", "http://grist:8484")
GRIST_DOC_ID = os.environ.get("GRIST_DOC_ID", "")
GRIST_API_KEY = os.environ.get("GRIST_API_KEY", "")

# Production transcript format (see api/utils/transcript.py): '[timestamp]
# user: <candidate>' / '[timestamp] assistant: <caller, role-played by the
# interviewer>'. The grader grades ONLY the 'user:' lines.
TRANSCRIPT = """[00:00:00] user: Good morning, thanks for calling the IT Help Desk, this is Jordan. How can I help you?
[00:00:04] assistant: Hi, I can't connect to the VPN. It worked yesterday and now it just spins and never connects.
[00:00:10] user: I'm sorry to hear that. Can I confirm your name and employee ID, please?
[00:00:15] assistant: Yes, it's Dana Reyes, ID 8842.
[00:00:19] user: Thanks Dana. Can you tell me — when you try to connect, do you see any error message on screen?
[00:00:26] assistant: It says 'unable to establish connection' after about thirty seconds.
[00:00:31] user: Got it. Are you on the office network or at home right now?
[00:00:35] assistant: I'm working from home today.
[00:00:38] user: OK, let's try a couple of quick steps. Can you make sure your system clock shows the correct date and time?
[00:00:45] assistant: Yes, the time looks correct.
[00:00:48] user: Great. Next, could you disconnect from Wi-Fi and reconnect, then try the VPN again?
[00:00:55] assistant: I did that, still the same spinning.
[00:00:58] user: Understood. Let me check the VPN service status on our side. One moment please.
[00:01:05] assistant: Sure, take your time.
[00:01:10] user: Thank you for waiting. I can see the VPN gateway is up, so this looks like it may be a profile issue on your machine. I'd like to escalate this to Tier 2 so they can rebuild your VPN profile. I'll note your employee ID 8842 and the error 'unable to establish connection' in the ticket, and you'll get an update within the hour. Is there anything else I can help you with?
[00:01:28] assistant: No, that's all. Thank you!
[00:01:31] user: You're welcome. Have a great day, Dana.
"""

# A distinctive phrase used to confirm the stored transcript is the real text
# (not the webhook payload wrapper) — guards against the binary/text fetch bug.
_TRANSCRIPT_MARKER = "VPN profile"


def _http(method, url, *, payload=None, headers=None, timeout=30, attempts=3):
    """Minimal HTTP helper; follows redirects. Returns (status, body_bytes).

    Retries transient failures (socket timeouts / connection resets) a few
    times — the API can stall briefly while generating a signed MinIO URL or
    right after a container restart.
    """
    req_headers = dict(headers or {})
    data = None
    if payload is not None:
        req_headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    last = (0, b"")
    for attempt in range(attempts):
        req = urllib.request.Request(
            url, data=data, headers=req_headers, method=method
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()
        except Exception as e:  # URLError, TimeoutError, ConnectionResetError, ...
            last = (0, str(e).encode())
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    return last


async def ensure_workflow():
    """Reuse an existing workflow, or create a user + workflow if none exist."""
    from api.db import db_client

    workflows = await db_client.get_all_workflows()
    if workflows:
        wf = workflows[0]
        print(f"[workflow] reusing {wf.name!r} (id {wf.id})")
        return wf

    user = await db_client.create_user_with_email(
        "smoke@localhost", "unused-password-hash", name="Smoke Test"
    )
    wf = await db_client.create_workflow(
        name="Interview Grader (smoke)",
        workflow_definition={},
        user_id=user.id,
    )
    print(f"[workflow] created {wf.name!r} (id {wf.id})")
    return wf


async def main():
    parser = argparse.ArgumentParser(
        description="Trigger the full interview grading chain and verify the grade."
    )
    parser.add_argument("--timeout", type=int, default=600,
                        help="seconds to wait for the grade in Grist (default 600)")
    parser.add_argument("--student", default="Jordan Avery")
    parser.add_argument("--phone", default="+15550102030")
    parser.add_argument("--transcript-file", default=None,
                        help="path to a transcript file to grade instead of the fixture")
    parser.add_argument("--no-precheck", action="store_true",
                        help="skip the internal transcript fetch precheck")
    args = parser.parse_args()

    if not GRIST_DOC_ID or not GRIST_API_KEY:
        print("ERROR: set GRIST_DOC_ID and GRIST_API_KEY in the environment.",
              file=sys.stderr)
        return 2

    transcript = TRANSCRIPT
    if args.transcript_file:
        with open(args.transcript_file, encoding="utf-8") as f:
            transcript = f.read()

    from api.db import db_client
    from api.services.workflow_run_artifacts import upload_workflow_run_artifacts

    # 1. Workflow
    workflow = await ensure_workflow()

    # 2. Run
    run_name = f"smoke-{int(time.time())}"
    run = await db_client.create_workflow_run(
        name=run_name,
        workflow_id=workflow.id,
        mode="outbound",
        user_id=workflow.user_id,
        initial_context={"student_name": args.student, "phone": args.phone},
    )
    print(f"[run] created run {run.id} ({run_name})")

    # 3. Upload the transcript exactly like the production pipeline does.
    await upload_workflow_run_artifacts(run.id, transcript_text=transcript)
    run = await db_client.get_workflow_run(run.id)
    print(f"[artifacts] transcript uploaded: {run.transcript_url}")

    # 4. Public download token + URL (same construction as run_integrations).
    token = await db_client.ensure_public_access_token(run.id)
    transcript_url = (
        f"{BACKEND_API_ENDPOINT}/api/v1/public/download/workflow/{token}/transcript"
    )

    # 5. Precheck: fetch the transcript through the same internal path n8n uses.
    if not args.no_precheck:
        internal_url = (
            f"http://127.0.0.1:8000/api/v1/public/download/workflow/{token}"
            f"/transcript?internal=true"
        )
        status, body = _http("GET", internal_url, timeout=30)
        if status != 200:
            print(f"FAIL: transcript precheck returned HTTP {status} "
                  f"({body[:200]!r})", file=sys.stderr)
            return 1
        print(f"[precheck] internal transcript fetch: 200 ({len(body)} bytes)")

    # 6. Fire the n8n webhook with the production payload shape.
    payload = {
        "run_id": str(run.id),
        "student_name": args.student,
        "phone": args.phone,
        "transcript_url": transcript_url,
    }
    status, body = _http("POST", N8N_WEBHOOK_URL, payload=payload, timeout=30)
    print(f"[webhook] POST {N8N_WEBHOOK_URL} -> {status} {body[:120]!r}")
    if status != 200:
        print(f"FAIL: n8n webhook returned HTTP {status}", file=sys.stderr)
        return 1

    # 7. Poll Grist for the graded row.
    print(f"[grist] polling for RunID={run.id} (up to {args.timeout}s)...")
    deadline = time.time() + args.timeout
    row = None
    while time.time() < deadline:
        row = _find_grist_row(run.id)
        if row:
            break
        time.sleep(15)
    if not row:
        print(f"FAIL: no Grist row for RunID={run.id} within {args.timeout}s",
              file=sys.stderr)
        return 1

    elapsed = args.timeout - max(0.0, deadline - time.time())
    print(f"[grist] row found after ~{elapsed:.0f}s")

    # 8. Verify the grade and that the stored transcript is the real text.
    score = row.get("Score")
    verdict = row.get("Verdict")
    dimensions = row.get("Dimensions")
    stored_transcript = row.get("Transcript") or ""

    print("\n=== grade result ===")
    print(f"  RunID:    {row.get('RunID')}")
    print(f"  Student:  {row.get('Student')}")
    print(f"  Score:    {score}")
    print(f"  Verdict:  {verdict}")
    if isinstance(dimensions, dict):
        for k, v in dimensions.items():
            print(f"    {k}: {v}")
    print(f"  Transcript: {len(stored_transcript)} chars stored in Grist")

    problems = []
    if verdict not in ("pass", "review", "fail"):
        problems.append(f"verdict {verdict!r} is not one of pass/review/fail")
    if not isinstance(score, (int, float)):
        problems.append(f"score {score!r} is not numeric")
    if _TRANSCRIPT_MARKER not in stored_transcript:
        problems.append(
            f"stored transcript does not contain marker {_TRANSCRIPT_MARKER!r} "
            "- transcript fetch/write path may be broken"
        )
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1

    print("\nPASS: full grading chain verified end to end.")
    return 0


def _find_grist_row(run_id):
    """Return the Interviews row whose RunID matches, or None."""
    url = f"{GRIST_BASE_URL}/api/docs/{GRIST_DOC_ID}/tables/Interviews/records"
    headers = {"Authorization": f"Bearer {GRIST_API_KEY}"}
    status, body = _http("GET", url, headers=headers, timeout=30)
    if status != 200:
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    for rec in data.get("records", []):
        if str(rec.get("fields", {}).get("RunID")) == str(run_id):
            return rec["fields"]
    return None


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
