# Diagram 02 — RL Agent Internal Data Flow

**Scope**: DQN agent internals — state, action, environment, replay buffer, learning  
**Last Updated**: 2026-06-03  
**Related Spec**: [specs/architecture/rl-agent-design.md](../specs/architecture/rl-agent-design.md)  
**Source Files**: `Backend-RL/src/dqn.py`, `Backend-RL/src/environment.py`, `Backend-RL/src/trainer.py`

---

```mermaid
flowchart LR
    classDef state fill:#0d2b1a,stroke:#26a69a,color:#e0f2f1
    classDef agent fill:#1a1a3a,stroke:#5c6bc0,color:#e8eaf6
    classDef env   fill:#1e3a5f,stroke:#4a90d9,color:#e8f4fd
    classDef buf   fill:#3b1f0a,stroke:#ff8c00,color:#fff5e6

    ENV["InventoryEnvironment\nState s_t ∈ R^15:\n- log-norm inventory\n- norm last demand\n- norm last action\n- norm pipeline inv\n- day-of-week 7-hot\n- seasonal progress\n- promo flag f_t\n- days since order\n- stockout flag"]:::env

    ACT["DQNAgent.act(s_t)\nEpsilon-greedy policy\nEpsilon: 1.0 to 0.05\nlinear over 75% of training"]:::agent

    STEP["env.step(a_t)\n1. Arrivals from pipeline\n2. Sales = min(d_t, inv)\n3. Reward R_t:\n   p x sold\n   - h x inv\n   - c_s x lost_sales\n   - f x ordered"]:::env

    BUF["ReplayBuffer\nCapacity: 100,000\nStores raw transitions\nWelford: running mu,sigma\nNormalize reward at sample:\nr_hat = (r - mu) / sigma"]:::buf

    LEARN["DQNAgent.learn() every 4 steps\n1. Sample batch size 256\n2. Q(s,a) from policy_net\n3. Double DQN target:\n   a* = argmax Q_theta(s')\n   y  = r + gamma * Q_theta_bar(s', a*)\n4. Loss: Huber/SmoothL1\n5. Adam lr=1e-4\n6. Grad clip norm<=1.0\n7. Polyak: theta_bar = tau*theta + (1-tau)*theta_bar"]:::agent

    CKPT["Best Checkpoint\nGreedy eval every 100 ep\non fixed validation set\nSave if eval_reward > best\nRestore for deployment"]:::agent

    ENV  -->|"s_t (15-D state)"| ACT
    ACT  -->|"a_t (action index)"| STEP
    STEP -->|"s_{t+1}, R_t, done"| BUF
    STEP -->|"next state"| ENV
    BUF  -->|"normalized batch"| LEARN
    LEARN -->|"update theta, theta_bar"| ACT
    LEARN -->|"trigger eval every 100 ep"| CKPT
```

---

## Key Parameters

| Parameter | Value | Location |
|-----------|-------|----------|
| State dimensions | 15 | `environment.py` |
| Action space | Discrete (order qty steps) | `environment.py` |
| Replay buffer capacity | 100,000 | `dqn.py` |
| Batch size | 256 | `dqn.py` |
| Learning rate | 1e-4 | `dqn.py` |
| Polyak tau | 0.005 | `dqn.py` |
| Epsilon range | 1.0 → 0.05 | `trainer.py` |
| Eval frequency | Every 100 episodes | `trainer.py` |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-06-03 | Initial diagram — ported from replenix_architecture.md | @sujaynimmagadda |
