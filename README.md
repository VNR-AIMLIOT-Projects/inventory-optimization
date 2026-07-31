# Replenix: Intelligent Inventory Optimization

Replenix is an advanced, Reinforcement Learning (RL) powered supply chain dynamics optimization engine. It is designed to mitigate the "Bullwhip Effect" and optimize inventory planning across complex, multi-echelon supply chains.

## Live Environments

- **Production**: https://www.replenix.app
- **Preprod (Staging)**: https://preprod.replenix.app
- **Observability (Prod)**: https://obs.replenix.app

## Architecture Overview

Replenix utilizes a robust, horizontally scalable microservices architecture designed to handle computationally heavy reinforcement learning tasks alongside a responsive web application and conversational AI components. 

The system consists of the following isolated services:
1. **Frontend Application (React / Next.js)**: Provides the interactive modeling dashboard for users to configure supply chain scenarios and visualize results.
2. **Backend API (FastAPI)**: Manages data flow, user authentication, and orchestrates training jobs. Houses the **Multi-Agent RAG Orchestrator** which queries vector embeddings for context-aware AI interactions.
3. **Observability Dashboard (Next.js)**: A dedicated, decoupled dashboard that monitors AI traces, relevance scores, and hallucination metrics asynchronously without impacting main API latency.
4. **Message Broker (RabbitMQ)**: Handles the queuing of intensive RL training tasks, ensuring decoupling of the API from the computationally heavy processing layers.
5. **Reinforcement Learning Workers (Python / PyTorch)**: Asynchronous Deep Q-Network (DQN) agents that process jobs from RabbitMQ, simulating demand and supply dynamics.
6. **Primary Database (PostgreSQL with `pgvector`)**: Securely stores user sessions, inventory parameters, AI traces, and vector embeddings for the RAG pipeline.
7. **Application Cache (Redis)**: Accelerates API response times by caching heavy historical and demand analytics payloads.
8. **Infrastructure Observability Stack (Prometheus, Grafana, Thanos)**: Provides high-availability metrics collection, long-term storage, and interactive RED (Rate, Errors, Duration) dashboards.

The entire architecture is containerized and orchestrated via **DigitalOcean Kubernetes (DOKS)**, utilizing strict default-deny `NetworkPolicies` to enforce zero-trust security between the microservices. Traffic is routed via an NGINX Ingress Controller with automated Let's Encrypt TLS certificate provisioning.

> **Note on Infrastructure (July 2026)**: The active DigitalOcean resources (Kubernetes cluster, node droplets, load balancers, and persistent volumes) hosting Replenix have been decommissioned. The Kubernetes manifests (`k8s/` directory) and deployment workflows have been preserved in the repository to allow a seamless migration to a new cloud provider (e.g., Oracle Cloud, AWS, GCP, or PaaS alternatives like Supabase/Vercel) when needed.

## Environment Separation

The repository strictly enforces environment separation to maintain code stability and secure deployment pipelines.

### 1. Development Environment (Local)
The `dev` branch is reserved exclusively for local, stable development. Local development is orchestrated using Docker Compose (or `container-compose` for Apple Silicon) and NPM Workspaces, allowing engineers to spin up the entire Replenix stack instantly on their local machines. Configuration files for local setup are maintained in the `setup/` directory.

### 2. Pre-Production Environment (Staging)
The `preprod` branch acts as the final validation stage before production. Pushes to this branch trigger automated GitHub Actions that build Docker images and deploy them to the `replenix-preprod` namespace on our DigitalOcean Kubernetes cluster. This environment mirrors production identically, allowing for rigorous integration testing and quality assurance without affecting live users.

### 3. Production Environment
The `prod` branch is the live, user-facing application. Code is merged into `prod` only after passing all smoke tests in the Pre-Production environment. Pushes to this branch trigger a zero-downtime rolling update to the `replenix-prod` namespace, dynamically scaling RL Workers via KEDA (Kubernetes Event-Driven Autoscaling) based on real-time RabbitMQ queue depth.

