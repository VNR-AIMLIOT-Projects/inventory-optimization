#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.prod}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
: "${GCP_ZONE:?GCP_ZONE is required}"
: "${VM_NAME:?VM_NAME is required}"

gcloud config set project "$GCP_PROJECT_ID"

VM_HOME_CMD='echo $HOME'
REMOTE_HOME=$(gcloud compute ssh "$VM_NAME" --zone "$GCP_ZONE" --command "$VM_HOME_CMD")
REMOTE_APP_DIR="$REMOTE_HOME/inventory-optimization"

# Package current workspace while excluding large local artifacts.
TMP_ARCHIVE="$(mktemp /tmp/inventory-optimization-src.XXXXXX.tar.gz)"
trap 'rm -f "$TMP_ARCHIVE"' EXIT

tar -czf "$TMP_ARCHIVE" \
  --exclude='.git' \
  --exclude='Backend-RL/venv' \
  --exclude='Frontend/node_modules' \
  --exclude='**/__pycache__' \
  -C "$ROOT_DIR" .

gcloud compute scp "$TMP_ARCHIVE" "$VM_NAME:$REMOTE_HOME/inventory-optimization-src.tar.gz" --zone "$GCP_ZONE"
gcloud compute ssh "$VM_NAME" --zone "$GCP_ZONE" --command "mkdir -p $REMOTE_APP_DIR && tar -xzf $REMOTE_HOME/inventory-optimization-src.tar.gz -C $REMOTE_APP_DIR"
gcloud compute scp "$ENV_FILE" "$VM_NAME:$REMOTE_APP_DIR/.env.prod" --zone "$GCP_ZONE"

REMOTE_DEPLOY_CMD="cd $REMOTE_APP_DIR && docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build"
gcloud compute ssh "$VM_NAME" --zone "$GCP_ZONE" --command "$REMOTE_DEPLOY_CMD"

echo "Deployment complete."
