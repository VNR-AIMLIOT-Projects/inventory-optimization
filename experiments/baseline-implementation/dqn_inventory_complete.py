import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import random
from collections import namedtuple, deque

# Set random seeds for reproducibility
np.random.seed(0)
torch.manual_seed(0)
random.seed(0)

# Check if MPS (Apple Silicon GPU) or CUDA is available
if torch.backends.mps.is_available():
    device = torch.device("mps")
    print(f"Using Apple Silicon GPU (MPS)")
elif torch.cuda.is_available():
    device = torch.device("cuda:0")
    print(f"Using NVIDIA GPU (CUDA)")
else:
    device = torch.device("cpu")
    print(f"Using CPU")

# Environment Class
class InvOptEnv():
    """
    Inventory Optimization Environment for DQN Training

    This simulates a retail store that sells Coke with:
    - Variable demand patterns by day of week
    - Lead time for order delivery
    - Inventory capacity constraints
    - Profit maximization objective
    """
    def __init__(self, demand_records):
        self.n_period = len(demand_records)
        self.current_period = 1
        self.day_of_week = 0  # 0=Sunday, 1=Monday, ..., 6=Saturday
        self.inv_level = 25   # Initial inventory
        self.inv_pos = 25     # Inventory position (on hand + incoming orders)

        # Business parameters
        self.capacity = 50
        self.holding_cost = 3
        self.unit_price = 30
        self.fixed_order_cost = 50
        self.variable_order_cost = 10
        self.lead_time = 2

        self.order_arrival_list = []
        self.demand_list = demand_records
        self.state = np.array([self.inv_pos] + self.convert_day_of_week(self.day_of_week))

        # History tracking
        self.state_list = [self.state]
        self.action_list = []
        self.reward_list = []

    def reset(self):
        """Reset environment to initial state"""
        self.state_list = []
        self.action_list = []
        self.reward_list = []
        self.inv_level = 25
        self.inv_pos = 25
        self.current_period = 1
        self.day_of_week = 0
        self.state = np.array([self.inv_pos] + self.convert_day_of_week(self.day_of_week))
        self.state_list.append(self.state)
        self.order_arrival_list = []
        return self.state

    def step(self, action):
        """
        Execute one time step within the environment

        Args:
            action (int): Order quantity (0 to 20 cases)

        Returns:
            next_state: New state after action
            reward: Profit for this period
            done: Whether episode is finished
        """
        # Place order if action > 0
        if action > 0:
            y = 1  # Ordering indicator
            self.order_arrival_list.append([self.current_period + self.lead_time, action])
        else:
            y = 0

        # Check if any orders arrive today
        if len(self.order_arrival_list) > 0:
            if self.current_period == self.order_arrival_list[0][0]:
                self.inv_level = min(self.capacity, self.inv_level + self.order_arrival_list[0][1])
                self.order_arrival_list.pop(0)

        # Get demand for current period
        demand = self.demand_list[self.current_period - 1]

        # Calculate units sold (limited by inventory)
        units_sold = min(demand, self.inv_level)

        # Calculate profit (reward)
        reward = (units_sold * self.unit_price - 
                 self.holding_cost * self.inv_level - 
                 y * self.fixed_order_cost - 
                 action * self.variable_order_cost)

        # Update inventory level after sales
        self.inv_level = max(0, self.inv_level - demand)

        # Calculate new inventory position (on hand + pipeline orders)
        self.inv_pos = self.inv_level
        for order_info in self.order_arrival_list:
            self.inv_pos += order_info[1]

        # Move to next day
        self.day_of_week = (self.day_of_week + 1) % 7
        self.state = np.array([self.inv_pos] + self.convert_day_of_week(self.day_of_week))
        self.current_period += 1

        # Store history
        self.state_list.append(self.state)
        self.action_list.append(action)
        self.reward_list.append(reward)

        # Check if episode is done
        terminate = self.current_period > self.n_period

        return self.state, reward, terminate

    def convert_day_of_week(self, d):
        """Convert day of week to one-hot encoding"""
        encoding = [0] * 6  # 6 dimensions for days 1-6 (Sunday=0 maps to all zeros)
        if d > 0:
            encoding[d-1] = 1
        return encoding

