# Replenix: Intelligent Inventory Optimization

Replenix is an advanced, Reinforcement Learning (RL) powered supply chain dynamics optimization engine. It is designed to mitigate the "Bullwhip Effect" and optimize inventory planning across complex, multi-echelon supply chains.

## Key Features

- **RL-Powered Optimization**: Uses Deep Q-Network (DQN) agents to simulate demand and supply dynamics.
- **Multi-Agent RAG Orchestrator**: Uses a Retrieval-Augmented Generation pipeline grounded in Postgres `pgvector` for conversational AI insights.
- **Interactive Modeling Dashboard**: Allows users to configure supply chain scenarios and visualize results in real-time.
- **AI Observability**: Zero-latency asynchronous tracing and evaluation to detect hallucinations and monitor relevance.

## Tech Stack

- **Frontend**: Next.js with React, Tailwind CSS, Shadcn UI
- **Backend API**: FastAPI (Python), SQLAlchemy, Groq, SentenceTransformers
- **RL Workers**: Python, PyTorch (Asynchronous workers)
- **Database**: PostgreSQL (with pgvector for embeddings)
- **Message Broker**: RabbitMQ
- **Caching**: Redis
- **Observability**: Prometheus, Grafana, Thanos
- **Deployment**: DigitalOcean Kubernetes (K8s), Docker, GitHub Actions, KEDA

## Prerequisites

- Docker and Docker Compose (or `container-compose` for Apple Silicon)
- Node.js 20 or higher (for local frontend/UI development)
- Python 3.10 or higher (for local backend development)
- Git

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/VNR-AIMLIOT-Projects/inventory-optimization.git
cd inventory-optimization
```

### 2. Environment Setup

Copy the example environment files for the various microservices (if applicable) or use the defaults provided in the `setup/` directory for local development.

```bash
# E.g., for the backend
cd apps/Backend-RL
cp .env.example .env
cd ../../
```

### 3. Start Development Server (Docker Compose)

The easiest way to run the entire stack (Frontend, Backend, Redis, Postgres, RabbitMQ, RL Workers, and Grafana) locally is via Docker Compose.

```bash
docker compose -f setup/docker-compose.yml up --build
```

**Alternative (Apple Silicon Native):**
If you prefer using Apple's native `container` runtime instead of Docker Desktop:
```bash
brew install container container-compose
container-compose -f setup/docker-compose.yml up --build
```

The application will initialize and be accessible locally at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Observability UI**: http://localhost:3001
- **Grafana Dashboard**: http://localhost:3005

### 4. Local Native Development (Optional)

Since this is an NPM Workspace monorepo, you can run the frontend development server natively:

```bash
npm install
npm run dev
```

For the backend:

```bash
cd apps/Backend-RL
pip install -r requirements.txt
uvicorn src.main:app --reload
```

## Architecture

### Directory Structure

```
├── apps/
│   ├── Backend-RL/            # FastAPI backend, RL workers, and RAG orchestrator
│   ├── Frontend/              # Next.js user-facing web application
│   └── Frontend-Observability/# AI Observability dashboard
├── docs/                      # Extensive architecture and developer documentation
│   └── diagrams/              # Mermaid diagrams for RAG, Observability, DB schema, etc.
├── e2e_tests/                 # Playwright end-to-end tests
├── k8s/                       # Kubernetes deployment manifests
├── setup/                     # Docker Compose configurations for local dev
├── package.json               # NPM Workspace root configuration
└── .github/workflows/         # CI/CD pipelines
```

### Key Components

**Frontend (`apps/Frontend/`)**
- Next.js App Router providing the interactive dashboard.
- Uses Tailwind CSS and Shadcn UI components.
- Communicates directly with the FastAPI backend.

**Backend API (`apps/Backend-RL/`)**
- FastAPI server handling authentication, data ingestion, and orchestrating training jobs.
- **RAG Orchestrator**: Uses a router to determine intent, querying `pgvector` for context chunks when necessary, and interfacing with the Groq LLM.
- **Observability Layer**: Synchronously logs AI traces and asynchronously evaluates them for hallucinations and relevance.

**RL Worker Pool**
- Dedicated asynchronous worker pool for heavy Deep Q-Network (DQN) training.
- Pulls tasks from RabbitMQ.
- Automatically scaled via KEDA based on queue depth in production.

**Data & Caching**
- **PostgreSQL**: Primary data store, utilizing `pgvector` for vector embeddings.
- **Redis**: Caches API responses (invalidated by RL workers).
- **RabbitMQ**: Message broker decoupling the API from the heavy RL workloads.

## Environment Variables

For local development with Docker Compose, standard environment variables are pre-configured in `setup/docker-compose.yml`. For production deployments or native development, ensure the following are set in your respective `.env` files:

### Backend Required Variables
| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `RABBITMQ_URL` | RabbitMQ connection string |
| `GROQ_API_KEY` | API key for the Groq LLM |
| `SECRET_KEY` | Secret for JWT authentication |

## Available Scripts

From the root directory (NPM Workspace):

| Command | Description |
|---------|-------------|
| `npm run dev` | Starts development servers for all workspace apps |
| `npm run build` | Builds all workspace apps for production |
| `npm run test` | Runs tests across the workspaces |
| `docker compose -f setup/docker-compose.yml up` | Spins up the full infrastructure locally |

## Testing

The project uses Pytest for backend testing and Playwright for E2E testing.

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

## Deployment

Pushes to the `dev` branch are strictly for local, stable development.
Pushes to `preprod` or `prod` trigger automated GitHub Actions that build Docker images and deploy them to DigitalOcean Kubernetes.

### Kubernetes (DigitalOcean)

The CI/CD pipeline (`.github/workflows/ci-cd.yml`) handles:
1. Building Docker images for Frontend, Backend, and RL Workers.
2. Pushing images to DigitalOcean Container Registry.
3. Applying Kubernetes manifests (`k8s/`).
4. Verifying rollout success and executing smoke tests.

Zero-trust security is enforced via strict `NetworkPolicies` inside the cluster.

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
**Solution**: Check the RabbitMQ management UI (usually port 15672) to ensure the queues are created and the `rl-worker` container logs show successful connection to the broker.
