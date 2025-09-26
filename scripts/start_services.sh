#!/usr/bin/env bash
# restart_services.sh — safer, simplified

set -euo pipefail

### CONFIGURATION #############################################################
ENV_FILE="api/.env"
RUN_DIR="run"                 # where we keep *.pid
LOG_ROOT="logs"

### 1) Load environment vars so that configurations like FASTAPI_WORKERS are loaded #
set -a && . "$ENV_FILE" && set +a

# Get ENVIRONMENT for nginx config selection
ENVIRONMENT="${ENVIRONMENT:-staging}"

if [[ -z "${FASTAPI_PORT:-}" ]]; then
  echo "Error: FASTAPI_PORT environment variable is not set."
  exit 1
fi

if [[ -z "${FASTAPI_WORKERS:-}" ]]; then
  echo "Error: FASTAPI_WORKERS environment variable is not set."
  exit 1
fi

if [[ -z "${CONDA_ENV_NAME:-}" ]]; then
  echo "Error: CONDA_ENV_NAME environment variable is not set."
  exit 1
fi

# Default ARQ_WORKERS to 1 if not set
ARQ_WORKERS=${ARQ_WORKERS:-1}

# map "service name" → "command to run"
declare -A SERVICES=(
  [ari_manager]="python -m api.services.telephony.ari_manager"
  [campaign_orchestrator]="python -m api.services.campaign.campaign_orchestrator"
  [uvicorn]="uvicorn api.app:app --host 0.0.0.0 --port $FASTAPI_PORT --workers $FASTAPI_WORKERS"
)

# Add ARQ workers dynamically based on ARQ_WORKERS environment variable
for ((i=1; i<=ARQ_WORKERS; i++)); do
  SERVICES[arq$i]="python -m arq api.tasks.arq.WorkerSettings --custom-log-dict api.tasks.arq.LOG_CONFIG"
done

### 2) Activate conda #########################################################
# Source conda if not already available (needed when running from systemd)
if ! command -v conda &>/dev/null; then
  source /opt/conda/etc/profile.d/conda.sh
fi
eval "$(conda shell.bash hook)"
conda activate "$CONDA_ENV_NAME"

### 3) Stop old services (only via PID files) #################################
mkdir -p "$RUN_DIR"
for name in "${!SERVICES[@]}"; do
  pidfile="$RUN_DIR/$name.pid"
  if [[ -f $pidfile ]]; then
    oldpid=$(<"$pidfile")
    if kill -0 "$oldpid" 2>/dev/null; then
      echo "Stopping $name (PID $oldpid and its process group)…"
      # Kill the entire process group (negative PID)
      # First try SIGTERM
      kill -TERM -"$oldpid" 2>/dev/null || kill -TERM "$oldpid" 2>/dev/null || true
      sleep 4
      # If still running, use SIGKILL
      if kill -0 "$oldpid" 2>/dev/null; then
        echo "⚠️  $name did not exit cleanly, forcing stop..."
        kill -KILL -"$oldpid" 2>/dev/null || kill -KILL "$oldpid" 2>/dev/null || true
        sleep 1
      fi
    fi
    rm -f "$pidfile"
  else
    echo "No PID file for $name, skipping stop."
  fi
done

# Clean up any port tracking files for uvicorn
rm -f "$RUN_DIR/uvicorn.port" "$RUN_DIR/uvicorn_new.port" "$RUN_DIR/uvicorn_old.pid"


### 4) Run migrations #########################################################
alembic -c api/alembic.ini upgrade head

### 5) Prepare logs ###########################################################
timestamp=$(date '+%Y-%m-%d_%H-%M-%S')
LOG_DIR="$LOG_ROOT/$timestamp"
mkdir -p "$LOG_DIR"
# Create relative symlink
cd "$LOG_ROOT" && ln -sfn "$timestamp" latest && cd - >/dev/null

### 6) (Optional) Free FastAPI port ###########################################
FASTAPI_PORT=$FASTAPI_PORT
if command -v lsof &>/dev/null; then
  lsof -ti tcp:"$FASTAPI_PORT" | xargs -r kill -9 || true
fi

### 7) Start services #########################################################
# Export rotation settings for loguru (if using file logging)
export LOG_ROTATION_SIZE="${LOG_ROTATION_SIZE:-100 MB}"
export LOG_RETENTION="${LOG_RETENTION:-7 days}"
export LOG_COMPRESSION="${LOG_COMPRESSION:-gz}"

