# Experiment C1 — Disruption Robustness

**Branch:** `experiments/multi-echelon-research`
**Status:** 🟡 Designed — Ready to Run
**Depends on:** A2 (extends 3-echelon env with disruption injection)

---

## 1. Motivation

All prior experiments (A1–B1) assume **perfect supplier availability** — the upstream
supplier always delivers. Real supply chains face disruptions: factory shutdowns, port
delays, raw material shortages. No paper in the literature tests DRL robustness under
**supply disruption + seasonal demand** simultaneously.

The COVID-19 pandemic, the 2021 Suez Canal blockage, and semiconductor shortages
demonstrated that rare-but-severe disruptions are the dominant risk in modern supply chains.

**Research Question:** How much does supply disruption degrade Joint DDQN performance
(service level and cost), and does a disruption-aware agent (trained with disruptions)
outperform a naïve agent (trained without) when disruptions occur at test time?

---

## 2. Topology

Extends A2 (3-echelon) with a **disruption channel** on the supplier → warehouse link:

```
[Experiment C1]
  Supplier ──[DISRUPTION]──[L1=4d]──► Warehouse ──[L2=2d]──► DC ──[L3=1d]──► Retailer ──► Demand
                 ↑
       Zero supply for D_len days
       with prob p_shock per day

  Joint DDQN Agent (same architecture as A2)
  State extended: +2 dims (disruption_active flag, disruption_days_remaining)
```

---

## 3. Research Hypotheses

> **H1 (Degradation):** A naïve agent (trained without disruptions, tested with disruptions)
> sees service level drop by ≥15 pp during disruption windows compared to normal periods.

> **H2 (Robustness via training):** A disruption-aware agent (trained WITH disruptions)
> maintains service level within 5 pp of the no-disruption baseline even during active shocks.

> **H3 (Recovery speed):** The disruption-aware agent recovers to pre-disruption inventory
> levels within L1+L2+L3=7 days of disruption end; the naïve agent takes ≥14 days.

---

## 4. Disruption Model

### 4.1 Shock Process
```
At each day t:
  If not currently disrupted:
    with prob p_shock = 0.03:   # ~11 disruption events per year
      start disruption of length D_len ~ Uniform(1, 7) days
  During disruption:
    supplier ships ZERO units (pipeline_W gets 0 instead of a_W)
    disruption_days_remaining -= 1
```

### 4.2 Disruption Severity Levels

| Mode | p_shock | Max D_len | Expected disruption days/year |
|------|---------|----------|-------------------------------|
| **Mild** | 0.02 | 5 | ~36 days/year |
| **Moderate** | 0.03 | 7 | ~54 days/year |
| **Severe** | 0.05 | 14 | ~90 days/year |

We train and evaluate on **Moderate** as the primary setting, then test the
trained agent under Mild and Severe as zero-shot robustness checks.

### 4.3 State Extension (+2 dims, total 15 dims for C1)

```
s_t = [
    # ... same 13 dims as A2 ...
    disruption_active,         # 0 or 1
    disruption_remaining_norm  # remaining_days / max_disruption_len (0–1)
]
```

The **naïve agent** uses the original 13-dim state (no disruption info).
The **disruption-aware agent** uses the 15-dim state.

---

## 5. Experimental Conditions

| Condition | Train | Test | Agent State |
|-----------|-------|------|-------------|
| **Baseline** | No disruption | No disruption | 13-dim (A2) |
| **Naïve** | No disruption | Moderate disruption | 13-dim |
| **Aware** | Moderate disruption | Moderate disruption | 15-dim |
| **Zero-shot Mild** | Moderate | Mild disruption | 15-dim |
| **Zero-shot Severe** | Moderate | Severe disruption | 15-dim |

---

## 6. Cost Parameters

Identical to A2: h1=1, h2=3, h3=5, b3=500, c_order=2, LT=4+2+1.

**No cost for disruptions** (disruption is an environment phenomenon, not a decision variable).
The agent must learn to buffer against it through safety stock ordering.

---

## 7. Metrics

| Metric | Normal Window | Disruption Window | Recovery |
|--------|--------------|-------------------|----------|
| **Service Level** | % during non-disruption days | % during disruption days | % in 14-day post-disruption window |
| **Avg Cost** | Cost per day (normal) | Cost per day (disruption) | Cost per day (recovery) |
| **Safety Stock Buffer** | Avg inv_W before shock | Avg inv_W during shock | Days to return to pre-shock level |
| **Bullwhip Ratio** | Full episode | — | — |

---

## 8. Expected Outputs

```
C1_disruption_robustness/
├── EXPERIMENT.md
├── RESULTS.md
├── env_disruption.py      ← A2 env extended with disruption injection
├── run_experiment.py
├── results/
│   ├── config.json
│   ├── summary.json
│   └── experiment_log.jsonl
└── plots/
    ├── service_level_by_window.png    ← SL: normal vs disruption vs recovery
    ├── disruption_timeline.png        ← Inventory trace with disruption markers
    ├── severity_comparison.png        ← Naive vs Aware across mild/mod/severe
    └── training_curves.png
```

---

## 9. How to Run

```bash
cd experiments/C1_disruption_robustness
python3 run_experiment.py              # Full run (500 eps each condition)
python3 run_experiment.py --smoke-test # 50 eps quick check
```

---

## 10. Literature Gap Closed

No existing paper combines: **DRL + multi-echelon + seasonal demand + supply disruption**.
Risk-averse MAPPO (CityU HK, 2024) tests disruption but with non-seasonal i.i.d. demand.
Our C1 experiment is the first to study disruption robustness in a seasonally-driven
supply chain — directly relevant to real retail scenarios (e.g., disruption during peak season).
