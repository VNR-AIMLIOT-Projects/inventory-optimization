#!/usr/bin/env bash
# =====================================================================
# Replenix Monitoring Stack — One-Shot Install Script
# Region: BLR1 | Cluster: replenix-cluster | K8s: 1.36.0-do.1
#
# Usage:
#   chmod +x k8s/monitoring/install.sh
#   ./k8s/monitoring/install.sh
#
# Prerequisites:
#   - doctl authenticated (doctl auth init)
#   - kubectl context set to replenix-cluster
#   - helm >= 3.12 installed
#   - DO Spaces bucket "replenix-metrics-prod" created in BLR1
#     (doctl spaces create replenix-metrics-prod --region blr1)
# =====================================================================
set -euo pipefail

NAMESPACE="monitoring"
CHART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/helm" && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
step() { echo -e "\n${CYAN}==> [$1] $2${NC}"; }
ok()   { echo -e "${GREEN}    ✓ $1${NC}"; }
warn() { echo -e "${YELLOW}    ⚠ $1${NC}"; }

# ─── Preflight checks ────────────────────────────────────────────────
step "0/8" "Preflight checks..."
command -v kubectl &>/dev/null || { echo -e "${RED}kubectl not found. Install: brew install kubectl${NC}"; exit 1; }
command -v helm    &>/dev/null || { echo -e "${RED}helm not found. Install: brew install helm${NC}"; exit 1; }
command -v openssl &>/dev/null || { echo -e "${RED}openssl not found.${NC}"; exit 1; }

CURRENT_CTX=$(kubectl config current-context)
echo "    Current kubectl context: ${CURRENT_CTX}"
if [[ "$CURRENT_CTX" != *"replenix"* ]]; then
  warn "Context doesn't contain 'replenix'. Are you on the right cluster?"
  read -rp "    Continue anyway? (y/N): " CONFIRM
  [[ "$CONFIRM" =~ ^[Yy]$ ]] || exit 1
fi
ok "Preflight passed"

# ─── Step 1: Namespace ───────────────────────────────────────────────
step "1/8" "Creating monitoring namespace..."
kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
ok "Namespace: monitoring"

# ─── Step 2: Helm repos ──────────────────────────────────────────────
step "2/8" "Adding Helm repositories..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts --force-update
helm repo add bitnami             https://charts.bitnami.com/bitnami                  --force-update
helm repo add grafana             https://grafana.github.io/helm-charts               --force-update
helm repo update
helm dependency update "$CHART_DIR"
ok "Helm repos ready"

# ─── Step 3: Thanos objstore secret ──────────────────────────────────
step "3/8" "Creating DO Spaces secret (thanos-objstore-secret)..."
if kubectl get secret thanos-objstore-secret -n "$NAMESPACE" &>/dev/null; then
  warn "Secret already exists. Skipping. Delete it first to re-create:"
  warn "  kubectl delete secret thanos-objstore-secret -n monitoring"
else
  echo "    Enter your DigitalOcean Spaces credentials for SFO3."
  echo "    (Generate at: cloud.digitalocean.com/account/api/tokens → Spaces Keys)"
  read -rsp "    Spaces Access Key: " SPACES_KEY; echo
  read -rsp "    Spaces Secret Key: " SPACES_SECRET; echo

  OBJSTORE_YAML=$(cat <<EOF
type: S3
config:
  bucket: replenix-metrics-prod
  region: sfo3
  endpoint: sfo3.digitaloceanspaces.com
  access_key: ${SPACES_KEY}
  secret_key: ${SPACES_SECRET}
  insecure: false
  signature_version2: false
  http_config:
    idle_conn_timeout: 90s
    response_header_timeout: 2m
  trace:
    enable: false
EOF
)
  kubectl create secret generic thanos-objstore-secret \
    --namespace "$NAMESPACE" \
    --from-literal=thanos.yaml="$OBJSTORE_YAML" \
    --dry-run=client -o yaml | kubectl apply -f -
  unset SPACES_KEY SPACES_SECRET OBJSTORE_YAML
  ok "thanos-objstore-secret created"
