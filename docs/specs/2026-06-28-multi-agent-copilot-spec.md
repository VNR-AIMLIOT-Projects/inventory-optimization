# Project DevLog: Multi-Agent Copilot & RAG Integration
* **📅 Date**: 2026-06-28
* **🏷️ Tags**: `#Feature` `#Copilot` `#Agents` `#RAG` `#Architecture`

---

> 🎯 **Progress Summary**
> Refactored the monolithic `copilot.py` into a highly modular multi-agent system located in `Backend-RL/src/services/chat/agents/`. Introduced Retrieval-Augmented Generation (RAG) capabilities via `pgvector` to inject document context into prompts. Enhanced the frontend `PageCopilot` with intelligent cross-page redirect commands from the AI orchestrator.

## Problem Statement

As the Copilot gained more responsibilities—handling user requests across demand modification, training execution, evaluation reports, and deployment strategies—the single `copilot.py` file became monolithic, difficult to test, and prone to mixing concerns. Furthermore, the Copilot lacked access to historical insights and contextual data beyond the immediate request, leading to generalized rather than contextual responses. 

Users also found themselves asking the copilot to perform actions belonging to other pages (e.g., asking to train the model while on the Demand page), which resulted in poor user experience because the copilot was bound to the current page's context.

## Solution Details

This PR completely overhauls the Copilot logic by introducing a Multi-Agent Orchestrator and a RAG pipeline.

### 1. Multi-Agent Orchestrator
The `Backend-RL/src/services/chat/agents` module now contains:
- **`router.py`**: A specialized intent routing agent that analyzes a user's prompt and history to determine which expert agent should handle the request (e.g., `demand`, `modify`, `train`, `evaluate`, `deploy`).
- **`orchestrator.py`**: The main entry point that invokes the router, handles cross-page navigations, and executes the appropriate expert agent.
- **Expert Agents**: Individual agents (`demand_agent.py`, `train_agent.py`, etc.) that hold specific system prompts, logic, and context formats for their respective domains.

### 2. Retrieval-Augmented Generation (RAG)
To provide contextual intelligence:
- Integrated `pgvector` into the PostgreSQL database.
- Implemented `embedding_service.py` using `SentenceTransformers` (`all-MiniLM-L6-v2`) to generate document embeddings.
- Implemented `retriever.py` to perform hybrid searches (metadata pre-filtering + vector similarity search) against the database.
- The `orchestrator.py` fetches relevant document chunks using the RAG retriever and injects them into the Groq LLM context for all expert agents (excluding Demand).

### 3. Frontend Redirect Capabilities
- **Cross-Page Redirection:** If the `orchestrator` detects that a user's intent belongs to a different page (e.g., user is on "modify" but asks about "training"), it returns a `navigate_to_<agent>` action. 
- **`PageCopilot.tsx` Update:** The frontend intercepts `navigate_to_*` actions and executes `window.location.href = route` to seamlessly transport the user to the correct page in the application.

## Testing & Validation
- **RAG Tests (`test_rag.py`)**: Validates embedding generation, chunk upsertion, vector similarity search, and hybrid retrieval. These tests passed successfully.
- **Automated Agent Tests**: Validated context parsing and router classification logic across multiple scenarios (`copilot_cases.yaml`).
- **Manual Verification**: We validated the frontend redirect functionality by asking the Copilot out-of-context requests, confirming it triggers the correct `navigate_to_` logic and loads the target page.
