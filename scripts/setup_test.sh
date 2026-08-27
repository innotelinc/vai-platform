#!/usr/bin/env bash
#
# One-click test install for the innotelinc/dograh merged stack
# (docker-compose.yaml + docker-compose.override.yaml).
#
# After you fill in .env (copy .env.example to .env and set real secrets),
# run this from the repo root:
#
#     ./scripts/setup_test.sh
#
# What it does:
#   1. Validates .env has the secrets the stack needs (fails with a clear list
#      of what is missing, so you never get a half-configured stack).
#   2. Builds the three local images (api, ui, n8n). This fork builds from
#      source via docker-compose.override.yaml (pull_policy: never), so
#      upstream's `remote_up.sh` / `start_docker.sh` — which pass
#      `--pull always` — override that and try to pull the local-only images
#      from a registry, producing the "pull access denied" errors. This script
#      never passes `--pull always`.
#   3. Starts the full stack with the `remote` profile (nginx + coturn +
#      dograh-init) and, when the host has no public IP, the `tunnel` profile
#      (cloudflared quick tunnel) so inbound webhooks stay reachable.
#   4. Waits for api and ui to become healthy (bounded loop).
#   5. Verifies every service endpoint over HTTP and reports pass/fail.
#   6. Prints the access URLs.
#
# The api container runs `alembic upgrade head` on startup (see
# scripts/start_services_docker.sh), so no separate migrate step is needed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_PATH="$SCRIPT_DIR/lib/setup_common.sh"
BOOTSTRAP_LIB=""

if [[ ! -f "$LIB_PATH" ]]; then
    BOOTSTRAP_LIB="$(mktemp)"
    curl -fsSL -o "$BOOTSTRAP_LIB" "https://raw.githubusercontent.com/dograh-hq/dograh/main/scripts/lib/setup_common.sh"
    LIB_PATH="$BOOTSTRAP_LIB"
fi

cleanup() {
    if [[ -n "$BOOTSTRAP_LIB" ]]; then
        rm -f "$BOOTSTRAP_LIB"
    fi
}
trap cleanup EXIT

# shellcheck disable=SC1090
. "$LIB_PATH"

REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

ENV_FILE="$REPO_ROOT/.env"

[[ -f docker-compose.yaml ]] || dograh_fail "docker-compose.yaml not found in $REPO_ROOT"
[[ -f docker-compose.override.yaml ]] || dograh_fail "docker-compose.override.yaml not found in $REPO_ROOT — this fork builds api/ui/n8n from source via this override."

command -v docker >/dev/null 2>&1 || dograh_fail "docker not found on PATH"
docker compose version >/dev/null 2>&1 || dograh_fail "docker compose v2 plugin not available"

# ── 1) Validate .env ──────────────────────────────────────────────────────
[[ -f "$ENV_FILE" ]] || dograh_fail ".env not found in $REPO_ROOT.

Copy the template and fill in real secrets first:
  cp .env.example .env
  # edit .env — at minimum set the secrets below to random values
  # (openssl rand -hex 32)"

env_value() {
    local key=$1
    awk -F= -v k="$key" '$1 == k { sub(/^[^=]*=/, ""); print; exit }' "$ENV_FILE"
}

is_placeholder() {
    local value=$1
    [[ -z "$value" || "$value" == CHANGE_ME* || "$value" == change-me* ]]
}

# Secrets that must be set or the stack cannot boot (no sane default exists).
required_keys=(OSS_JWT_SECRET POSTGRES_PASSWORD REDIS_PASSWORD MINIO_ACCESS_KEY MINIO_SECRET_KEY)

enable_coturn="$(env_value ENABLE_COTURN)"
if [[ "$enable_coturn" == "true" ]]; then
    required_keys+=(TURN_SECRET)
fi

# Interview-stack secrets (n8n sandbox + SearXNG). Compose has fallbacks for
# these, but a test install should use real random values, not the public
# "change-me" defaults.
required_keys+=(SANDBOX_API_KEYS SANDBOX_API_RUNNER_REGISTRATION_TOKEN SANDBOX_API_RUNNER_API_KEY SEARXNG_SECRET)

