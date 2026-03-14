import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import StepLR
import random
import numpy as np
import copy
from collections import deque

# Use GPU if available, otherwise CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

class DQN(nn.Module):
    """
    Deep Q-Network Architecture.
    Maps state -> action values (Q-values).
    """
    def __init__(self, state_size, action_size):
        super().__init__()
        # 3-Layer Fully Connected Network
        self.net = nn.Sequential(
            nn.Linear(state_size, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, action_size)
        )

    def forward(self, x):
        return self.net(x)


class ReplayBuffer:
    """
    Experience Replay Memory with Running Reward Normalization.
    Stores transitions (state, action, reward, next_state, done) 
    to break correlation during training.
    
    Rewards are stored RAW. When sampled, they are normalized using
    a running mean/std tracked via Welford's algorithm, so the network
    always trains on ~zero-mean, unit-variance rewards.
    """
    def __init__(self, capacity=100000):
        self.buffer = deque(maxlen=capacity)
        # Welford's online algorithm for running mean/std of rewards
        self._reward_count = 0
        self._reward_mean = 0.0
        self._reward_m2 = 0.0

    def push(self, s, a, r, s2, done):
        # Store experience tuple (raw reward)
        self.buffer.append((s, a, r, s2, done))
        # Update running reward statistics (Welford's algorithm)
        self._reward_count += 1
        delta = r - self._reward_mean
        self._reward_mean += delta / self._reward_count
        delta2 = r - self._reward_mean
        self._reward_m2 += delta * delta2

    @property
    def reward_std(self):
        """Running standard deviation of all rewards seen."""
        if self._reward_count < 2:
            return 1.0
        return max(np.sqrt(self._reward_m2 / self._reward_count), 1e-6)

    def sample(self, batch_size):
        # Randomly sample a batch
        batch = random.sample(self.buffer, batch_size)
        s, a, r, s2, d = zip(*batch)
        
        # Normalize rewards: zero-mean, unit-variance using running stats
        r_array = np.array(r, dtype=np.float32)
        r_normalized = (r_array - self._reward_mean) / self.reward_std
        
        # Convert to Tensors and move to device (GPU/CPU)
        return (
            torch.FloatTensor(np.array(s)).to(device),
            torch.LongTensor(a).to(device),
            torch.FloatTensor(r_normalized).to(device),
            torch.FloatTensor(np.array(s2)).to(device),
            torch.FloatTensor(d).to(device)
        )

    def __len__(self):
        return len(self.buffer)


class DQNAgent:
    """
    The RL Agent that interacts with the environment.
    """
    def __init__(self, state_size, action_size, total_episodes=300, decay_type="exponential"):
        self.action_size = action_size
        self.decay_type = decay_type       # "exponential" or "linear"
        self.total_episodes = total_episodes

        # Hyperparameters
        self.gamma = 0.98           # Discount factor (future rewards)
        self.epsilon = 1.0          # Exploration rate (starts high)
        self.eps_min = 0.05         # Minimum exploration (reached by end of training)
        self.tau = 0.005            # Soft target update rate (Polyak averaging)
        self.learn_every = 4        # Learn every N steps (standard DQN frequency)

        # --- Decay schedule ---
        if decay_type == "exponential":
            # Auto-compute: epsilon * decay^total_episodes == eps_min
            self.eps_decay = (self.eps_min / self.epsilon) ** (1.0 / total_episodes)
        else:  # linear
            # Decay linearly to eps_min over first 75% of episodes, flat thereafter
            self.eps_decay = (self.epsilon - self.eps_min) / (0.75 * total_episodes)
        
        # Networks
        self.policy_net = DQN(state_size, action_size).to(device)
        self.target_net = DQN(state_size, action_size).to(device)
        
        # Initialize target weights to match policy
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval() # Target net is only for inference (calculating loss targets)
        
        # Optimizer + LR scheduler (halve LR every 300 episodes to stabilize late training)
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=1e-4)
        steps_per_episode = 365  # approximate
        self.scheduler = StepLR(self.optimizer, step_size=300 * steps_per_episode // self.learn_every, gamma=0.5)
        
        # Memory
        self.buffer = ReplayBuffer()
        self.batch_size = 256
        self._step_count = 0  # Counter for learn_every logic

        # Best model checkpoint (saved during training)
        self._best_weights = None

    def act(self, state):
        """Epsilon-greedy action selection"""
        # Exploration: Random action
        if random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        
        # Exploitation: Best action from Neural Net
        state_t = torch.from_numpy(np.asarray(state, dtype=np.float32)).unsqueeze(0).to(device)
        with torch.inference_mode():
            return torch.argmax(self.policy_net(state_t)).item()

    def learn(self):
        """Train the neural network using a batch from replay buffer.
        Only runs every `learn_every` steps to reduce noise from correlated updates.
        """
        self._step_count += 1
        
        # Only learn every N steps
        if self._step_count % self.learn_every != 0:
            return
        
        if len(self.buffer) < self.batch_size:
            return
        
        # 1. Sample batch (rewards are auto-normalized by the buffer)
        s, a, r, s2, d = self.buffer.sample(self.batch_size)
        
        # 2. Calculate Q(s, a) - The predicted value for the action we took
        q = self.policy_net(s).gather(1, a.unsqueeze(1)).squeeze()
        
        # 3. Calculate Target Q - Bellman Equation: R + gamma * max(Q(s', a'))
        # We use target_net for stability
        with torch.no_grad():
            # Double DQN: policy net selects best action, target net evaluates it
            # Reduces Q-value overestimation that destabilizes training
            best_actions = self.policy_net(s2).argmax(dim=1, keepdim=True)
            q_next = self.target_net(s2).gather(1, best_actions).squeeze(1)
            target = r + self.gamma * q_next * (1 - d)
        
        # 4. Compute Loss (Huber loss — linear for large errors, stable with raw rewards)
        loss = nn.SmoothL1Loss()(q, target)
        
        # 5. Backpropagation
        self.optimizer.zero_grad()
        loss.backward()
        
        # Gradient Clipping (prevents exploding gradients)
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        
        self.optimizer.step()
        self.scheduler.step()
        
        # 6. Soft target update (Polyak averaging) — every learn step
        # target_param = tau * policy_param + (1 - tau) * target_param
        self._soft_update_target()

    def decay_epsilon(self, ep):
        """Update epsilon according to the chosen decay schedule."""
        if self.decay_type == "exponential":
            # Multiplicative decay — reaches eps_min at total_episodes
            self.epsilon = max(self.eps_min, self.epsilon * self.eps_decay)
        else:
            # Linear decay until 75% of training, flat for the remainder
            if ep < 0.75 * self.total_episodes:
                self.epsilon = max(self.eps_min, self.epsilon - self.eps_decay)
            # else: epsilon stays at eps_min (no change needed)

    def _soft_update_target(self):
        """Soft (Polyak) target update: target = tau*policy + (1-tau)*target"""
        for tp, pp in zip(self.target_net.parameters(), self.policy_net.parameters()):
            tp.data.copy_(self.tau * pp.data + (1.0 - self.tau) * tp.data)

    def save_best(self):
        """Snapshot current policy weights as the best model."""
        self._best_weights = copy.deepcopy(self.policy_net.state_dict())

    def load_best(self):
        """Restore the best model weights for evaluation."""
        if self._best_weights is not None:
            self.policy_net.load_state_dict(self._best_weights)
            self.target_net.load_state_dict(self._best_weights)