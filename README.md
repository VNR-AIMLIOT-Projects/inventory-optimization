# Replenix: Intelligent Inventory Optimization

Replenix is an advanced, Reinforcement Learning (RL) powered supply chain dynamics optimization engine. It is designed to mitigate the "Bullwhip Effect" and optimize inventory planning across complex, multi-echelon supply chains.

## Live Environments

- Production: https://www.replenix.app/
- Preprod (Staging): https://preprod.replenix.app/

## Architecture Overview

Replenix utilizes a robust, horizontally scalable microservices architecture designed to handle computationally heavy reinforcement learning tasks alongside a responsive web application. 

The system consists of the following isolated services:
1. Frontend Application (React / Next.js): Provides the interactive modeling dashboard for users to configure supply chain scenarios and visualize results.
2. Backend API (FastAPI): Manages data flow, user authentication, and orchestrates training jobs.
3. Message Broker (RabbitMQ): Handles the queuing of intensive RL training tasks, ensuring decoupling of the API from the computationally heavy processing layers.
4. Reinforcement Learning Workers (Python / PyTorch): Asynchronous Deep Q-Network (DQN) agents that process jobs from RabbitMQ, simulating demand and supply dynamics.
5. Primary Database (PostgreSQL): Securely stores user sessions, inventory parameters, and aggregated metrics.
6. Application Cache (Redis): Accelerates API response times by caching heavy historical and demand analytics payloads.
7. Observability Stack (Prometheus, Grafana, Thanos): Provides high-availability metrics collection, long-term storage, and interactive RED (Rate, Errors, Duration) dashboards.

The entire architecture is containerized and orchestrated via Kubernetes, utilizing strict default-deny NetworkPolicies to enforce zero-trust security between the microservices. Traffic is routed via an NGINX Ingress Controller with automated Let's Encrypt TLS certificate provisioning.

## Environment Separation

The repository strictly enforces environment separation to maintain code stability and secure deployment pipelines.

### Development Environment (Local)
The `dev` branch is reserved exclusively for local, stable development. It does not contain Kubernetes deployment manifests or cloud-specific GitHub Actions. Local development is orchestrated using Docker Compose, allowing engineers to spin up the entire Replenix stack instantly on their local machines. Configuration files for local setup are maintained in the `setup/` directory.

### Pre-Production Environment (Staging)
The `preprod` branch acts as the final validation stage before production. Pushes to this branch trigger automated GitHub Actions that build Docker images and deploy them to the `replenix-preprod` namespace on our DigitalOcean Kubernetes cluster. This environment mirrors production identically, allowing for rigorous integration testing and quality assurance without affecting live users.

### Production Environment
The `prod` branch is the live, user-facing application. Code is merged into `prod` only after passing all smoke tests in the Pre-Production environment. Pushes to this branch trigger a zero-downtime rolling update to the `replenix-prod` namespace, dynamically scaling RL Workers via KEDA (Kubernetes Event-Driven Autoscaling) based on real-time RabbitMQ queue depth.

## Codebase Documentation

Extensive documentation covering every aspect of the platform can be found in the `docs/` directory:

1. docs/architecture.md: Detailed architecture breakdowns, encompassing data flow, networking, scaling mechanisms, and visual Mermaid diagrams.
2. docs/developer_guide.md: Comprehensive instructions for configuring the local development environment using Docker Compose and setting up environment variables.
3. docs/deployment_guide.md: A thorough guide on the CI/CD deployment process, GitHub Actions workflow files, Kubernetes namespaces, and Let's Encrypt integration.
4. CHANGELOG.md: The project's release history and version notes following Semantic Versioning (SemVer).

## Quick Start (Local Setup)

To begin local development on the `dev` branch, navigate to the `setup/` directory where the local configurations are housed. Ensure Docker is running on your machine and execute:

```bash
docker compose -f setup/docker-compose.yml up --build
```

The application will initialize and be accessible locally at http://localhost:3000. Refer to the Developer Guide for advanced bare-metal execution parameters.

## License

Please refer to the LICENSE file in the root directory for distribution rights and intellectual property information.