# OmniRoute (LLM gateway) secrets. The compose fallbacks are deliberately
# undersized ("change-me-omniroute-jwt" is 23 chars) and OmniRoute refuses to
# start with JWT_SECRET < 32 chars — so these must be real values.
required_keys+=(OMNIROUTE_JWT_SECRET OMNIROUTE_API_KEY_SECRET OMNIROUTE_INITIAL_PASSWORD OMNIROUTE_WS_BRIDGE_SECRET)

missing=()
for key in "${required_keys[@]}"; do
    value="$(env_value "$key")"
    if is_placeholder "$value"; then
        missing+=("$key")
    fi
done

if (( ${#missing[@]} )); then
    dograh_fail ".env is missing or has placeholder values for: ${missing[*]}

Set them to random values (openssl rand -hex 32) and re-run."
fi

# ── 2) Compose preflight ──────────────────────────────────────────────────
# Syncs derived keys (SERVER_IP / PUBLIC_HOST / PUBLIC_BASE_URL / ENABLE_COTURN),
# requires the init-compose layout, and dry-runs dograh-init rendering of the
# nginx + coturn configs against the current .env and certs/. This catches
# config drift before anything starts.
dograh_prepare_remote_install "$REPO_ROOT"
docker compose config -q || dograh_fail "docker compose config failed — fix the compose files first."
dograh_success "✓ .env validated; compose config OK"

# Reconcile the Postgres role password with .env (idempotent; only matters
# when a data volume already exists from an earlier start).
dograh_sync_postgres_password "$REPO_ROOT" docker compose

# ── 3) Build local images ─────────────────────────────────────────────────
echo ""
dograh_info "Building local images (api, ui, n8n) — first build takes a while (Python venv + Next.js + ffmpeg)..."
docker compose build api ui n8n
dograh_success "✓ Local images built"

# ── 4) Start the stack ────────────────────────────────────────────────────
# NOTE: intentionally no `--pull always` — it would override pull_policy: never
# and try to pull the local-only images from a registry.
PROFILE_ARGS=(--profile remote)
if dograh_is_local_ipv4 "${SERVER_IP:-}"; then
    dograh_warn "SERVER_IP is a private address — adding the tunnel profile (cloudflared quick tunnel) for inbound webhooks."
    PROFILE_ARGS+=(--profile tunnel)
fi

echo ""
dograh_info "Starting the stack (profiles: ${PROFILE_ARGS[*]})..."
# `up -d` exits non-zero if a service whose health the stack waits on (n8n
# first boot can take minutes) doesn't flip healthy within its healthcheck
# window. The health waits below are the real gate, so tolerate that here and
# re-run `up -d` afterwards to start services that were skipped (n8n-import).
if ! docker compose "${PROFILE_ARGS[@]}" up -d; then
    dograh_warn "docker compose up reported a dependency issue (usually a slow first boot, e.g. n8n); continuing to wait for health."
fi

# ── 5) Wait for health ────────────────────────────────────────────────────
echo ""
dograh_info "Waiting for api and ui to become healthy (api start_period is up to 5 min; first boot also imports the n8n workflow)..."
wait_healthy() {
    local service=$1
    local deadline=$2
    local now
    now=$(date +%s)
    while (( now < deadline )); do
        if docker compose ps --format '{{.Service}} {{.Health}}' 2>/dev/null | grep -q "^${service} healthy$"; then
            dograh_success "✓ $service is healthy"
            return 0
        fi
        sleep 10
        now=$(date +%s)
    done
    dograh_fail "$service did not become healthy within the timeout. Check 'docker compose logs $service'."
}

deadline_api=$(( $(date +%s) + 900 ))
deadline_ui=$(( $(date +%s) + 600 ))

wait_healthy api "$deadline_api"
wait_healthy ui "$deadline_ui"

# Re-run `up -d` now that api/ui are healthy: services gated on other health
# conditions (n8n-import waits for n8n) may have been skipped on the first run.
# Idempotent — containers already up are left alone.
if ! docker compose "${PROFILE_ARGS[@]}" up -d; then
    dograh_warn "Second docker compose up reported issues; continuing to verify — failures below will name the service."
fi

# nginx (port 80 front) depends on dograh-init completing AND ui starting, so a
# first `up` that aborts on another service's dependency can leave it "Created".
# Start it explicitly now that its dependencies are satisfied; idempotent.
if docker compose "${PROFILE_ARGS[@]}" up -d nginx; then
    dograh_success "✓ nginx started — UI reachable on port 80"
else
    dograh_warn "nginx did not start; the UI is still reachable on :3010."
fi

# ── 6) Verify every service endpoint ─────────────────────────────────────
# Probes each published port over HTTP and reports pass/fail. Polls all
# services in parallel within one shared deadline, so slow first boots
# (speaches/kokoro download models on first run; SigNoz migrates schema) don't
# stretch the total wait.
http_code() {
    local url=$1
    local code
    if command -v curl >/dev/null 2>&1; then
        # On connection failure curl -w still prints "000" AND exits non-zero;
        # capture its output first so the trailing `||` can't append a second
        # "000" (which would produce "000000" and be misread as a live port).
        code="$(curl -s -o /dev/null --max-time 5 -w '%{http_code}' "$url" 2>/dev/null || true)"
    elif command -v wget >/dev/null 2>&1; then
        code="$(wget -q -O /dev/null --timeout=5 "$url" 2>/dev/null && echo 200 || echo 000)"
    else
        code="000"
    fi
    # Normalize: anything that isn't exactly a 3-digit HTTP code is "down".
    [[ "$code" =~ ^[0-9]{3}$ ]] || code="000"
    printf '%s\n' "$code"
}

svc_names=(API "Dograh UI" "nginx (port 80)" MinIO "kokoro (TTS)" "speaches (STT)" n8n Grist SigNoz OmniRoute)
svc_urls=(
  "http://localhost:8000/api/v1/health"
  "http://localhost:3010"
  "http://localhost/"
  "http://localhost:9000/minio/health/live"
  "http://127.0.0.1:8880/health"
  "http://127.0.0.1:8001/health"
  "http://localhost:5678/healthz"
  "http://localhost:8484"
  "http://localhost:3301/api/v1/health"
  "http://localhost:20128"
)

if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    dograh_warn "Neither curl nor wget found on the host — skipping service verification."
else
    echo ""
    dograh_info "Verifying services (up to 8 min for slow first boots)..."

    svc_codes=()
    for ((i = 0; i < ${#svc_names[@]}; i++)); do
        svc_codes[i]="000"
    done

    verification_deadline=$(( $(date +%s) + 480 ))
    while (( $(date +%s) < verification_deadline )); do
        all_up=1
        for ((i = 0; i < ${#svc_names[@]}; i++)); do
            [[ "${svc_codes[$i]}" != "000" ]] && continue
            svc_codes[$i]="$(http_code "${svc_urls[$i]}")"
            [[ "${svc_codes[$i]}" != "000" ]] || all_up=0
        done
        [[ "$all_up" == "1" ]] && break
        sleep 10
    done

    echo ""
    failures=0
    for ((i = 0; i < ${#svc_names[@]}; i++)); do
        if [[ "${svc_codes[$i]}" != "000" ]]; then
            dograh_success "  ✓ ${svc_names[$i]} — HTTP ${svc_codes[$i]} (${svc_urls[$i]})"
        else
            dograh_warn "  ✗ ${svc_names[$i]} — no HTTP response (${svc_urls[$i]})"
            failures=$((failures + 1))
        fi
    done

    if (( failures > 0 )); then
        echo ""
        dograh_warn "$failures service(s) did not respond. Inspect with:"
        dograh_warn "  docker compose ps"
        dograh_warn "  docker compose logs <service>"
        exit 1
    fi
fi

# ── 7) Summary ────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                     Test install complete                    ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Services are up. Access URLs:"
echo ""
echo "  Dograh UI       http://localhost:3010   (or http://<host-ip>/ via nginx on port 80)"
echo "  API health      http://localhost:8000/api/v1/health"
echo "  MinIO console   http://localhost:9001"
echo "  n8n             http://localhost:5678"
echo "  Grist           http://localhost:8484"
echo "  SigNoz          http://localhost:3301"
echo "  OmniRoute       http://localhost:20128"
echo "  kokoro (TTS)    http://127.0.0.1:8880/health"
echo "  speaches (STT)  http://127.0.0.1:8001/health"
echo ""
if [[ -n "${PUBLIC_HOST:-}" ]]; then
    echo "Public host:     https://$PUBLIC_HOST"
fi
echo ""
echo "Next steps:"
echo "  - Inspect:         docker compose ps"
echo "  - Logs:            docker compose logs -f api"
echo "  - Stop:            docker compose down"
echo "  - Wipe state:      docker compose down -v   (removes ALL volumes incl. the DB)"
