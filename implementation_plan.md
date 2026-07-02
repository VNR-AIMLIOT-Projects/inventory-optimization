# Multi-Agent Copilot Integration Review & Documentation Plan

This document outlines the validation and documentation steps for the `feature/multi-agent-copilot` branch (PR #106), which introduces a sophisticated multi-agent orchestrator with RAG capabilities for the Replenix Copilot.

## User Review Required
No code changes are currently planned, but I need your approval on the documentation structure and testing methodology below before I finalize this PR's review.

## Open Questions
- Do you have any specific test scenarios you want me to run (e.g., specific cross-page redirect commands to test)?
- Would you like the backend tests (`tests/test_rag.py`) to be run as part of the verification?

## Proposed Changes

### Documentation (Specs & Architecture)
#### [NEW] `docs/specs/2026-06-28-multi-agent-copilot-spec.md`
- Create a dedicated Specification Document outlining the migration from a monolithic `copilot.py` to the modular `agents/` directory (`router`, `orchestrator`, `demand_agent`, etc.).
- Detail the RAG (Retrieval-Augmented Generation) pipeline implementation leveraging `pgvector` and `embedding_service.py`.
- Explain the frontend `PageCopilot.tsx` action-handling logic for cross-page redirects.

#### [MODIFY] `docs/architecture.md`
- Update the Kubernetes/Microservices architecture diagram to explicitly include the **RAG Vector Database** extension (if applicable) and the **Multi-Agent Orchestrator** in the Backend API section.

## Verification Plan

### Automated Tests
- Run `pytest Backend-RL/tests/test_rag.py` to ensure the RAG triggers and semantic retrieval logic operate correctly without errors.

### Manual Verification
- Execute API requests against the Copilot endpoints (or interact locally) to test the intent routing mechanism.
  - Scenario 1: On the **Demand** page, ask: *"Help me train the model."* -> Ensure Orchestrator returns `navigate_to_train` action.
  - Scenario 2: On the **Modify** page, ask: *"Decrease order cost by 5."* -> Ensure Orchestrator returns `modify_parameters` action.
