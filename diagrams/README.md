# Replenix — Architecture Diagrams

All diagrams live here as `.excalidraw` files (plain JSON, git-diffable) and `.md` files (Mermaid source).

Open `.excalidraw` files at [excalidraw.com](https://excalidraw.com) or in your IDE via the Excalidraw extension.

---

## Diagram Index

| # | File | Description | Format | Last Updated |
|---|------|-------------|--------|--------------|
| 01 | [01-system-architecture](./01-system-architecture.md) | Full system: React → FastAPI → RL Engine → PostgreSQL | Mermaid | 2026-06-03 |
| 02 | [02-rl-agent-dataflow](./02-rl-agent-dataflow.md) | DQN internals: state → action → reward → learn loop | Mermaid | 2026-06-03 |
| 03 | [03-database-schema](./03-database-schema.md) | ERD: uploaded_files → training_runs → evaluation_results | Mermaid | 2026-06-03 |
| 04 | [04-stage-sequence-flow](./04-stage-sequence-flow.md) | Warehouse Manager: Stage 1–5 + LLM copilot sequence | Mermaid | 2026-06-03 |
| 05 | [05-docker-deployment](./05-docker-deployment.md) | Docker Compose: 5 services + volumes + healthchecks | Mermaid | 2026-06-03 |
| 06 | [06-rabbitmq-message-flow](./06-rabbitmq-message-flow.md) | RabbitMQ: jobs exchange → workers → progress fanout → WS | Mermaid | 2026-06-03 |
| 07 | [07-frontend-component-tree](./07-frontend-component-tree.md) | React component hierarchy: App → Stage1–5 → shared | Mermaid | 2026-06-03 |
| 08 | [08-api-contracts](./08-api-contracts.md) | All REST + WebSocket endpoints at a glance | Mermaid | 2026-06-03 |

---

## Conventions

### File Naming
```
{NN}-{scope}-{type}.excalidraw   ← editable visual
{NN}-{scope}-{type}.md           ← Mermaid source (always keep in sync)
```

### Update Rules
- **Always update the diagram when the system it describes changes.**
- If a spec (`specs/features/`) changes an API or data model, update the relevant diagram in the same PR.
- Diagrams are **living documentation** — not one-time artifacts.

### Generating Diagrams with AI
You can ask the AI agent to generate or update diagrams:
> "Update `diagrams/06-rabbitmq-message-flow.md` to include the new priority queue exchange"

---

## Tools

| Tool | Use |
|------|-----|
| [excalidraw.com](https://excalidraw.com) | Open/edit `.excalidraw` files visually |
| VS Code Excalidraw extension | Edit in-IDE |
| Excalidraw MCP | Ask AI to generate diagrams |
| Mermaid Preview (VS Code) | Preview `.md` Mermaid diagrams |
