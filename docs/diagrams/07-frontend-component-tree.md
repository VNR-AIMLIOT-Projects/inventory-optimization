# Diagram 07 — Frontend Component Tree

**Scope**: React component hierarchy — App root through Stage 1–5 pages and shared components  
**Last Updated**: 2026-06-03  
**Source Directory**: `Frontend/client/src/`

---

```mermaid
flowchart TD
    classDef page    fill:#1e3a5f,stroke:#4a90d9,color:#e8f4fd
    classDef shared  fill:#1a3a2a,stroke:#4caf50,color:#e8f7ed
    classDef ui      fill:#2d1b4e,stroke:#9c27b0,color:#f3e5f5
    classDef hook    fill:#3b1f0a,stroke:#ff8c00,color:#fff5e6

    APP["App.tsx\nRouter + QueryClient\nSession Provider"]

    subgraph Auth["Auth Layer"]
        LAND["LandingPage.tsx"]:::page
        LOGIN["Login / Register"]:::page
    end

    subgraph Pipeline["Pipeline Pages (Stage 1–5)"]
        direction LR
        P1["Stage1Page.tsx\nData Ingestion\n- CSVUpload\n- SyntheticGen\n- SKUSelector\n- DemandChart\n- CopilotChat"]:::page
        P2["Stage2Page.tsx\nDemand Shaping\n- ChartEditor\n- SpikeControls\n- ScaleDateRange\n- CopilotChat"]:::page
        P3["Stage3Page.tsx\nRL Training\n- HyperparamForm\n- LiveRewardChart\n- EpsilonBar\n- StatusBadge\n- CopilotChat"]:::page
        P4["Stage4Page.tsx\nEvaluation\n- ComparisonTable\n- InventoryChart\n- RatioDisplay\n- CopilotChat"]:::page
        P5["Stage5Page.tsx\nDeployment Sim\n- DayStepperControl\n- OverrideInput\n- KPIBoard\n- HealthBadges\n- CopilotChat"]:::page
    end

    subgraph Shared["Shared Components"]
        direction TB
        COPILOT["CopilotChat\nGroq LLM interface\nStage-scoped system prompt\nJSON action parser"]:::shared
        CHART["DemandChart\nRecharts wrapper\nInteractive spike overlay"]:::shared
        NAVBAR["Navbar\nStage progress indicator\nUser session"]:::shared
        TOAST["Toast / Notification"]:::ui
        BTN["Button / Form primitives\nshadcn/ui based"]:::ui
    end

    subgraph Hooks["Custom Hooks"]
        H1["useTrainingWebSocket\nWS connection to /ws/training\nEpisode event handler"]:::hook
        H2["useStageData\nReact Query wrappers\nPer-stage API calls"]:::hook
        H3["useSession\nAuth state\nUser info"]:::hook
    end

    APP --> LAND
    APP --> Login
    APP --> NAVBAR
    APP --> P1
    APP --> P2
    APP --> P3
    APP --> P4
    APP --> P5

    P1 --> COPILOT
    P2 --> COPILOT
    P3 --> COPILOT
    P4 --> COPILOT
    P5 --> COPILOT

    P1 --> CHART
    P2 --> CHART

    P3 --> H1
    P1 --> H2
    P2 --> H2
    P3 --> H2
    P4 --> H2
    P5 --> H2

    APP --> H3
```

---

## Key Routing Structure

```
/                   → LandingPage
/login              → Login
/register           → Register
/stage/1            → Stage1Page (Data Ingestion)
/stage/2            → Stage2Page (Demand Shaping)
/stage/3            → Stage3Page (RL Training)
/stage/4            → Stage4Page (Evaluation)
/stage/5            → Stage5Page (Deployment Sim)
```

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-06-03 | Initial component tree — derived from Frontend/client/src | @sujaynimmagadda |
