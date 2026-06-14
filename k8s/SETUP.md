# Replenix — Kubernetes Deployment Setup Guide

This guide walks you through setting up the new Kubernetes infrastructure from scratch.

## Prerequisites

- DigitalOcean account with GitHub Student Pack credit ($200)
- `doctl` CLI installed: `brew install doctl`
- `kubectl` installed: `brew install kubectl`
- Domain `replenix.app` pointed to Cloudflare (free)

---

## Step 1 — Create the DOKS Cluster

```bash
# Authenticate with DigitalOcean
doctl auth init

# Create a 2-node cluster (cheapest viable setup)
doctl kubernetes cluster create replenix-cluster \
  --region blr1 \
  --node-pool "name=replenix-pool;size=s-2vcpu-4gb;count=2" \
  --version latest \
  --wait

# Get your cluster ID (needed for GitHub Secrets)
doctl kubernetes cluster list
# Copy the cluster ID (looks like: abc12345-xxxx-xxxx-xxxx-xxxxxxxxxxxx)

# Configure kubectl locally
doctl kubernetes cluster kubeconfig save replenix-cluster
```

---

## Step 2 — Install Required Helm Charts

```bash
# Add Helm repos
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo add jetstack https://charts.jetstack.io
helm repo add kedacore https://kedacore.github.io/charts
helm repo update

# 1. Install Nginx Ingress Controller
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace \
  --set controller.service.type=LoadBalancer

# 2. Install cert-manager (free TLS from Let's Encrypt)
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager --create-namespace \
  --set installCRDs=true

# 3. Install KEDA (auto-scaling workers by queue depth — free)
helm install keda kedacore/keda \
  --namespace keda --create-namespace

# Wait for ingress to get an external IP (takes ~2 mins)
kubectl get svc -n ingress-nginx
# Copy the EXTERNAL-IP — this is your load balancer IP
```

---

## Step 3 — Configure Cloudflare DNS

Go to Cloudflare → replenix.app → DNS:

| Type | Name | Value | Proxy |
|------|------|-------|-------|
| A | `@` | `<LOAD_BALANCER_IP>` | ✅ (orange cloud) |
| A | `api` | `<LOAD_BALANCER_IP>` | ✅ |
| A | `preprod` | `<LOAD_BALANCER_IP>` | ✅ |
| A | `api-preprod` | `<LOAD_BALANCER_IP>` | ✅ |
| CNAME | `www` | `replenix.app` | ✅ |

Enable in Cloudflare:
- SSL/TLS → Full (strict)
- Always Use HTTPS → On
- HSTS → Enable (max-age 1 year)

---

## Step 4 — Set GitHub Secrets

Go to: **GitHub → inventory-optimization → Settings → Secrets → Actions**

Add these secrets:

| Secret Name | Value | Notes |
|---|---|---|
| `DO_API_TOKEN` | Your DigitalOcean API token | Create at: cloud.digitalocean.com/account/api/tokens |
| `DO_CLUSTER_ID` | DOKS cluster ID from Step 1 | e.g. `abc12345-xxxx-...` |
| `DOCKER_USERNAME` | Your Docker Hub username | e.g. `sujaynimmagadda` |
| `DOCKER_PASSWORD` | Docker Hub access token | Create at: hub.docker.com/settings/security |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:port/inventory` |
| `RABBITMQ_DEFAULT_USER` | RabbitMQ username | Use a strong random string |
| `RABBITMQ_DEFAULT_PASS` | RabbitMQ password | Use a strong random string |
| `GROQ_API_KEY` | Your Groq API key | From console.groq.com |
| `RESEND_API_KEY` | Your Resend API key | From resend.com |
| `SESSION_SECRET` | Random 32-byte string | Run: `openssl rand -base64 32` |

---

## Step 5 — Bootstrap Kubernetes Namespaces

```bash
# Create namespaces
kubectl apply -f k8s/namespace/namespace.yaml

# Apply network policies
kubectl apply -f k8s/network-policy/network-policy.yaml

# Apply cert-manager issuers
kubectl apply -f k8s/ingress/ingress.yaml

# Deploy RabbitMQ to both namespaces
kubectl apply -f k8s/rabbitmq/statefulset.yaml -n replenix-prod
kubectl apply -f k8s/rabbitmq/statefulset.yaml -n replenix-preprod
```

---

## Step 6 — First Deploy

Push to `dev` branch → auto-deploys to **preprod** (preprod.replenix.app)
Push to `prod` branch → auto-deploys to **production** (replenix.app)

```bash
git push origin feature/kubernetes-infra
# Create PR: feature/kubernetes-infra → dev
# Merge → triggers preprod deploy
# Test preprod.replenix.app
# Create PR: dev → prod
# Merge → triggers production deploy
```

---

## Cost Breakdown (with $200 Student Credit)

| Resource | Monthly Cost |
|---|---|
| DOKS: 2× s-2vcpu-4gb nodes | $48/mo |
| Load Balancer (auto-provisioned) | $12/mo |
| Block Storage: 10GB backend + 5GB RabbitMQ | ~$2/mo |
| **Total** | **~$62/mo** |
| **With $200 credit** | **~3 months free** |

> PostgreSQL runs as a **StatefulSet in the cluster** (free). If you later want DigitalOcean Managed PostgreSQL for automated backups, that's +$15/mo.

---

## Pre/Prod Environment Comparison

| Feature | preprod.replenix.app | replenix.app |
|---|---|---|
| Triggers from | `dev` branch | `prod` branch |
| Namespace | `replenix-preprod` | `replenix-prod` |
| TLS cert | Let's Encrypt staging | Let's Encrypt production |
| Replicas | 1 per service | 2 per service |
| RL Workers | 1-2 (KEDA) | 1-4 (KEDA) |
| Same cluster? | ✅ Yes (no extra cost!) | ✅ Yes |
| Shares same DB? | ❌ No (separate secrets) | ❌ No |
