#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.prod}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE"
  echo "Copy .env.prod.example to .env.prod and fill it first."
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_FILE"

: "${GCP_PROJECT_ID:?GCP_PROJECT_ID is required}"
: "${GCP_ZONE:?GCP_ZONE is required}"
: "${VM_NAME:?VM_NAME is required}"
: "${MACHINE_TYPE:?MACHINE_TYPE is required}"
: "${GPU_TYPE:?GPU_TYPE is required}"
: "${GPU_COUNT:?GPU_COUNT is required}"
: "${BOOT_DISK_SIZE_GB:?BOOT_DISK_SIZE_GB is required}"

NETWORK="${NETWORK:-default}"
SUBNET="${SUBNET:-default}"

gcloud config set project "$GCP_PROJECT_ID"

gcloud compute instances create "$VM_NAME" \
  --zone "$GCP_ZONE" \
  --machine-type "$MACHINE_TYPE" \
  --boot-disk-size "${BOOT_DISK_SIZE_GB}GB" \
  --maintenance-policy TERMINATE \
  --restart-on-failure \
  --accelerator "type=$GPU_TYPE,count=$GPU_COUNT" \
  --image-family ubuntu-2204-lts \
  --image-project ubuntu-os-cloud \
  --network "$NETWORK" \
  --subnet "$SUBNET" \
  --scopes cloud-platform \
  --tags inventory-app,inventory-gpu

echo "VM created: $VM_NAME"
echo "Next: run scripts/gcp/setup_vm.sh via SSH on the VM."
