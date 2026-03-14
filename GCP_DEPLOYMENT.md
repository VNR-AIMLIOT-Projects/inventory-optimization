# GCP Deployment Guide (prod branch)

This guide deploys the full stack on a single GPU VM using files from `prod` branch.

## 1) Prepare local files

1. Ensure you are on `prod` branch.
2. Copy `.env.prod.example` to `.env.prod` and fill all values.
3. Install Google Cloud SDK locally and authenticate:

```bash
gcloud auth login
gcloud auth application-default login
```

## 2) GCP Console setup

### A. Select or create project

- Open GCP Console.
- Create/select your project.
- Make sure billing is enabled.

### B. Enable required APIs

In "APIs & Services > Library", enable:
- Compute Engine API
- Cloud Resource Manager API
- IAM API

### C. Create firewall rules

In "VPC network > Firewall", create inbound allow rules for target tag `inventory-app`:
- TCP 3000 (frontend)
- TCP 8000 (backend)
- Optional: TCP 15672 (RabbitMQ UI)

Keep 5432 and 5672 closed to the public internet.

## 3) Create GPU VM

Use helper script (recommended):

```bash
./scripts/gcp/create_gpu_vm.sh .env.prod
```

Console equivalent settings:
- Machine type: `n1-standard-4` (or better)
- GPU: `nvidia-tesla-t4`, count `1`
- Boot disk: Ubuntu 22.04 LTS, at least 100 GB
- Availability policy: On host maintenance = Terminate
- Firewall tags: `inventory-app`, `inventory-gpu`

## 4) Install Docker + NVIDIA stack on VM

From your local machine, run the bootstrap helper:

```bash
./scripts/gcp/bootstrap_vm.sh .env.prod
gcloud compute ssh "$VM_NAME" --zone "$GCP_ZONE" --command 'sudo reboot'
```

If you prefer GCP Console directly: open VM > SSH, then run `~/setup_vm.sh` and reboot.

After reboot, reconnect and verify GPU:

```bash
nvidia-smi
```

## 5) Deploy the application stack

From your local machine:

```bash
./scripts/gcp/deploy_stack.sh .env.prod
```

This uploads the repo and runs:

```bash
docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## 6) Validate deployment

On VM:

```bash
docker ps
docker logs -f inventory-optimization-rl-worker-1
```

From browser:
- `http://<VM_EXTERNAL_IP>:3000` for frontend
- `http://<VM_EXTERNAL_IP>:8000/docs` for backend docs

GPU validation inside worker container:

```bash
docker exec -it inventory-optimization-rl-worker-1 python -c "import torch; print('CUDA:', torch.cuda.is_available(), 'DEVICE:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

## 7) Cost control (important)

Stop VM whenever not training:

```bash
./scripts/gcp/manage_vm.sh stop .env.prod
```

Start again when needed:

```bash
./scripts/gcp/manage_vm.sh start .env.prod
```

Check status:

```bash
./scripts/gcp/manage_vm.sh status .env.prod
```

Also create budget alerts in Billing at 50%, 75%, 90%.

## 8) Recommended operations model

- Keep `WORKER_REPLICAS=1` for one T4 initially.
- Benchmark training runtime.
- Only increase worker replicas if GPU utilization is low and queue is long.
- Keep DB and RabbitMQ private (no public inbound rules).