for name in "${!SERVICES[@]}"; do
  cmd=${SERVICES[$name]}
  echo "→ Starting $name with loguru rotation…"
  
  # Export LOG_FILE_PATH for this specific service
  export LOG_FILE_PATH="$LOG_DIR/$name.log"
  
  # Start in new process group with setsid
  # Each service gets its own LOG_FILE_PATH environment variable
  setsid nohup bash -c "LOG_FILE_PATH='$LOG_DIR/$name.log' $cmd" >/dev/null 2>&1 &
  
  # Get the PID of the setsid process
  pid=$!
  echo $pid >"$RUN_DIR/$name.pid"
  
  # For uvicorn, also save the port for rolling updates and update nginx
  if [[ "$name" == "uvicorn" ]]; then
    echo "$FASTAPI_PORT" >"$RUN_DIR/uvicorn.port"
    
    # Update nginx upstream configuration if nginx is installed
    if command -v nginx &>/dev/null && [[ -d /etc/nginx ]]; then
      # Determine which upstream config to update based on ENVIRONMENT
      if [[ "${ENVIRONMENT:-}" == "production" ]]; then
        NGINX_UPSTREAM_CONF="/etc/nginx/conf.d/dograh_production_upstream.conf"
        UPSTREAM_NAME="dograh_production_backend"
        echo "→ Updating PRODUCTION nginx upstream to port $FASTAPI_PORT…"
      else
        # Default to staging for any non-production environment
        NGINX_UPSTREAM_CONF="/etc/nginx/conf.d/dograh_staging_upstream.conf"
        UPSTREAM_NAME="dograh_staging_backend"
        echo "→ Updating STAGING nginx upstream to port $FASTAPI_PORT…"
      fi
      
      if [[ -w $(dirname "$NGINX_UPSTREAM_CONF") ]] || [[ $EUID -eq 0 ]]; then
        cat > "${NGINX_UPSTREAM_CONF}.tmp" <<EOF
# Auto-generated by start_services.sh for ${ENVIRONMENT:-staging}
# Last updated: $(date)
upstream ${UPSTREAM_NAME} {
    server 127.0.0.1:${FASTAPI_PORT} max_fails=3 fail_timeout=30s;
}
EOF
        # Atomic move (may need sudo)
        if [[ $EUID -eq 0 ]]; then
          mv "${NGINX_UPSTREAM_CONF}.tmp" "${NGINX_UPSTREAM_CONF}"
        else
          sudo mv "${NGINX_UPSTREAM_CONF}.tmp" "${NGINX_UPSTREAM_CONF}" 2>/dev/null || \
            echo "⚠️  Could not update nginx config (need sudo). Run: sudo $0"
        fi
        
        # Test and reload nginx if config was updated
        if [[ -f "$NGINX_UPSTREAM_CONF" ]]; then
          if nginx -t 2>/dev/null || sudo nginx -t 2>/dev/null; then
            echo "→ Reloading nginx…"
            nginx -s reload 2>/dev/null || sudo nginx -s reload 2>/dev/null || \
              echo "⚠️  Could not reload nginx (may need sudo)"
          else
            echo "⚠️  Nginx configuration test failed"
          fi
        fi
      else
        echo "⚠️  Cannot write to nginx config directory (need sudo privileges)"
        echo "   Run: sudo $0 to update nginx configuration"
      fi
    fi
  fi
done
disown -a

### 8) Summary #################################################################
echo
echo "──────────────────────────────────────────────────"
for name in "${!SERVICES[@]}"; do
  pid=$(<"$RUN_DIR/$name.pid")
  echo "✓ $name (PID $pid) → $LOG_DIR/$name.log"
done
echo "  Rotation: ${LOG_ROTATION_SIZE:-100 MB}"
echo "  Retention: ${LOG_RETENTION:-7 days}"
echo "  Compression: ${LOG_COMPRESSION:-gz}"
echo "Logs: tail -f $LOG_DIR/*.log"
echo "Rotated logs: ls $LOG_DIR/*.log.*"
echo "To stop: run this script again or kill -TERM -<PID> for process groups"
echo "──────────────────────────────────────────────────"