# Neural Network for Q-function approximation
class QNetwork(nn.Module):
    """
    Deep Q-Network with 3 fully connected layers

    Architecture:
    - Input: 7 features (inventory position + day of week encoding)
    - Hidden: 128 neurons each with ReLU activation
    - Output: 21 Q-values for actions 0-20
    """
    def __init__(self, state_size, action_size, seed, fc1_unit=128, fc2_unit=128):
        super(QNetwork, self).__init__()
        self.seed = torch.manual_seed(seed)
        self.fc1 = nn.Linear(state_size, fc1_unit)
        self.fc2 = nn.Linear(fc1_unit, fc2_unit)
        self.fc3 = nn.Linear(fc2_unit, action_size)

    def forward(self, x):
        """Forward pass through the network"""
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)

# Experience Replay Buffer
class ReplayBuffer:
    """Store and sample experience tuples for training stability"""

    def __init__(self, action_size, buffer_size, batch_size, seed):
        self.action_size = action_size
        self.memory = deque(maxlen=buffer_size)
        self.batch_size = batch_size
        self.experience = namedtuple("Experience", 
                                   field_names=["state", "action", "reward", "next_state", "done"])
        self.seed = random.seed(seed)

    def add(self, state, action, reward, next_state, done):
        """Add a new experience to memory"""
        e = self.experience(state, action, reward, next_state, done)
        self.memory.append(e)

    def sample(self):
        """Randomly sample a batch of experiences from memory"""
        experiences = random.sample(self.memory, k=self.batch_size)

        states = torch.from_numpy(np.vstack([e.state for e in experiences if e is not None])).float().to(device)
        actions = torch.from_numpy(np.vstack([e.action for e in experiences if e is not None])).long().to(device)
        rewards = torch.from_numpy(np.vstack([e.reward for e in experiences if e is not None])).float().to(device)
        next_states = torch.from_numpy(np.vstack([e.next_state for e in experiences if e is not None])).float().to(device)
        dones = torch.from_numpy(np.vstack([e.done for e in experiences if e is not None]).astype(np.uint8)).float().to(device)

        return (states, actions, rewards, next_states, dones)

    def __len__(self):
        return len(self.memory)

# DQN Agent
class Agent():
    """
    Deep Q-Learning Agent with experience replay and target networks
    """

    def __init__(self, state_size, action_size, seed, lr=1e-4, buffer_size=int(5e5), 
                 batch_size=128, gamma=0.99, tau=1e-3, update_every=4):
        self.state_size = state_size
        self.action_size = action_size
        self.seed = random.seed(seed)

        # Hyperparameters
        self.lr = lr
        self.batch_size = batch_size
        self.gamma = gamma
        self.tau = tau
        self.update_every = update_every

        # Q-Networks (local and target)
        self.qnetwork_local = QNetwork(state_size, action_size, seed).to(device)
        self.qnetwork_target = QNetwork(state_size, action_size, seed).to(device)
        self.optimizer = optim.Adam(self.qnetwork_local.parameters(), lr=lr)

        # Replay memory
        self.memory = ReplayBuffer(action_size, buffer_size, batch_size, seed)
        self.t_step = 0

    def step(self, state, action, reward, next_state, done):
        """Save experience and learn if enough samples available"""
        # Save experience in replay memory
        self.memory.add(state, action, reward, next_state, done)

        # Learn every update_every steps
        self.t_step = (self.t_step + 1) % self.update_every
        if self.t_step == 0:
            if len(self.memory) > self.batch_size:
                experiences = self.memory.sample()
                self.learn(experiences)

    def act(self, state, eps=0.):
        """Choose action using epsilon-greedy policy"""
        state = torch.from_numpy(state).float().unsqueeze(0).to(device)
        self.qnetwork_local.eval()

        with torch.no_grad():
            action_values = self.qnetwork_local(state)

        self.qnetwork_local.train()

        # Epsilon-greedy action selection
        if random.random() > eps:
            return np.argmax(action_values.cpu().data.numpy())
        else:
            return random.choice(np.arange(self.action_size))

    def learn(self, experiences):
        """Update Q-network parameters using given batch of experience tuples"""
        states, actions, rewards, next_states, dones = experiences

        # Get expected Q values from local model
        Q_expected = self.qnetwork_local(states).gather(1, actions)

        # Get max predicted Q values (for next states) from target model
        Q_targets_next = self.qnetwork_target(next_states).detach().max(1)[0].unsqueeze(1)

        # Compute Q targets for current states
        Q_targets = rewards + (self.gamma * Q_targets_next * (1 - dones))

        # Compute loss
        loss = F.mse_loss(Q_expected, Q_targets)

        # Minimize the loss
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        # Update target network
        self.soft_update(self.qnetwork_local, self.qnetwork_target)

    def soft_update(self, local_model, target_model):
        """Soft update model parameters: θ_target = τ*θ_local + (1 - τ)*θ_target"""
        for target_param, local_param in zip(target_model.parameters(), local_model.parameters()):
            target_param.data.copy_(self.tau * local_param.data + (1.0 - self.tau) * target_param.data)

