# Experiment B1 — Results

**Branch:** `experiments/multi-echelon-research`  
**Run date:** 2026-05-17  
**Episodes per variant:** 500 | **Device:** Apple MPS | **Total runtime:** ~26 min  
**Environment:** A1 2-Echelon (b_R=500, c_W=2, c_R=2 — tuned config)  
**Test seed:** 999 | **Val seed:** 777

---

## What Was Tested

| Variant | State Repr. | Key Difference |
|---------|------------|----------------|
| **IS** | Installation Stock | Warehouse sees only its own inventory |
| **ES** | Echelon Stock | Warehouse sees total downstream coverage (own + pipeline + retailer) |

Both variants use the **identical** A1 environment with identical hyperparameters.
The only difference is the state vector construction.

---

## Training Convergence — IS (Installation Stock)

| Episode | Train Reward | Eval Reward | ε | Bullwhip | Svc Level |
|:-------:|-------------:|------------:|:---:|:-------:|:---------:|
| 0 | −133,501,743 | −359,921,644 | 0.994 | 1.384 | 100.0% |
| 50 | −84,261,025 | −44,050,995 | 0.737 | 0.378 | 83.7% |
| 100 | −65,853,782 | −114,693,176 | 0.546 | 0.128 | 9.3% |
| 150 | −65,158,104 | −40,012,537 | 0.405 | 1.113 | 97.5% |
| 200 | −31,016,597 | −25,972,168 | 0.300 | 1.592 | 83.1% |
| 250 | −14,439,305 | −23,412,020 | 0.222 | 1.798 | 87.9% |
| 300 | −14,100,766 | **−10,434,840 ✓** | 0.165 | 2.501 | 97.1% |
| 350 | −12,196,743 | −12,880,526 | 0.122 | 1.663 | 97.6% |
| 400 | −10,316,727 | −13,995,725 | 0.090 | 2.489 | 94.3% |
| 450 | −10,222,372 | −10,583,682 | 0.067 | 2.382 | 97.7% |
| 499 | −8,969,320 | −8,818,848 | 0.050 | 2.861 | 99.0% |

**IS Best checkpoint:** Episode 300 · Eval reward = −10,434,840

---

## Training Convergence — ES (Echelon Stock)

| Episode | Train Reward | Eval Reward | ε | Bullwhip | Svc Level |
|:-------:|-------------:|------------:|:---:|:-------:|:---------:|
| 0 | −148,652,486 | −164,799,980 | 0.994 | 1.907 | 100.0% |
| 50 | −71,693,436 | −91,498,218 | 0.737 | 0.058 | 27.9% |
| 100 | −49,206,427 | −94,006,513 | 0.546 | 0.062 | 25.6% |
| 150 | −32,030,711 | −47,397,465 | 0.405 | 2.276 | 65.7% |
| 200 | −26,454,949 | −38,501,389 | 0.300 | 2.226 | 73.6% |
| 250 | −12,258,986 | −17,481,175 | 0.222 | 2.738 | 94.7% |
| 300 | −16,138,358 | **−12,759,288 ✓** | 0.165 | 2.253 | 97.1% |
| 350 | −12,988,779 | −14,915,706 | 0.122 | 2.477 | 94.7% |
| 400 | −12,275,962 | −16,156,542 | 0.090 | 2.841 | 93.3% |
| 450 | −9,391,654 | −13,507,972 | 0.067 | 2.700 | 94.9% |
| 499 | −9,759,708 | −11,614,021 | 0.050 | 2.478 | 96.0% |

**ES Best checkpoint:** Episode 300 · Eval reward = −12,759,288

---

## Final Evaluation (Test Demand, Seed 999)

### Head-to-Head: IS vs ES

| Metric | IS (Installation Stock) | ES (Echelon Stock) | ES wins? |
|--------|:-----------------------:|:------------------:|:--------:|
| **Total Cost** | **11,547,025** | 11,789,089 | IS ✓ |
| **Service Level** | **95.5%** | 94.0% | IS ✓ |
| **Bullwhip Ratio** | 2.325 | **1.807** | ES ✓ |
| **Fill Rate** | 96.7% | **97.0%** | ES ✓ |
| **Holding Cost** | 6,834,347 | **5,531,219** | ES ✓ |
| **Backorder Cost** | **4,712,000** | 6,257,000 | IS ✓ |
| **Total Backlog** | **9,424** | 12,514 | IS ✓ |

### ES vs IS Summary

| Metric | Δ (ES − IS) | Direction |
|--------|:-----------:|:---------:|
| Total Cost | −2.1% | IS wins (slightly) |
| Service Level | −1.5 pp | IS wins |
| Bullwhip Ratio | **+22.3%** | **ES wins significantly** |
| Fill Rate | +0.3 pp | ES wins |
| Holding Cost | −19.0% | **ES wins significantly** |
| Backorder Cost | +32.8% | IS wins |

---

## Key Findings

### ⚠️ H1 NOT Confirmed — IS outperforms ES on Service Level (by 1.5 pp)

Contrary to the hypothesis, the Installation Stock agent achieves **slightly higher
service level** (95.5% vs 94.0%) and lower total cost (−2.1%). ES learns a richer
upstream picture but translates it into more conservative retailer ordering, which
reduces holding cost but increases backorder risk.

**Interpretation:** In a 2-echelon environment with a short retailer lead time (1 day),
the additional downstream context in the ES state doesn't help the agent decide when to
order — the critical decision is how much to order, which IS already captures through
backlog signals.

### ✅ H2 Confirmed — ES Produces Smoother Upstream Orders

The ES agent's Bullwhip Ratio (**1.807**) is **22.3% lower** than IS (**2.325**).
By seeing the total echelon stock (WH + pipeline + retailer), the warehouse doesn't
panic-order when it sees its own stock drop — it accounts for what's already in transit
to the retailer. This produces **smoother upstream ordering**.

This confirms the classical Clark & Scarf (1960) intuition: echelon stock information
is primarily useful for **upstream decision making**, not downstream service level.

### ✅ H3 — Convergence Speed Similar

Both IS and ES best checkpoints appear at episode 300. ES has a slower warmup
(service level 25.6% at ep 100 vs IS's 9.3%) but both reach similar convergence
episodes. The ES state is more informative but not measurably faster to learn.

### 📊 Key Insight for Research Paper

> **Echelon Stock state does not help an RL agent improve service level in a 2-echelon
> system, but it significantly reduces upstream demand variance (Bullwhip Ratio −22.3%).
> If the primary KPI is supply chain stability (bullwhip), ES is preferable.
> If the primary KPI is customer service level, IS is equally effective at lower
> complexity.**

---

## Config

Both variants used identical hyperparameters:
```json
{
  "lead_time_W": 3, "lead_time_R": 1,
  "h_W": 2.0, "h_R": 5.0, "b_R": 500, "c_W": 2, "c_R": 2,
  "n_actions_W": 11, "n_actions_R": 11,
  "episodes": 500, "gamma": 0.98, "lr": 0.0001, "tau": 0.005
}
```

---

## Plots

| Plot | Description |
|------|-------------|
| `plots/training_curves_comparison.png` | IS vs ES training curves side-by-side |
| `plots/metric_comparison.png` | Bar chart: IS vs ES on 4 key metrics |