fi

# ─── Step 4: Grafana admin secret ────────────────────────────────────
step "4/8" "Creating Grafana admin secret..."
if kubectl get secret grafana-admin-secret -n "$NAMESPACE" &>/dev/null; then
  warn "grafana-admin-secret already exists. Skipping."
else
  GRAFANA_PASS=$(openssl rand -base64 24)
  kubectl create secret generic grafana-admin-secret \
    --namespace "$NAMESPACE" \
    --from-literal=admin-user=admin \
    --from-literal=admin-password="$GRAFANA_PASS" \
    --dry-run=client -o yaml | kubectl apply -f -
  echo ""
  echo -e "  ${GREEN}╔══════════════════════════════════════════════╗${NC}"
  echo -e "  ${GREEN}║  📊 Grafana Admin Credentials (SAVE THESE)  ║${NC}"
  echo -e "  ${GREEN}║  URL:      https://grafana.replenix.app      ║${NC}"
  echo -e "  ${GREEN}║  Username: admin                             ║${NC}"
  echo -e "  ${GREEN}║  Password: ${GRAFANA_PASS}  ║${NC}"
  echo -e "  ${GREEN}╚══════════════════════════════════════════════╝${NC}"
  echo ""
  unset GRAFANA_PASS
fi

# ─── Step 5: kube-prometheus-stack ───────────────────────────────────
step "5/8" "Installing kube-prometheus-stack (Prometheus + Thanos sidecars + AlertManager)..."
helm upgrade --install replenix-prometheus prometheus-community/kube-prometheus-stack \
  --namespace "$NAMESPACE" \
  --values "$CHART_DIR/values.yaml" \
  --timeout 15m \
  --wait
ok "kube-prometheus-stack installed"

# ─── Step 6: Thanos ──────────────────────────────────────────────────
step "6/8" "Installing Thanos (Store Gateway + Query + Compact)..."
helm upgrade --install replenix-thanos bitnami/thanos \
  --namespace "$NAMESPACE" \
  --values "$CHART_DIR/thanos-values.yaml" \
  --timeout 10m \
  --wait
ok "Thanos installed"

# ─── Step 7: Grafana ─────────────────────────────────────────────────
step "7/8" "Installing Grafana with Replenix dashboards..."
helm upgrade --install replenix-grafana grafana/grafana \
  --namespace "$NAMESPACE" \
  --values "$CHART_DIR/values.yaml" \
  --timeout 5m \
  --wait

# Apply dashboard ConfigMaps
kubectl apply -f "$CHART_DIR/templates/dashboards-configmap.yaml"
ok "Grafana installed + dashboards provisioned"

# ─── Step 8: Verify ──────────────────────────────────────────────────
step "8/8" "Verifying installation..."
echo ""
echo "    Pods in monitoring namespace:"
kubectl get pods -n "$NAMESPACE" --no-headers | \
  awk '{status=$3; name=$1; print "    " (status=="Running" ? "\033[0;32m✓\033[0m" : "\033[0;31m✗\033[0m") " " name " [" status "]"}'

echo ""
echo -e "${GREEN}✅ Replenix monitoring stack installed!${NC}"
echo ""
echo "    Next steps:"
echo "    1. Add Cloudflare DNS A record: grafana.replenix.app → $(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo '<load-balancer-ip>')"
echo "    2. Wait 2–3 min for cert-manager to issue TLS cert"
echo "    3. Open https://grafana.replenix.app (username: admin)"
echo "    4. Verify Thanos Query: kubectl port-forward svc/replenix-thanos-query 9090:9090 -n monitoring"
echo "       then: curl http://localhost:9090/api/v1/query?query=up"
echo ""
echo "    Alert emails:"
echo "    → sujaynsv@gmail.com"
echo "    → rishitsura@gmail.com"
echo "    (via AlertManager → /api/webhooks/alerts → Resend)"
