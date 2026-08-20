# Self-hosted interview voice-agent stack

This stack turns Dograh into a phone-based mock-interview agent. A caller is
connected through the FreePBX/Asterisk PBX, the agent conducts the interview,
and the completed transcript is graded by a local LLM and written to Grist.
The stack is open-source and self-hosted: there are no paid telephony, LLM,
workflow, database, or observability dependencies.

## Components

| Component | Compose service / endpoint | Purpose |
|---|---|---|
| Dograh API + UI | `api:8000`, `ui:3010` | Voice-agent orchestration and dashboard |
| PostgreSQL / Redis / MinIO | internal; loopback host ports | Dograh state, queue, and recordings |
| Asterisk ARI | `https://ari.voice.innotel.us` | PBX call control |
| Asterisk media WebSocket | `wss://ws.vai.innotel.us/api/v1/telephony/ws/ari` | Bidirectional call audio |
| Speaches | `127.0.0.1:8001` / `speaches:8000` | Local faster-whisper STT |
| Kokoro | `127.0.0.1:8880` / `kokoro:8880` | Local TTS |
| Ollama | `127.0.0.1:11434` / `ollama:11434` | Local model server |
| 9Router | `127.0.0.1:20128` / `nine-router:20128` | OpenAI-compatible Ollama gateway |
| n8n Community Edition | `http://localhost:5678` | Post-call grading workflow and AI Assistant |
| n8n sandbox + SearXNG | Docker-internal | AI Assistant code execution and web search |
| Grist | `http://localhost:8484` | Interview score and transcript table |
| SigNoz + OTel Collector | `http://localhost:3301` | Traces, errors, and STT/LLM/TTS latency |

`9Router` is the local gateway shipped in `llm_router.py`. It does not add a
closed-source dependency: it is a small Python standard-library proxy that
keeps the OpenAI-compatible endpoint stable and preserves streaming responses
while forwarding to Ollama.

## Start from a fresh checkout

Run these commands from the repository root, not from this directory. The
interview services are part of the single root Compose project.

```bash
git submodule update --init --recursive
cp .env.example .env
# Edit .env and replace every CHANGE_ME value with a generated secret.
# Keep BACKEND_API_ENDPOINT reachable from the n8n container.
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The first start downloads the Ollama image/model and the Whisper/Kokoro model
assets. `ollama-model` pulls `OLLAMA_MODEL` (default `llama3.2:1b`) before 9Router
and n8n are marked ready. Do not expose port 11434 or 20128 through the router;
only NPM-facing web services and PBX SIP/RTP should be externally reachable.

To completely recreate the test installation while preserving the source:

```bash
docker compose down --remove-orphans
docker compose -p vai-platform-test down -v --remove-orphans
# The second command removes only the isolated test project's volumes.
# Start again with the commands above.
```

## Model wiring in Dograh

Configure the workflow's service providers in the Dograh UI. Use the following
values from **inside the `api` container**:

| Stage | Provider | Model | Base URL | Voice / language |
|---|---|---|---|---|
| LLM | `speaches` (OpenAI-compatible) | `llama3.2:1b` | `http://nine-router:20128/v1` | — |
| STT | `speaches` | `Systran/faster-distil-whisper-small.en` | `http://speaches:8000/v1` | `en` |
| TTS | `speaches` | `kokoro` | `http://kokoro:8880/v1` | `af_heart` |

Use any non-empty local placeholder API key if the UI requires one; the local
services do not authenticate requests. The API service must be able to resolve
`nine-router`, `speaches`, and `kokoro` on `app-network`.

## n8n grading and AI Assistant

The root Compose file mounts `n8n-grader-workflow.json`, starts the n8n
Community Edition container, imports and activates the workflow during n8n startup, before the n8n server
process begins, and exports n8n HTTP spans to SigNoz.

The grading path is:

```text
Dograh Webhook
  -> rewrite the public transcript URL to http://api:8000 inside Docker
  -> fetch transcript from the vai API
  -> 9Router /v1/chat/completions
  -> parse strict JSON rubric result
  -> Grist Interviews table
```

The n8n AI Assistant is local as well:

- the model endpoint is `http://nine-router:20128/v1`;
- the `n8n-sandbox-service-api` and privileged runner execute assistant code;
- SearXNG supplies the assistant's web-search endpoint;
- none of the sandbox, runner, or SearXNG ports are published to the host.

