# Replenix Deployment Guide

Replenix follows a structured deployment pipeline across three distinct environments: **Dev**, **Preprod**, and **Prod**. This document explains how code moves from a developer's laptop to live production.

---

## 1. Dev Environment (Local)

The **Dev** environment is exclusively for local development and testing. 

- **Infrastructure:** Docker Desktop (via `docker-compose.yml`) or bare-metal execution.
- **Trigger:** Manual execution by the developer (`docker compose up`).
- **Secrets:** Managed manually via `.env` files.
- **Goal:** Fast, iterative development with hot-reloading for both the Frontend and Backend.

*See `developer_guide.md` for complete instructions on running the Dev environment.*

---

## 2. Preprod Environment (Staging)

The **Preprod** environment serves as the staging grounds. It is an exact replica of production, running on the same DigitalOcean Kubernetes cluster, but completely isolated within the `replenix-preprod` namespace.

- **Infrastructure:** DigitalOcean Kubernetes (DOKS).
- **Namespaces:** `replenix-preprod`.
- **URLs:** 
  - `https://preprod.replenix.app`
  - `https://api-preprod.replenix.app`
- **Goal:** Integration testing, QA, and catching configuration errors before they affect live users.

### CI/CD Pipeline (Preprod)

The automated testing and deployment pipeline is defined in `.github/workflows/ci-cd.yml` and is triggered **automatically** whenever code is pushed.

#### Pipeline Steps:
1. **Automated Testing:** Pytest and Playwright E2E tests are executed first. Deployment is blocked if tests fail.
2. **Build & Push:** Builds the Docker images for the Frontend, Backend, and RL Worker, tagging them with the current Git commit SHA. The images are pushed to the DigitalOcean Container Registry (DOCR).
3. **Setup Kustomize / Kubectl:** Authenticates with the DigitalOcean cluster.
4. **Deploy to Cluster:** Uses `sed` to dynamically replace image tags in the Kubernetes manifests (`k8s/*/deployment.yaml`) and applies them to the `replenix-preprod` namespace.
5. **Secret Injection:** Dynamically generates a base64-encoded `replenix-secrets` based on the GitHub Actions secrets and applies it.
6. **Rollout Verification:** Pauses the pipeline to monitor `kubectl rollout status`.
7. **Smoke Test:** Executes internal curl commands against the deployed `api-preprod` endpoints. To bypass global DNS propagation delays, the smoke test uses the `--resolve` flag to query the NGINX Ingress internal IP directly.
8. **Automated Rollback:** If the rollout times out or the smoke test fails, the pipeline executes `kubectl rollout undo` to revert the deployment safely.

---

## 3. Prod Environment (Production)

The **Prod** environment is the live, public-facing application.

- **Infrastructure:** DigitalOcean Kubernetes (DOKS).
- **Namespaces:** `replenix-prod`.
- **URLs:** 
  - `https://www.replenix.app`
  - `https://api.replenix.app`
- **Goal:** Stable, secure, and auto-scaling execution for end users.

### CI/CD Pipeline (Prod)

The Prod pipeline uses the exact same unified GitHub Action (`.github/workflows/ci-cd.yml`) but dynamically adjusts when triggered by pushes to the `prod` branch.

The pipeline automatically detects the branch name (`prod`) and adjusts the deployment variables accordingly:
- `NS=replenix-prod`
- Targets the `www.replenix.app` domains during the Smoke Test.

---

## Infrastructure Security & Ingress

### Zero-Trust Network Policies
Both `preprod` and `prod` namespaces are secured using strict **NetworkPolicies**. A `default-deny-all` policy blocks all traffic. Specific policies are explicitly defined to allow:
- NGINX Ingress to reach the Frontend/Backend.
- Backend and RL Workers to reach PostgreSQL and RabbitMQ.
- `cert-manager` HTTP-01 solvers to be reached by NGINX Ingress (required for Let's Encrypt validation).
- `allow-prometheus-scrape` to permit the Prometheus Operator (running in the `monitoring` namespace) to scrape metrics from the application pods.

### TLS & SSL Certificates (Let's Encrypt)
All production and preproduction traffic is fully secured via HTTPS.
- We use **cert-manager** inside the cluster to automatically provision TLS certificates.
- The `k8s/ingress/ingress.yaml` file defines the `ClusterIssuer` (Let's Encrypt) and requests the certificates.
- When a new environment is spun up, cert-manager automatically creates an HTTP-01 challenge, proves domain ownership, and secures the ingress routes.

### Observability Deployment
The monitoring stack runs in the `monitoring` namespace.
- **Grafana & Prometheus** are deployed using the `kube-prometheus-stack` Helm chart.
- Custom dashboards are provisioned dynamically via a `ConfigMap` managed in `k8s/monitoring/helm/templates/dashboards-configmap.yaml`.
- Ensure you apply the generic scrape configuration (`scrape-config-annotations.yaml`) to allow Prometheus to dynamically discover targets based on `prometheus.io/scrape: "true"` annotations.

---

## Manual Operations & Troubleshooting

If you ever need to manually intervene in the cluster:

### Checking Logs
```bash
# Get logs for the backend API
kubectl logs -l app=replenix-backend -n replenix-preprod

# Get logs for the RL Worker
kubectl logs -l app=replenix-rl-worker -n replenix-preprod
```

### Restarting Deployments
If a deployment gets stuck, you can force a rolling restart:
```bash
kubectl rollout restart deployment backend -n replenix-preprod
```

### Investigating TLS/SSL Issues
If the green padlock isn't showing up, check the cert-manager challenges:
```bash
kubectl get challenge,certificate -n replenix-preprod
kubectl describe challenge <challenge-name> -n replenix-preprod
```
