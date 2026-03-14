#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${2:-$ROOT_DIR/.env.prod}"
ACTION="${1:-}"

if [[ -z "$ACTION" ]]; then
  echo "Usage: $0 <start|stop|status> [path-to-env-file]"
  exit 1
fi

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

case "$ACTION" in
  start)
    gcloud compute instances start "$VM_NAME" --zone "$GCP_ZONE"
    ;;
  stop)
    gcloud compute instances stop "$VM_NAME" --zone "$GCP_ZONE"
    ;;
  status)
    gcloud compute instances describe "$VM_NAME" --zone "$GCP_ZONE" --format='value(status)'
    ;;
  *)
    echo "Invalid action: $ACTION"
    echo "Usage: $0 <start|stop|status> [path-to-env-file]"
    exit 1
    ;;
esac
