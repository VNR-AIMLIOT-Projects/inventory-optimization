# Spec-Driven Development — Replenix

This directory contains all specifications for the Replenix project.

**Core rule: No code is written without a spec. No exceptions.**

---

## How It Works

```
Write Spec → Review → Implement → Verify
     ↑                               |
     └──────── iterate if needed ────┘
```

1. **Write** — Create a spec in the right subdirectory using `SPEC_TEMPLATE.md`
2. **Review** — Read it out loud. Does it cover all edge cases? Is the acceptance criteria unambiguous?
3. **Implement** — Prompt the AI: *"Implement `specs/features/NNN-name.md`. Do not add anything outside the acceptance criteria."*
4. **Verify** — Check each acceptance criterion one by one. Close the spec when all pass.

---

## Directory Structure

```
specs/
├── README.md                        ← This file
├── SPEC_TEMPLATE.md                 ← Copy this for every new spec
│
├── features/                        ← New user-facing features
│   └── NNN-short-name.md
│
├── api/                             ← API contract specs (endpoint design before coding)
│   ├── backend-api.md               ← FastAPI endpoint contracts
│   └── websocket-protocol.md        ← WebSocket message schemas
│
├── architecture/                    ← System-level design decisions
│   ├── system-overview.md           ← High-level architecture narrative
│   ├── rl-agent-design.md           ← DQN agent design decisions
│   └── data-model.md                ← Database schema decisions
│
└── bugs/                            ← Reproducible bug specs
    └── NNN-short-description.md
```

---

## Spec Status Lifecycle

```
Draft → Review → Approved → In Progress → Done → Archived
```

| Status | Meaning |
|--------|---------|
| `Draft` | Being written, not ready for review |
| `Review` | Ready for human review and feedback |
| `Approved` | Approved for implementation |
| `In Progress` | Currently being implemented |
| `Done` | All acceptance criteria verified |
| `Archived` | No longer relevant (replaced or cancelled) |

---

## Spec Index

### Features

| ID | Title | Status | Created |
|----|-------|--------|---------|
| SPEC-F001 | [Multi-SKU Parallel Training](./features/F001-multi-sku-parallel-training.md) | Approved | 2026-06-03 |

### Architecture

| ID | Title | Status | Created |
|----|-------|--------|---------|
| SPEC-A001 | [System Overview](./architecture/A001-system-overview.md) | Done | 2026-06-03 |
| SPEC-A002 | [RL Agent Design](./architecture/A002-rl-agent-design.md) | Done | 2026-06-03 |
| SPEC-A003 | [Data Model](./architecture/A003-data-model.md) | Done | 2026-06-03 |

### API Contracts

| ID | Title | Status | Created |
|----|-------|--------|---------|
| SPEC-API001 | [Backend API](./api/API001-backend-api.md) | Done | 2026-06-03 |
| SPEC-API002 | [WebSocket Protocol](./api/API002-websocket-protocol.md) | Done | 2026-06-03 |

---

## Rules

1. **Spec first** — Never start coding without an Approved spec
2. **Scope is law** — The "Out of Scope" section is a hard boundary
3. **Acceptance criteria are binary** — Each AC is either ✅ or ❌, no partial credit
4. **Diagrams in sync** — If a spec changes the system, update the relevant `diagrams/` file in the same PR
5. **One spec per PR** — Keep PRs focused; one feature, one spec, one PR
6. **Bug specs too** — Non-trivial bugs get a spec in `bugs/` before a fix is written

---

## Prompting the AI with Specs

When asking the AI to implement a feature, use this format:

```
Implement SPEC-F001 as described in specs/features/F001-multi-sku-parallel-training.md.

Constraints:
- Implement only what is listed under "In Scope"
- Do not implement anything listed under "Out of Scope"
- All acceptance criteria must pass
- Update diagrams/06-rabbitmq-message-flow.md if the message schema changes
```
