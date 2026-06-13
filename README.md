# Replenix: Intelligent Inventory Optimization

**Replenix** is an advanced, Reinforcement Learning (RL) powered supply chain dynamics optimization engine. It is designed to mitigate the "Bullwhip Effect" and optimize inventory planning across complex, multi-echelon supply chains.

### 🌐 Live Environments
- **Production:** [https://www.replenix.app/](https://www.replenix.app/)
- **Preprod (Staging):** [https://preprod.replenix.app/](https://preprod.replenix.app/)

---

## 📖 Project Documentation

We have thoroughly documented the architecture, development process, and deployment strategies. Please refer to the `/docs` directory for detailed information:

1. **[Architecture Overview](file:///Users/sujaynimmagadda/Documents/College/Main/inventory-optimization/docs/architecture.md):** High-level view of the microservices, Kubernetes setup, NetworkPolicies, and data flows.
2. **[Developer Guide](file:///Users/sujaynimmagadda/Documents/College/Main/inventory-optimization/docs/developer_guide.md):** Complete instructions for running the stack locally using Docker Compose or bare-metal execution.
3. **[Deployment Guide](file:///Users/sujaynimmagadda/Documents/College/Main/inventory-optimization/docs/deployment_guide.md):** Detailed breakdown of our GitHub Actions CI/CD pipelines across the Dev, Preprod, and Prod environments.

---

## ✨ Key Features

- **Interactive Modeling Dashboard:** A rich React/Next.js frontend allows users to configure supply chain scenarios, upload custom demand CSVs, and visualize simulation results dynamically.
- **Deep Q-Network (DQN) Training:** An asynchronous Python worker pool trains RL agents to optimize reorder points and safety stock levels in real-time.
- **Microservices Architecture:** Symmetrically scalable infrastructure separating the UI, API, Message Broker (RabbitMQ), and RL processing workers.
- **Zero-Trust Security:** Strict Kubernetes NetworkPolicies completely firewall the cluster internally, exposing only necessary ports to explicit namespaces.
- **Automated CI/CD:** Fully automated GitHub Actions pipeline executing safe, zero-downtime rolling deployments to DigitalOcean Kubernetes with built-in smoke tests and auto-rollback mechanisms.

---

## 🚀 Quick Start (Local Development)

To start the entire Replenix stack locally (Frontend, Backend, PostgreSQL, RabbitMQ, and RL Workers), simply ensure Docker is running and execute:

```bash
docker compose up --build
```

Access the application at [http://localhost:3000](http://localhost:3000).

For complete bare-metal setup instructions and environment variable configurations, please read the [Developer Guide](file:///Users/sujaynimmagadda/Documents/College/Main/inventory-optimization/docs/developer_guide.md).

---

## 🛡️ License & Citations

See `LICENSE` for distribution rights.
If using Replenix in academic research, please refer to the attached `replenix_paper.tex` and `references.bib` files for proper citation context.