# Demand Data Generation
def generate_demand_data(weeks=52, seed=0):
    """
    Generate realistic demand data with day-of-week patterns

    Demand patterns:
    - Monday-Thursday: Normal(3, 1.5) - Low demand weekdays
    - Friday: Normal(6, 1) - Medium demand
    - Saturday-Sunday: Normal(12, 2) - High demand weekends
    """
    np.random.seed(seed)
    demand_hist = []

    for week in range(weeks):
        # Monday to Thursday (4 days) - Low demand
        for day in range(4):
            demand = np.random.normal(3, 1.5)
            demand = max(0, np.round(demand))  # Ensure non-negative integer
            demand_hist.append(demand)

        # Friday - Medium demand
        demand = np.random.normal(6, 1)
        demand = max(0, np.round(demand))
        demand_hist.append(demand)

        # Saturday and Sunday (2 days) - High demand
        for day in range(2):
            demand = np.random.normal(12, 2)
            demand = max(0, np.round(demand))
            demand_hist.append(demand)

    return demand_hist

# Training function
def train_dqn(env, agent, n_episodes=1000, eps_start=1.0, eps_end=0.01, eps_decay=0.995):
    """
    Train the DQN agent

    Args:
        env: Environment instance
        agent: DQN agent
        n_episodes: Number of training episodes
        eps_start: Starting epsilon for exploration
        eps_end: Minimum epsilon
        eps_decay: Epsilon decay rate
    """
    print(f"Starting DQN training for {n_episodes} episodes...")
    scores = []
    eps = eps_start

    for i_episode in range(1, n_episodes + 1):
        state = env.reset()
        score = 0

        while True:
            action = agent.act(state, eps)
            next_state, reward, done = env.step(action)
            agent.step(state, action, reward, next_state, done)
            state = next_state
            score += reward

            if done:
                break

        scores.append(score)
        eps = max(eps * eps_decay, eps_end)

        # Print progress
        if i_episode % 100 == 0:
            avg_score = np.mean(scores[-100:])
            print(f'Episode {i_episode:4d}, Average Score: {avg_score:8.2f}, Epsilon: {eps:.3f}')

    return scores

# (s,S) Policy Implementation for Comparison
def evaluate_sS_policy(s, S, demand_records):
    """
    Evaluate the performance of an (s,S) inventory policy

    Args:
        s: Reorder point
        S: Order-up-to level
        demand_records: Historical demand data
    """
    total_profit = 0
    inv_level = 25  # Starting inventory
    lead_time = 2
    capacity = 50
    holding_cost = 3
    fixed_order_cost = 50
    variable_order_cost = 10
    unit_price = 30
    order_arrival_list = []

    for period in range(len(demand_records)):
        # Calculate inventory position
        inv_pos = inv_level
        for order_info in order_arrival_list:
            inv_pos += order_info[1]

        # Make ordering decision based on (s,S) policy
        if inv_pos <= s:
            order_quantity = min(20, S - inv_pos)  # Limited by max order size
            order_arrival_list.append([period + lead_time, order_quantity])
            y = 1
        else:
            order_quantity = 0
            y = 0

        # Process arriving orders
        if order_arrival_list and period == order_arrival_list[0][0]:
            inv_level = min(capacity, inv_level + order_arrival_list[0][1])
            order_arrival_list.pop(0)

        # Process demand
        demand = demand_records[period]
        units_sold = min(demand, inv_level)

        # Calculate profit
        profit = (units_sold * unit_price - 
                 holding_cost * inv_level - 
                 y * fixed_order_cost - 
                 order_quantity * variable_order_cost)

        inv_level = max(0, inv_level - demand)
        total_profit += profit

    return total_profit

