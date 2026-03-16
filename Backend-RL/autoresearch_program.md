# autoresearch — Inventory Optimization RL

This is an experiment to have an AI agent autonomously research and improve the DQN-based inventory optimization model.

## Setup

To set up a new experiment, work with the user to:

1. **Agree on a run tag**: propose a tag based on today's date (e.g., `mar16`). The branch `autoresearch/<tag>` must not already exist — this is a fresh run.
2. **Create the branch**: `git checkout -b autoresearch/<tag>` from current dev.
3. **Read the in-scope files**: The RL backend is small. Read these files for full context:
   - `src/dqn.py` — **the file you modify**. Contains the DQN network architecture, replay buffer, and agent (epsilon-greedy, Double DQN, learning logic, hyperparameters).
   - `src/environment.py` — the inventory simulation environment. Maps state → action → reward. **Do not modify.**
   - `src/trainer.py` — training loop, baselines (oracle + rule), evaluation. **Do not modify.**
   - `src/demand.py` — demand generation. **Do not modify.**
   - `src/autoresearch_eval.py` — standalone evaluation script. Run experiments with this. **Do not modify.**
4. **Initialize results**: Create `autoresearch_results.tsv` with just the header row if it doesn't exist.
5. **Confirm and go**: Confirm setup looks good.

Once you get confirmation, kick off the experimentation.

## Experimentation

Each experiment trains a DQN agent on inventory optimization and evaluates it against oracle and rule baselines. You launch it simply as:

```bash
cd src && python3 autoresearch_eval.py > run.log 2>&1
```

**What you CAN do:**
- Modify `src/dqn.py` — this is the only file you edit. Everything is fair game:
  - Network architecture (layer sizes, depth, activation functions, dueling DQN, noisy nets, etc.)
  - Replay buffer (capacity, prioritized replay, n-step returns, etc.)
  - Agent hyperparameters (gamma, epsilon schedule, tau, learning rate, batch size, optimizer, etc.)
  - Learning algorithm (Double DQN improvements, gradient clipping, loss function, etc.)

**What you CANNOT do:**
- Modify `environment.py`, `trainer.py`, `demand.py`, or `autoresearch_eval.py`. They are read-only.
- Install new packages or add dependencies. You can only use what's already available (PyTorch, numpy, etc.).
- Modify the evaluation harness. The `_greedy_eval` function in `trainer.py` is the ground truth metric.

**The goal is simple: get the highest `eval_reward`.** The episode budget is fixed (100 episodes by default), so experiments run fast (~1-3 minutes). Everything about the DQN agent is fair game: change the architecture, the optimizer, the hyperparameters, the replay buffer, the learning algorithm.

**Simplicity criterion**: All else being equal, simpler is better. A small improvement that adds ugly complexity is not worth it. Conversely, removing something and getting equal or better results is a great outcome — that's a simplification win. When evaluating whether to keep a change, weigh the complexity cost against the improvement magnitude.

**The first run**: Your very first run should always be to establish the baseline, so you will run the evaluation script as-is.

## Output format

Once the script finishes it prints a summary like this:

```
---
eval_reward:        25432.10
oracle_reward:      30155.00
rule_reward:        22100.50
rl_vs_oracle_pct:   84.3
training_seconds:   95.2
episodes:           100
best_train_reward:  27000.00
---
```

You can extract the key metric from the log file:

```bash
grep "^eval_reward:" run.log
```

## Logging results

When an experiment is done, log it to `autoresearch_results.tsv` (tab-separated, NOT comma-separated — commas break in descriptions).

The TSV has a header row and 5 columns:

```
commit	eval_reward	rl_vs_oracle_pct	status	description
```

1. git commit hash (short, 7 chars)
2. eval_reward achieved (e.g., 25432.10) — use 0.00 for crashes
3. rl_vs_oracle_pct (e.g., 84.3) — use 0.0 for crashes
4. status: `keep`, `discard`, or `crash`
5. short text description of what this experiment tried

Example:

```
commit	eval_reward	rl_vs_oracle_pct	status	description
a1b2c3d	25432.10	84.3	keep	baseline
b2c3d4e	26100.50	86.5	keep	increase hidden layer to 512
c3d4e5f	24000.00	79.6	discard	switch to GeLU activation
d4e5f6g	0.00	0.0	crash	dueling DQN (shape mismatch)
```

## The experiment loop

The experiment runs on a dedicated branch (e.g., `autoresearch/mar16`).

LOOP FOREVER:

1. Look at the git state: the current branch/commit we're on
2. Tune `src/dqn.py` with an experimental idea by directly hacking the code.
3. git commit
4. Run the experiment: `cd src && python3 autoresearch_eval.py > run.log 2>&1` (redirect everything — do NOT use tee or let output flood your context)
5. Read out the results: `grep "^eval_reward:\|^rl_vs_oracle_pct:" run.log`
6. If the grep output is empty, the run crashed. Run `tail -n 50 run.log` to read the Python stack trace and attempt a fix. If you can't get things to work after more than a few attempts, give up.
7. Record the results in the tsv (NOTE: do not commit the results.tsv file, leave it untracked by git)
8. If eval_reward improved (higher), you "advance" the branch, keeping the git commit
9. If eval_reward is equal or worse, you git reset back to where you started

The idea is that you are a completely autonomous researcher trying things out. If they work, keep. If they don't, discard. And you're advancing the branch so that you can iterate.

**Experiment ideas to try** (in rough priority order):
- Increase/decrease network width (256 → 512, or 128)
- Add/remove hidden layers
- Try different activations (LeakyReLU, GELU, Tanh)
- Tune learning rate (1e-4 → 3e-4, 5e-5, etc.)
- Tune gamma (discount factor: 0.95, 0.99)
- Tune batch size (128, 512)
- Tune replay buffer capacity (50000, 200000)
- Try prioritized experience replay
- Try n-step returns
- Try Dueling DQN architecture
- Try Noisy Networks for exploration (instead of epsilon-greedy)
- Try different optimizers (AdamW, RMSprop)
- Tune soft update rate tau (0.001, 0.01)
- Tune epsilon decay schedule
- Add layer normalization or batch normalization

**Crashes**: If a run crashes (OOM, or a bug, or etc.), use your judgment: If it's something dumb and easy to fix (e.g., a typo, a missing import), fix it and re-run. If the idea itself is fundamentally broken, just skip it, log "crash" as the status in the tsv, and move on.

**NEVER STOP**: Once the experiment loop has begun (after the initial setup), do NOT pause to ask the human if you should continue. Do NOT ask "should I keep going?" or "is this a good stopping point?". The human might be asleep, or gone from a computer and expects you to continue working *indefinitely* until you are manually stopped. You are autonomous. If you run out of ideas, think harder — try combining previous near-misses, try more radical architectural changes. The loop runs until the human interrupts you, period.