Check `docker compose logs n8n nine-router ollama-model` if the
workflow is not visible or the Assistant reports that its model is unavailable.
Workflow import and publish errors fail n8n startup instead of being hidden.
The n8n container waits for the API health check before starting, and transcript
fetches use `N8N_VAI_API_INTERNAL_URL` (default `http://api:8000`) to avoid
routing an internal request back through NPM. The workflow also marks the
public-download request as internal, so the API redirects it to Docker-internal
MinIO instead of sending n8n back through the public storage hostname. The
incoming public URL is still used as the source path, so this works with either
`api.vai.innotel.us` or the main UI host.

### Grist bootstrap

Create a Grist document whose ID is in `GRIST_DOC_ID` and create a table named
`Interviews` with these columns:

```text
Student, Phone, RunID, Score, Verdict, Dimensions, Strengths,
Improvements, Transcript
```

The workflow writes to:
`POST /api/docs/<GRIST_DOC_ID>/tables/Interviews/records`.
For a single-user Grist install, create the document from the Grist UI at
`http://localhost:8484` (or `https://grist.vai.innotel.us`) and put its ID in
`.env` before restarting n8n. Generate the admin user's API key (Grist →
Profile → API) and put it in `.env` as `GRIST_API_KEY`; the grader sends it as a
Bearer token so the transcript table can stay private. This is the only
one-time UI setup; rows are written automatically afterward.

## PBX wiring

The PBX remains the call-control system. Copy and merge the files in
`deploy/asterisk/` on the FreePBX/Asterisk host:

1. configure the `dograh` ARI user and HTTP server on port 8088;
2. configure `websocket_client.conf` with
   `wss://ws.vai.innotel.us/api/v1/telephony/ws/ari`;
3. route the interview DID/extension to `Stasis(dograh)`;
4. in Dograh, add an **Asterisk ARI** telephony configuration with endpoint
   `https://ari.voice.innotel.us`, app name `dograh`, matching password, and
   WebSocket client name `dograh`;
5. assign the inbound workflow and interview extension to the configuration.

The media URL is dynamically signed per call when
`TELEPHONY_WS_TOKEN_ENFORCE=true`; the static Asterisk URI must remain
 tokenless. Enable `ulaw` on the PBX endpoint. See
[`deploy/asterisk/README.md`](../asterisk/README.md) for FreePBX GUI routing,
NAT, module checks, and reload commands.

## Verification

Run this smoke test after every fresh start:

```bash
# Compose and application health
docker compose ps
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:5678/healthz
curl -fsS http://127.0.0.1:3301/api/v1/health
curl -fsS http://127.0.0.1:8880/health
curl -fsS http://127.0.0.1:8001/health
curl -fsS http://127.0.0.1:20128/health
docker compose exec -T ollama ollama list
curl -fsS http://127.0.0.1:8484/ -o /dev/null

# LLM through 9Router
curl -fsS http://127.0.0.1:20128/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"llama3.2:1b","messages":[{"role":"user","content":"Reply with OK"}],"stream":false}'

# TTS and STT round trip
curl -fsS http://127.0.0.1:8880/v1/audio/speech \
  -H 'Content-Type: application/json' \
  -d '{"model":"kokoro","input":"Welcome to your interview.","voice":"af_heart","response_format":"wav"}' \
  -o /tmp/interview.wav
curl -fsS http://127.0.0.1:8001/v1/audio/transcriptions \
  -F file=@/tmp/interview.wav \
  -F model=Systran/faster-distil-whisper-small.en \
  -F language=en
```

Then POST a representative Dograh webhook payload to
`http://127.0.0.1:5678/webhook/interview-graded` and confirm a row appears in
Grist. Open SigNoz and verify spans for `n8n`, `vai-api`, and the pipeline
service, including `metrics.ttfb` for LLM/TTS/STT stages.

For a deterministic workflow-only test without Ollama inference, run:

```bash
python3 deploy/interview-stack/verify_chain.py
```

That script is a stand-in for CI and does not replace the real call test.

## Network and production notes

- Import `npm-proxy-hosts.json` into Nginx Proxy Manager for the seven HTTPS
  hosts. Enable WebSockets for the API, media WS, ARI, and n8n hosts.
- Forward only TCP 80/443 to NPM and SIP/RTP ports to Asterisk. Keep databases,
  model servers, OTel ingest, Grist, n8n, and SigNoz behind NPM/firewall policy.
- Use the exact host/IP values in `NETWORKING.md`; update them when the LAN
  address changes.
- Model and audio assets are cached in Docker volumes. Back up PostgreSQL,
  MinIO, Grist, n8n, Ollama, and SigNoz volumes before upgrades.
