"""
Shared DDQN Agent — Replenix Multi-Echelon Experiments
=======================================================
Reusable Dueling Double-DQN agent used by A1, A2, A3, B1.

Architecture:
  - Dueling DQN head (Advantage + Value streams)
  - Double-DQN target update (prevents overestimation)
  - Soft Polyak target update (tau=0.005)
  - Welford running-reward normalization in replay buffer
  - Huber loss + gradient clipping (norm=1.0)
  - Exponential epsilon decay

This is a superset of Replenix's dqn.py, adapted for larger joint
action spaces required by multi-echelon topologies.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
from collections import deque
import random
import copy

# ---------------------------------------------------------------------------
# Device selection
# ---------------------------------------------------------------------------

DEVICE = torch.device(
    "mps"  if torch.backends.mps.is_available() else
    "cuda" if torch.cuda.is_available()         else
    "cpu"
)


# ---------------------------------------------------------------------------
# Neural Network
# ---------------------------------------------------------------------------

class DuelingDQN(nn.Module):
    """
    Dueling Double-DQN network.

    Splits the final layer into:
      V(s)       — scalar state value
      A(s,a)     — per-action advantage

    Q(s,a) = V(s) + A(s,a) - mean(A(s,·))

    This helps the network learn state value independent of action
    advantage, leading to more stable training in large action spaces.
    """

    def __init__(self, state_size: int, action_size: int, hidden: int = 256):
        super().__init__()
        self.feature = nn.Sequential(
            nn.Linear(state_size, hidden), nn.ReLU(),
            nn.Linear(hidden, hidden),     nn.ReLU(),
            nn.Linear(hidden, hidden // 2), nn.ReLU(),
        )
        mid = hidden // 2
        self.value     = nn.Linear(mid, 1)
        self.advantage = nn.Linear(mid, action_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        f = self.feature(x)
        v = self.value(f)
        a = self.advantage(f)
        return v + a - a.mean(dim=1, keepdim=True)


# ---------------------------------------------------------------------------
# Replay Buffer with Welford reward normalization
# ---------------------------------------------------------------------------

class ReplayBuffer:
    """
    Experience replay buffer.
    Rewards are normalized using a Welford running mean/variance
    to handle the large reward magnitude differences between experiments.
    """

    def __init__(self, capacity: int = 100_000):
        self.buf = deque(maxlen=capacity)
        self._n, self._mean, self._m2 = 0, 0.0, 0.0

    def push(self, s, a, r, s2, done):
        self.buf.append((s, a, float(r), s2, float(done)))
        # Welford online update
        self._n += 1
        d = r - self._mean
        self._mean += d / self._n
        self._m2   += d * (r - self._mean)

    @property
    def reward_std(self) -> float:
        return max(float(np.sqrt(self._m2 / max(self._n, 1))), 1e-6)

    def sample(self, batch_size: int):
        batch   = random.sample(self.buf, batch_size)
        s, a, r, s2, d = zip(*batch)
        r_norm = (np.array(r, np.float32) - self._mean) / self.reward_std
        return (
            torch.FloatTensor(np.array(s)).to(DEVICE),
            torch.LongTensor(a).to(DEVICE),
            torch.FloatTensor(r_norm).to(DEVICE),
            torch.FloatTensor(np.array(s2)).to(DEVICE),
            torch.FloatTensor(d).to(DEVICE),
        )

    def __len__(self) -> int:
        return len(self.buf)


# ---------------------------------------------------------------------------
# DDQN Agent
# ---------------------------------------------------------------------------

class DDQNAgent:
    """
    Double-DQN agent with dueling network, Polyak target updates,
    and exponential epsilon decay.

    Parameters
    ----------
    state_size   : dimension of the observation vector
    action_size  : total number of discrete actions (joint if multi-echelon)
    episodes     : total planned training episodes (used to compute decay rate)
    lr           : learning rate
    gamma        : discount factor
    tau          : soft target update coefficient (Polyak)
    batch_size   : minibatch size
    learn_every  : number of env steps between gradient updates
    eps_start    : initial exploration rate
    eps_min      : minimum exploration rate
    capacity     : replay buffer capacity
    hidden       : hidden layer width for DuelingDQN
    lr_step_eps  : LR scheduler halves every this many episodes
    """

    def __init__(
        self,
        state_size:  int,
        action_size: int,
        episodes:    int   = 500,
        lr:          float = 1e-4,
        gamma:       float = 0.98,
        tau:         float = 0.005,
        batch_size:  int   = 256,
        learn_every: int   = 4,
        eps_start:   float = 1.0,
        eps_min:     float = 0.05,
        capacity:    int   = 100_000,
        hidden:      int   = 256,
        lr_step_eps: int   = 300,
    ):
        self.action_size = action_size
        self.gamma       = gamma
        self.tau         = tau
        self.batch_size  = batch_size
        self.learn_every = learn_every
        self._step       = 0

        self.epsilon   = eps_start
        self.eps_min   = eps_min
        self.eps_decay = (eps_min / eps_start) ** (1.0 / max(episodes, 1))

        self.policy = DuelingDQN(state_size, action_size, hidden).to(DEVICE)
        self.target = DuelingDQN(state_size, action_size, hidden).to(DEVICE)
        self.target.load_state_dict(self.policy.state_dict())
        self.target.eval()

        self.opt = optim.Adam(self.policy.parameters(), lr=lr)
        self.scheduler = StepLR(
            self.opt,
            step_size=max(1, lr_step_eps * 365 // learn_every),
            gamma=0.5
        )
        self.buf = ReplayBuffer(capacity)

        self._best_eval   = -np.inf
        self._best_weights = None

    # ------------------------------------------------------------------

    def act(self, state: np.ndarray) -> int:
        """Epsilon-greedy action selection."""
        if random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        s = torch.FloatTensor(state).unsqueeze(0).to(DEVICE)
        with torch.inference_mode():
            return int(self.policy(s).argmax().item())

    def step(self, s, a, r, s2, done):
        """Store transition and trigger learning."""
        self.buf.push(s, a, r, s2, done)
        self._step += 1
        if self._step % self.learn_every == 0 and len(self.buf) >= self.batch_size:
            self._learn()

    def _learn(self):
        s, a, r, s2, d = self.buf.sample(self.batch_size)

        # Double-DQN: select action with policy, evaluate with target
        q_curr = self.policy(s).gather(1, a.unsqueeze(1)).squeeze(1)
        with torch.no_grad():
            best_a  = self.policy(s2).argmax(1, keepdim=True)
            q_next  = self.target(s2).gather(1, best_a).squeeze(1)
            q_target = r + self.gamma * q_next * (1.0 - d)

        loss = nn.SmoothL1Loss()(q_curr, q_target)
        self.opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
        self.opt.step()
        self.scheduler.step()

        # Soft Polyak target update
        for tp, pp in zip(self.target.parameters(), self.policy.parameters()):
            tp.data.copy_(self.tau * pp.data + (1.0 - self.tau) * tp.data)

    def decay_epsilon(self):
        self.epsilon = max(self.eps_min, self.epsilon * self.eps_decay)

    def save_best(self, eval_reward: float):
        if eval_reward > self._best_eval:
            self._best_eval    = eval_reward
            self._best_weights = copy.deepcopy(self.policy.state_dict())

    def load_best(self):
        if self._best_weights:
            self.policy.load_state_dict(self._best_weights)
            self.target.load_state_dict(self._best_weights)

    def greedy_act(self, state: np.ndarray) -> int:
        """Greedy (no exploration) action for evaluation."""
        s = torch.FloatTensor(state).unsqueeze(0).to(DEVICE)
        with torch.inference_mode():
            return int(self.policy(s).argmax().item())
