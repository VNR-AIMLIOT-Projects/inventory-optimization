import torch
import torch.nn as nn
import torch.optim as optim
import random
import numpy as np
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
    Experience Replay Memory.
    Stores transitions (state, action, reward, next_state, done) 
    to break correlation during training.
    """
    def __init__(self, capacity=100000):
        self.buffer = deque(maxlen=capacity)

    def push(self, s, a, r, s2, done):
        # Store experience tuple
        self.buffer.append((s, a, r, s2, done))

    def sample(self, batch_size):
        # Randomly sample a batch
        batch = random.sample(self.buffer, batch_size)
        s, a, r, s2, d = zip(*batch)
        
        # Convert to Tensors and move to device (GPU/CPU)
        return (
            torch.FloatTensor(np.array(s)).to(device),
            torch.LongTensor(a).to(device),
            torch.FloatTensor(r).to(device),
            torch.FloatTensor(np.array(s2)).to(device),
            torch.FloatTensor(d).to(device)
        )

    def __len__(self):
        return len(self.buffer)


class DQNAgent:
    """
    The RL Agent that interacts with the environment.
    """
    def __init__(self, state_size, action_size):
        self.action_size = action_size
        
        # Hyperparameters
        self.gamma = 0.98           # Discount factor (future rewards)
        self.epsilon = 1.0          # Exploration rate (starts high)
        self.eps_min = 0.05         # Minimum exploration
        self.eps_decay = 0.995      # Decay rate per episode
        self.target_update_freq = 100 # How often to update target net
        
        # Networks
        self.policy_net = DQN(state_size, action_size).to(device)
        self.target_net = DQN(state_size, action_size).to(device)
        
        # Initialize target weights to match policy
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval() # Target net is only for inference (calculating loss targets)
        
        # Optimizer
        self.optimizer = optim.Adam(self.policy_net.parameters(), lr=1e-4)
        
        # Memory
        self.buffer = ReplayBuffer()
        self.batch_size = 64

    def act(self, state):
        """Epsilon-greedy action selection"""
        # Exploration: Random action
        if random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        
        # Exploitation: Best action from Neural Net
        state = torch.FloatTensor(state).unsqueeze(0).to(device)
        with torch.no_grad():
            return torch.argmax(self.policy_net(state)).item()

    def learn(self):
        """Train the neural network using a batch from replay buffer"""
        if len(self.buffer) < self.batch_size:
            return
        
        # 1. Sample batch
        s, a, r, s2, d = self.buffer.sample(self.batch_size)
        
        # 2. Calculate Q(s, a) - The predicted value for the action we took
        q = self.policy_net(s).gather(1, a.unsqueeze(1)).squeeze()
        
        # 3. Calculate Target Q - Bellman Equation: R + gamma * max(Q(s', a'))
        # We use target_net for stability
        with torch.no_grad():
            q_next = self.target_net(s2).max(1)[0]
            target = r + self.gamma * q_next * (1 - d)
        
        # 4. Compute Loss (MSE)
        loss = nn.MSELoss()(q, target)
        
        # 5. Backpropagation
        self.optimizer.zero_grad()
        loss.backward()
        
        # Gradient Clipping (prevents exploding gradients)
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), 1.0)
        
        self.optimizer.step()

    def update_target(self):
        """Sync target network weights with policy network"""
        self.target_net.load_state_dict(self.policy_net.state_dict())