def optimize_sS_policy(demand_records):
    """Find optimal (s,S) parameters"""
    print("Optimizing (s,S) policy...")
    best_profit = float('-inf')
    best_params = (0, 1)

    for S in range(1, 61):  # Order-up-to level
        for s in range(0, S):  # Reorder point
            profit = evaluate_sS_policy(s, S, demand_records)
            if profit > best_profit:
                best_profit = profit
                best_params = (s, S)

    print(f"Optimal (s,S) policy: s={best_params[0]}, S={best_params[1]}")
    print(f"(s,S) policy profit: ${best_profit:.2f}")
    return best_params, best_profit

# Main execution function
def main():
    """Main function to run the complete DQN inventory management experiment"""

    print("=" * 60)
    print("DQN INVENTORY MANAGEMENT SYSTEM")
    print("=" * 60)

    # Generate training data
    print("\n1. Generating training demand data...")
    demand_hist = generate_demand_data(weeks=52, seed=0)
    print(f"   Generated {len(demand_hist)} days of demand data")
    print(f"   Average daily demand: {np.mean(demand_hist):.2f}")
    print(f"   Demand range: {min(demand_hist):.0f} - {max(demand_hist):.0f}")

    # Create environment and agent
    print("\n2. Creating environment and DQN agent...")
    env = InvOptEnv(demand_hist)
    agent = Agent(state_size=7, action_size=21, seed=0)
    print(f"   State size: 7 (inventory position + day encoding)")
    print(f"   Action size: 21 (order quantities 0-20)")
    print(f"   Using device: {device}")

    # Train the agent
    print("\n3. Training DQN agent...")
    scores = train_dqn(env, agent, n_episodes=1000)

    # Save the trained model
    model_path = 'dqn_inventory_model.pth'
    torch.save(agent.qnetwork_local.state_dict(), model_path)
    print(f"\n   Model saved as '{model_path}'")

    # Plot training progress
    plt.figure(figsize=(12, 5))

    plt.subplot(1, 2, 1)
    plt.plot(scores)
    plt.title('DQN Training Progress')
    plt.xlabel('Episode')
    plt.ylabel('Total Reward')
    plt.grid(True)

    plt.subplot(1, 2, 2)
    # Plot moving average
    window_size = 50
    moving_avg = [np.mean(scores[i:i+window_size]) for i in range(len(scores)-window_size+1)]
    plt.plot(range(window_size-1, len(scores)), moving_avg)
    plt.title(f'DQN Training Progress (Moving Average, window={window_size})')
    plt.xlabel('Episode')
    plt.ylabel('Average Reward')
    plt.grid(True)

    plt.tight_layout()
    plt.savefig('dqn_training_progress.png', dpi=300, bbox_inches='tight')
    plt.show()

    # Find optimal (s,S) policy for comparison
    print("\n4. Finding optimal (s,S) policy for comparison...")
    best_sS, sS_profit = optimize_sS_policy(demand_hist)

    # Test both policies
    print("\n5. Testing trained DQN policy...")
    test_demand = generate_demand_data(weeks=52, seed=100)

    # Test DQN policy
    env_test = InvOptEnv(test_demand)
    state = env_test.reset()
    total_dqn_reward = 0

    while True:
        action = agent.act(state, eps=0.0)  # No exploration during testing
        next_state, reward, done = env_test.step(action)
        total_dqn_reward += reward
        state = next_state
        if done:
            break

    # Test (s,S) policy on same data
    sS_test_profit = evaluate_sS_policy(best_sS[0], best_sS[1], test_demand)

    # Results summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"DQN Policy Profit:        ${total_dqn_reward:,.2f}")
    print(f"(s,S) Policy Profit:      ${sS_test_profit:,.2f}")

    if total_dqn_reward > sS_test_profit:
        improvement = ((total_dqn_reward - sS_test_profit) / sS_test_profit) * 100
        print(f"DQN Improvement:          +{improvement:.2f}%")
        print("DQN policy outperforms traditional (s,S) policy!")
    else:
        decline = ((sS_test_profit - total_dqn_reward) / sS_test_profit) * 100
        print(f"DQN Performance:          -{decline:.2f}%")
        print("Traditional (s,S) policy performed better")

    print("\nTraining completed successfully!")

if __name__ == "__main__":
    main()
