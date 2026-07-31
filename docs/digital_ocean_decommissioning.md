# DigitalOcean Infrastructure Decommissioning

**Date:** July 31, 2026

## Overview
This document records the decommissioning of the DigitalOcean (DO) resources that previously hosted the Replenix application. 
The resources were decommissioned to avoid billing charges following the expiration of GitHub Student Pack free tier credits.

The Kubernetes manifests (`k8s/` directory) and CI/CD pipelines (`.github/workflows/ci-cd.yml`) remain in the repository to serve as a reference and to allow a seamless transition to another Kubernetes-compatible cloud provider (e.g., Oracle Cloud Always Free Tier, AWS, or GCP) in the future.

## Decommissioned Resources
The following billable resources were permanently destroyed via the DigitalOcean API (`doctl`):

1. **Kubernetes Cluster (DOKS)**
   - **Name:** `replenix-cluster`
   - **Region:** `blr1`
   - **Nodes:** 3 Worker Nodes (`replenix-pool-3u49xi`, `replenix-pool-3u49xv`, `replenix-pool-37c1hm`)
   - *Action taken:* Cluster deleted, nodes destroyed.

2. **Standalone Droplets**
   - **Name:** `invnentory-prod`
   - **IP:** `139.59.67.247`
   - *Action taken:* Droplet force deleted.

3. **Load Balancers**
   - **Name:** `replenix-lb`
   - **IP:** `68.183.247.90`
   - *Action taken:* Deleted successfully.

4. **Block Storage Volumes**
   - 11 Persistent Volume Claims (PVCs) totaling ~99 GB attached to the cluster for PostgreSQL, Redis, and RabbitMQ state.
   - *Action taken:* All volumes detached and permanently deleted.

5. **DNS / Domains**
   - **Domain:** `replenix.app`
   - *Action taken:* DO DNS management records removed.

## Next Steps for Infrastructure
Since the Kubernetes manifests (`k8s/`) are preserved:
- **Zero-Code K8s Migration:** The infrastructure can be spun up on any standard Kubernetes cluster (like K3s, MicroK8s, or EKS) simply by applying the manifests. 
- **PaaS Migration (Alternative):** If Kubernetes management becomes too high overhead, the architecture can be decoupled into managed services (Vercel for Frontend, Render/Koyeb for Backend, Supabase for PostgreSQL).
- **CI/CD Updates:** Remember to update `DO_API_TOKEN` and Kubernetes contexts in `.github/workflows/ci-cd.yml` if you decide to deploy to a different cloud provider using GitHub Actions.
