#!/usr/bin/env bash
# start_services.sh

set -e  # Exit on error

### CONFIGURATION #############################################################
ENV_FILE="api/.env"
RUN_DIR="run"                 # where we keep *.pid
BASE_LOG_DIR="/home/ubuntu/dograh/logs"           # base logs directory
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR="$BASE_LOG_DIR/$TIMESTAMP"  # timestamped log directory
LATEST_LINK="$BASE_LOG_DIR/latest"  # symlink to latest logs
VENV_PATH="/home/ubuntu/dograh/venv"
ARQ_WORKERS=${ARQ_WORKERS:-1}

# Log startup
echo "Starting Dograh Services at $(date)"

### 1) Load environment vars so that configurations like FASTAPI_WORKERS are loaded
set -a && . "$ENV_FILE" && set +a

cd /home/ubuntu/dograh/app

if [[ -z "${FASTAPI_PORT:-}" ]]; then
  echo "Error: FASTAPI_PORT environment variable is not set."
  exit 1
fi

if [[ -z "${FASTAPI_WORKERS:-}" ]]; then
  echo "Error: FASTAPI_WORKERS environment variable is not set."
  exit 1
fi

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

### 2) Activate virtual environment #########################################
source ${VENV_PATH}/bin/activate

### 3) Stop old services (only via PID files) #################################
mkdir -p "$RUN_DIR"
for name in "${!SERVICES[@]}"; do
  pidfile="$RUN_DIR/$name.pid"
  if [[ -f $pidfile ]]; then
    oldpid=$(<"$pidfile")
    if kill -0 "$oldpid"; then
      echo "Stopping $name (PID $oldpid and its process group)…"
      # Kill the entire process group (negative PID)
      # First try SIGTERM
      kill -TERM -"$oldpid" || kill -TERM "$oldpid" || true
      sleep 4
      # If still running, use SIGKILL
      if kill -0 "$oldpid"; then
        echo "⚠️  $name did not exit cleanly, forcing stop..."
        kill -KILL -"$oldpid" || kill -KILL "$oldpid" || true
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
mkdir -p "$BASE_LOG_DIR"
mkdir -p "$LOG_DIR"

# Remove old symlink if it exists and create new one
if [[ -L "$LATEST_LINK" ]]; then
  rm "$LATEST_LINK"
fi
ln -s "$TIMESTAMP" "$LATEST_LINK"

echo "Log directory: $LOG_DIR"
echo "Latest symlink: $LATEST_LINK -> $TIMESTAMP"

### 7) Start services #########################################################
for name in "${!SERVICES[@]}"; do
  cmd=${SERVICES[$name]}
  echo "→ Starting $name"
  
  # Export LOG_FILE_PATH for this specific service
  export LOG_FILE_PATH="$LOG_DIR/$name.log"
  
  # Start in new process group with setsid
  # Each service gets its own LOG_FILE_PATH environment variable
  setsid nohup bash -c "LOG_FILE_PATH='$LOG_DIR/$name.log' $cmd" >/dev/null 2>&1 &
  
  # Get the PID of the setsid process
  pid=$!
  echo $pid >"$RUN_DIR/$name.pid"
  
  # For uvicorn, also save the port for rolling updates
  if [[ "$name" == "uvicorn" ]]; then
    echo "$FASTAPI_PORT" >"$RUN_DIR/uvicorn.port"
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
