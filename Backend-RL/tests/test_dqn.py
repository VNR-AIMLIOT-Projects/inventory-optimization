import numpy as np
import torch
import pytest

from rl.dqn import DQN, ReplayBuffer, DQNAgent

def test_dqn_network():
    state_size = 4
    action_size = 2
    net = DQN(state_size, action_size)
    
    # Check forward pass
    state = torch.randn(1, state_size)
    q_values = net(state)
    
    assert q_values.shape == (1, action_size)
    assert not torch.isnan(q_values).any()

def test_replay_buffer_push_len():
    buffer = ReplayBuffer(capacity=10)
    assert len(buffer) == 0
    assert buffer.reward_std == 1.0 # default when count < 2
    
    buffer.push([0.0, 1.0], 1, 10.0, [1.0, 0.0], False)
    assert len(buffer) == 1
    assert buffer.reward_std == 1.0 # count < 2
    
    buffer.push([1.0, 0.0], 0, 20.0, [0.0, 1.0], True)
    assert len(buffer) == 2
    assert buffer.reward_std > 0 # count >= 2
    
    # Fill buffer to capacity
    for i in range(15):
        buffer.push([0.0, 0.0], 0, float(i), [0.0, 0.0], False)
    
    assert len(buffer) == 10 # Should not exceed capacity

def test_replay_buffer_sample():
    buffer = ReplayBuffer(capacity=100)
    for i in range(10):
        buffer.push([float(i), float(i)], 0, float(i), [float(i+1), float(i+1)], False)
    
    s, a, r, s2, d = buffer.sample(4)
    
    assert s.shape == (4, 2)
    assert a.shape == (4,)
    assert r.shape == (4,)
    assert s2.shape == (4, 2)
    assert d.shape == (4,)
    
    # Verify r is normalized
    # Given they are samples from 0-9, the raw rewards shouldn't exactly match the output
    # Just checking it runs without error and returns tensors

def test_dqn_agent_init():
    agent_exp = DQNAgent(4, 2, total_episodes=100, decay_type="exponential", gamma=0.95, learning_rate=1e-3)
    assert agent_exp.action_size == 2
    assert agent_exp.epsilon == 1.0
    assert agent_exp.eps_min == 0.05
    assert hasattr(agent_exp, "eps_decay")
    
    agent_lin = DQNAgent(4, 2, total_episodes=100, decay_type="linear", gamma=0.95, learning_rate=1e-3)
    assert agent_lin.decay_type == "linear"

def test_dqn_agent_act():
    agent = DQNAgent(4, 2)
    
    # Test exploration
    agent.epsilon = 2.0 # Force exploration
    action = agent.act([0.0, 0.0, 0.0, 0.0])
    assert action in [0, 1]
    
    # Test exploitation
    agent.epsilon = -1.0 # Force exploitation
    action = agent.act([0.0, 0.0, 0.0, 0.0])
    assert action in [0, 1]

def test_dqn_agent_decay_epsilon():
    # Exponential
    agent = DQNAgent(4, 2, total_episodes=10, decay_type="exponential")
    initial_eps = agent.epsilon
    agent.decay_epsilon(1)
    assert agent.epsilon < initial_eps
    
    # Linear
    agent_lin = DQNAgent(4, 2, total_episodes=10, decay_type="linear")
    agent_lin.epsilon = 1.0
    agent_lin.eps_min = 0.1
    # decay linearly to eps_min over first 75% of episodes
    # eps_decay = (1.0 - 0.1) / (0.75 * 10) = 0.9 / 7.5 = 0.12
    initial_eps_lin = agent_lin.epsilon
    agent_lin.decay_epsilon(1)
    assert agent_lin.epsilon == initial_eps_lin - agent_lin.eps_decay
    
    # Above 75% it shouldn't decay further (though linear decay just checks < 0.75*total_episodes)
    eps_before = agent_lin.epsilon
    agent_lin.decay_epsilon(8)
    assert agent_lin.epsilon == eps_before

def test_dqn_agent_learn():
    agent = DQNAgent(4, 2)
    agent.batch_size = 4
    agent.learn_every = 2
    
    # Push dummy data
    for i in range(10):
        agent.buffer.push([0.1]*4, 0, 1.0, [0.2]*4, False)
        
    # _step_count = 0 initially
    
    # step 1, % learn_every != 0 -> returns early
    agent.learn()
    assert agent._step_count == 1
    
    # step 2, % learn_every == 0 -> learns
    agent.learn()
    assert agent._step_count == 2
    # we don't have a direct assert here, just ensure no errors are thrown during learning

def test_dqn_agent_learn_buffer_too_small():
    agent = DQNAgent(4, 2)
    agent.batch_size = 32
    agent.learn_every = 1
    
    # Only 5 items
    for i in range(5):
        agent.buffer.push([0.1]*4, 0, 1.0, [0.2]*4, False)
        
    agent.learn()
    # Should return early, no error

def test_dqn_agent_save_load_best():
    agent = DQNAgent(4, 2)
    
    # Modify a weight to test loading
    with torch.no_grad():
        agent.policy_net.net[0].weight.fill_(1.0)
        
    agent.save_best()
    
    with torch.no_grad():
        agent.policy_net.net[0].weight.fill_(0.0)
        
    assert (agent.policy_net.net[0].weight == 0.0).all()
    
    agent.load_best()
    
    assert (agent.policy_net.net[0].weight == 1.0).all()
    assert (agent.target_net.net[0].weight == 1.0).all()
    
def test_dqn_agent_load_best_none():
    agent = DQNAgent(4, 2)
    # Shouldn't error if _best_weights is None
    agent.load_best()