## Codebase Documentation

Extensive documentation covering every aspect of the platform can be found in the `docs/` directory:

1. **[Architecture Guidelines](file:///docs/architecture.md)**: Detailed architecture breakdowns, encompassing data flow, networking, and scaling mechanisms.
2. **[RAG Architecture Diagram](file:///docs/diagrams/09-rag-architecture.md)**: Details the vector retrieval and LLM generation loop.
3. **[Observability Architecture Diagram](file:///docs/diagrams/10-observability-architecture.md)**: Explains the asynchronous AI trace evaluation pipeline.
4. **[Developer Guide](file:///docs/developer_guide.md)**: Comprehensive instructions for configuring the local development environment.
5. **[Deployment Guide](file:///docs/deployment_guide.md)**: A thorough guide on the CI/CD deployment process, GitHub Actions workflow files, Kubernetes namespaces, and Let's Encrypt integration.
6. **[Changelog](file:///docs/CHANGELOG.md)** / **[Releases](file:///docs/RELEASES.md)**: The project's release history following Semantic Versioning (SemVer).

## Prerequisites

Before starting local development, ensure you have installed:
- Docker and Docker Compose (or `container-compose` for Apple Silicon)
- Node.js 20 or higher
- Python 3.10 or higher
- Git

## Quick Start (Local Setup)

### 1. Clone the Repository

```bash
git clone https://github.com/VNR-AIMLIOT-Projects/inventory-optimization.git
cd inventory-optimization
```

### 2. Start the Stack (Docker Compose)

The easiest way to run the entire stack locally is via Docker Compose from the root directory.

```bash
docker compose -f setup/docker-compose.yml up --build
```

**Alternative (Apple Silicon Native):**
If you prefer using Apple's native `container` runtime instead of Docker Desktop, ensure you have the `container-compose` wrapper installed (`brew install container container-compose`) and run:
```bash
container-compose -f setup/docker-compose.yml up --build
```

The application will initialize and be accessible locally at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **AI Observability UI**: http://localhost:3001
- **Grafana Dashboard**: http://localhost:3005

### 3. Local Native Development (Optional)

Since this project uses an NPM Workspace monorepo, you can run the web applications natively for faster hot-reloading:

```bash
# Install dependencies for Frontend and Observability
npm install

# Start development servers across the workspaces
npm run dev
```

For the backend:

```bash
cd apps/Backend-RL
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Available Scripts

From the root directory (NPM Workspace):

| Command | Description |
|---------|-------------|
| `npm run dev` | Starts development servers for all workspace apps (Frontend, Observability) |
| `npm run build` | Builds all workspace apps for production |
| `npm run test` | Runs JS/TS tests across the workspaces |
| `docker compose -f setup/docker-compose.yml up` | Spins up the full infrastructure locally |

## Testing

The project uses Pytest for backend testing and Playwright for End-to-End browser testing. These are strictly enforced in the GitHub Actions `dev` CI/CD pipeline.

### Backend Unit Tests

```bash
cd apps/Backend-RL
pytest tests/
```

### E2E Tests

```bash
cd e2e_tests
npx playwright test
```

## Troubleshooting

### Docker Compose Build Failures
**Error**: `failed to solve: rpc error: code = Unknown...`
**Solution**: Clear your Docker build cache and try again:
```bash
docker builder prune -a
docker compose -f setup/docker-compose.yml up --build
```

### Database Connection Refused
**Error**: `psycopg2.OperationalError: could not connect to server: Connection refused`
**Solution**: Ensure the `postgres` container in Docker Compose is fully initialized before the backend attempts to connect, or manually restart the backend container.

### RabbitMQ Worker Not Picking Up Tasks
**Solution**: Check the RabbitMQ management UI (port 15672) to ensure the queues are created and the `rl-worker` container logs show successful connection to the broker.

## License

Please refer to the LICENSE file in the root directory for distribution rights and intellectual property information.
