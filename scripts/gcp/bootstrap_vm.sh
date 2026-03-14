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

gcloud compute scp "$ROOT_DIR/scripts/gcp/setup_vm.sh" "$VM_NAME:~/setup_vm.sh" --zone "$GCP_ZONE"
gcloud compute ssh "$VM_NAME" --zone "$GCP_ZONE" --command "chmod +x ~/setup_vm.sh && ~/setup_vm.sh"

echo "Bootstrap complete. Reboot the VM now:"
echo "gcloud compute ssh $VM_NAME --zone $GCP_ZONE --command 'sudo reboot'"
