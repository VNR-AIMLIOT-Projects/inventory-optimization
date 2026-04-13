# Replenix - Intelligent Inventory Optimization (Production)

Welcome to the production repository for **Replenix**, a reinforcement learning-powered supply chain dynamics optimization engine.

**🌐 Production Deployment:** [https://www.replenix.app/](https://www.replenix.app/)

## Overview
Replenix is built to streamline inventory planning by providing an end-to-end pipeline that handles Data Upload, Scenario Modification, Data Preview, Reinforcement Learning (DQN) Training, Performance Evaluation, and final Deployment Simulation. This architecture enables dynamic response models to mitigate Bullwhip effects and stock-out risks across intricate supply chains.

## Production Architecture
This branch (`prod`) is configured with the infrastructure necessary for staging and provisioning. 

- **Frontend:** React, Tailwind CSS, Shadcn UI overlays, and Vite, deployed behind an NGINX proxy supporting SSL/HTTPS.
- **Backend/RL Engine:** FastAPI + Python RL worker pool, connecting symmetrically to persistent PostgreSQL volumes.
- **Orchestration:** Managed via Docker Compose (`docker-compose.yml` + `docker-compose.prod.yml`).
- **CI/CD:** Automated DigitalOcean deployments configured via GitHub Actions upon merges to `prod` branch.
- **Notifications:** Configured telemetry notifies maintaining developers upon execution status updates.

## Environment Layout
Make sure your deployment droplet securely injects `.env.prod`. This branch deliberately scrubs unneeded or insecure artifacts and relies exclusively on environment-injected parameters provided during the `docker compose --env-file .env.deploy` deployment step.

## Pipeline Integration
See `RELEASES.md` attached in this repository for an ongoing record of implemented stages, features, and fixes in sequential release clusters.
