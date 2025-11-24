# dqn_inventory_with_dataset.py
# Fixed & hardened version for single-SKU CSV + Poisson demand + DQN training

import os
import json
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import joblib
from sklearn.linear_model import PoissonRegressor

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import random
from collections import namedtuple, deque

# reproducibility
np.random.seed(0)
torch.manual_seed(0)
random.seed(0)

# device
if torch.backends.mps.is_available():
    device = torch.device("mps")
    print("Using Apple Silicon GPU (MPS)")
elif torch.cuda.is_available():
    device = torch.device("cuda:0")
    print("Using NVIDIA GPU (CUDA)")
else:
    device = torch.device("cpu")
    print("Using CPU")


# ------------------------------
# Utilities: scalers and preprocessing
# ------------------------------
def compute_scalers(df, business_limit=None):
    """Compute CAPACITY, DEMAND_SCALE, MAX_ORDER_QTY, DAYS_MAX and return dict."""

    annual_rate = 0.25  # 25%/year
    mean_unit_cost = float(df.get('Unit_Cost', pd.Series([14])).fillna(14).mean())
    HOLDING_COST_PER_UNIT = annual_rate/365.0 * mean_unit_cost  # ~0.01
    inventory = df['Inventory_Level'].dropna() if 'Inventory_Level' in df.columns else pd.Series(dtype=float)
    units = df['Units_Sold'].dropna() if 'Units_Sold' in df.columns else pd.Series(dtype=float)

    CAPACITY = int(math.ceil(1.2 * inventory.quantile(0.999))) if len(inventory) > 0 else 100
    DEMAND_SCALE = int(max(1, math.ceil(1.2 * units.quantile(0.995)))) if len(units) > 0 else 10
    HIST_Q = int(math.ceil(df['Order_Quantity'].quantile(0.995))) if 'Order_Quantity' in df.columns else 20
    if business_limit is None:
        MAX_ORDER_QTY = max(HIST_Q, 20)
    else:
        MAX_ORDER_QTY = max(business_limit, HIST_Q)

    # days between orders median
    if 'Date' in df.columns and 'Order_Quantity' in df.columns:
        df_sorted = df.sort_values('Date')
        orders = df_sorted[df_sorted['Order_Quantity'] > 0]
        if len(orders) >= 2:
            diffs = orders['Date'].diff().dt.days.dropna()
            median_days = int(diffs.median()) if len(diffs) > 0 else 30
            DAYS_MAX = min(365, 2 * median_days)
        else:
            DAYS_MAX = 60
    else:
        DAYS_MAX = 60

    #HOLDING_COST_PER_UNIT = 3  # business parameter (can be adjusted)

    scalers = {
        'CAPACITY': CAPACITY,
        'DEMAND_SCALE': DEMAND_SCALE,
        'MAX_ORDER_QTY': int(MAX_ORDER_QTY),
        'DAYS_MAX': int(DAYS_MAX),
        'HOLDING_COST_PER_UNIT': HOLDING_COST_PER_UNIT
    }
    return scalers


def build_lag_features(df, max_lag=7):
    """Create basic lag features used by demand model."""
    df = df.sort_values('Date').reset_index(drop=True)
    # ensure required columns exist
    if 'Units_Sold' not in df.columns:
        df['Units_Sold'] = 0
    if 'Order_Quantity' not in df.columns:
        df['Order_Quantity'] = 0
    if 'Inventory_Level' not in df.columns:
        df['Inventory_Level'] = 0
    if 'Promotion_Flag' not in df.columns:
        df['Promotion_Flag'] = 0
    if 'Stockout_Flag' not in df.columns:
        df['Stockout_Flag'] = 0

    df['last_demand'] = df['Units_Sold'].shift(1).fillna(0)
    df['last_action'] = df['Order_Quantity'].shift(1).fillna(0)

    # days_since_last_order
    days_since = []
    last_order_idx = None
    dates = df['Date']
    for i, row in df.iterrows():
        if i == 0:
            days_since.append(0)
            if row.get('Order_Quantity', 0) > 0:
                last_order_idx = i
            continue
        if row.get('Order_Quantity', 0) > 0:
            days_since.append(0)
            last_order_idx = i
        else:
            if last_order_idx is None:
                days_since.append((dates.iloc[i] - dates.iloc[0]).days)
            else:
                days_since.append((dates.iloc[i] - dates.iloc[last_order_idx]).days)
    df['days_since_last_order'] = days_since

    # day-of-week sin/cos
    dow = df['Date'].dt.dayofweek
    df['dow_sin'] = np.sin(2 * np.pi * dow / 7)
    df['dow_cos'] = np.cos(2 * np.pi * dow / 7)

    # stockout flag last week fraction
    df['stockout_last7'] = df['Stockout_Flag'].shift(1).rolling(7, min_periods=1).sum().fillna(0) / 7.0

    # promo
    df['promo_flag'] = df['Promotion_Flag'].fillna(0).astype(float)

    return df


# ------------------------------
# Demand model training (Poisson baseline)
# ------------------------------
def train_poisson_model(df, scalers, save_path='models/poisson.joblib'):
    """
    Train PoissonRegressor on decision-time features.
    Save model (and feature_names) to joblib and return the trained model object.
    """
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    df = build_lag_features(df)

    # Target y (handle censoring by replacing Units_Sold with Demand_Forecast when stockout + forecast exists)
    y = df['Units_Sold'].copy()
    if 'Stockout_Flag' in df.columns and 'Demand_Forecast' in df.columns:
        mask = (df['Stockout_Flag'] == 1) & (~df['Demand_Forecast'].isna())
        y.loc[mask] = df.loc[mask, 'Demand_Forecast']

    # Build features in the SAME order env._build_model_features uses
    X_df = pd.DataFrame()
    X_df['inv_onhand_norm'] = (df['Inventory_Level'] / scalers['CAPACITY']).clip(0, 1)
    X_df['last_demand_norm'] = (df['last_demand'] / scalers['DEMAND_SCALE']).clip(0, 1)
    X_df['last_action_norm'] = (df['last_action'] / max(1, scalers['MAX_ORDER_QTY'])).clip(0, 1)
    X_df['dow_sin'] = df['dow_sin']
    X_df['dow_cos'] = df['dow_cos']
    X_df['promo_flag'] = df['promo_flag']
    X_df['days_since_last_order_norm'] = (df['days_since_last_order'] / scalers['DAYS_MAX']).clip(0, 1)
    X_df['stockout_last7'] = df['stockout_last7']
    # inventory cost pressure: compute and clip
    unit_price_series = df['Unit_Price'].fillna(1.0)
    inv_cost_pressure = (scalers.get('HOLDING_COST_PER_UNIT', 3) / unit_price_series) * (df['Inventory_Level'] / scalers['CAPACITY'])
    X_df['inventory_cost_pressure_norm'] = np.clip(inv_cost_pressure.fillna(0), 0, 1)

    # Clean X_df: remove infs/nans and ensure numeric type
    X_df = X_df.replace([np.inf, -np.inf], np.nan).fillna(0).astype(float)

    # Mask valid rows
    mask_ok = (~y.isna()) & (~X_df.isna().any(axis=1))
    X_train = X_df.loc[mask_ok].values
    y_train = y.loc[mask_ok].values

    if len(X_train) < 10:
        raise ValueError("Not enough valid training rows for demand model after preprocessing.")

    # Fit PoissonRegressor with small regularization
    model = PoissonRegressor(alpha=1e-4, max_iter=1000)
    model.fit(X_train, y_train)

    # Save model + feature names
    joblib.dump({'model': model, 'feature_names': list(X_df.columns)}, save_path)
    print(f"Saved Poisson model to {save_path}")

    return model


# ------------------------------
# Environment (modified)
# ------------------------------
class InvOptEnv():
    """
    Inventory Optimization Environment which can run in 'sim' (sampled from demand model)
    or 'replay' (use dataset's Units_Sold values) mode.
    Discrete actions 0..20 map to [0, MAX_ORDER_QTY] and are feasibility-capped by capacity.
    """
    def __init__(self, df, demand_model_pipe=None, scalers=None, mode='sim', episode_length=None):
        self.df = df.sort_values('Date').reset_index(drop=True)
        self.n_total = len(self.df)
        self.current_idx = 0  # index into df (0-based)
        self.day_of_week = 0

        # inventory / pipeline state
        self.inv_level = 0
        self.order_arrival_list = []  # list of [arrival_idx, qty]

        # business params from scalers
        self.scalers = scalers or compute_scalers(self.df)
        self.capacity = self.scalers['CAPACITY']
        self.holding_cost = self.scalers.get('HOLDING_COST_PER_UNIT', 3)
        self.unit_price = 30
        self.fixed_order_cost = 50
        self.lead_time = int(self.df['Supplier_Lead_Time_Days'].iloc[0]) if 'Supplier_Lead_Time_Days' in self.df.columns else 14

        # demand model container (joblib dict with 'model' and 'feature_names') or None
        self.demand_model_pipe = demand_model_pipe
        self.mode = mode
        self.episode_length = episode_length or self.n_total

        # action mapping: discrete 0..20 -> qty
        self.action_size = 21

        # history tracking
        self.state_history = []
        self.action_history = []
        self.reward_history = []

        # rng
        self.rng = np.random.default_rng(0)

        # initialize a default reset
        self.reset(start_idx=0)

    def reset(self, start_idx=0):
        # initialize from dataset at start_idx
        self.start_idx = int(start_idx)
        self.current_idx = int(start_idx)
        row = self.df.iloc[self.current_idx]

        # initialize inventory from dataset Inventory_Level
        self.inv_level = int(row['Inventory_Level']) if not pd.isna(row['Inventory_Level']) else int(self.scalers['CAPACITY'] // 2)

        # build order_arrival_list from past orders that would arrive in future of start
        # In simulation mode, start with an empty pipeline (ignore historical dataset orders)
        if self.mode == 'sim':
            self.order_arrival_list = []
        else:
            # In replay mode, reconstruct pending orders from dataset
            self.order_arrival_list = []
            for j in range(0, self.current_idx + 1):
                q = int(self.df.iloc[j].get('Order_Quantity', 0) or 0)
                if q > 0:
                    arrival_idx = j + int(self.df.iloc[j].get('Supplier_Lead_Time_Days', self.lead_time))
                    if arrival_idx > self.current_idx:
                        self.order_arrival_list.append([arrival_idx, q])

        # self.order_arrival_list = []
        # for j in range(0, self.current_idx + 1):
        #     q = int(self.df.iloc[j].get('Order_Quantity', 0) or 0)
        #     if q > 0:
        #         arrival_idx = j + int(self.df.iloc[j].get('Supplier_Lead_Time_Days', self.lead_time))
        #         if arrival_idx > self.current_idx:
        #             self.order_arrival_list.append([arrival_idx, q])

        # last_demands and last_actions (size 7)
        self.last_demands = deque(maxlen=7)
        self.last_actions = deque(maxlen=7)
        history_slice = self.df.iloc[max(0, self.current_idx - 7):self.current_idx]
        for _, r in history_slice.iterrows():
            self.last_demands.append(int(r.get('Units_Sold', 0)))
            self.last_actions.append(int(r.get('Order_Quantity', 0)))
        while len(self.last_demands) < 7:
            self.last_demands.appendleft(0)
        while len(self.last_actions) < 7:
            self.last_actions.appendleft(0)

        # compute days_since_last_order
        prev_slice = self.df.iloc[:self.current_idx]
        prev_orders = prev_slice[prev_slice['Order_Quantity'] > 0] if len(prev_slice) > 0 else prev_slice[prev_slice.columns[0:0]]
        if len(prev_orders) > 0:
            last_order_date = prev_orders['Date'].iloc[-1]
            self.days_since_last_order = (row['Date'] - last_order_date).days
        else:
            self.days_since_last_order = self.scalers['DAYS_MAX']

        # day_of_week
        self.day_of_week = int(row['Date'].dayofweek)

        # clear histories
        self.state_history = []
        self.action_history = []
        self.reward_history = []

        self.step_logs=[]
        return self._build_state()

    def _map_action_index_to_qty(self, action_idx):
        # action_idx in [0,20] -> linear map to [0, MAX_ORDER_QTY]
        max_q = self.scalers['MAX_ORDER_QTY']
        qty = int(round((action_idx / (self.action_size - 1)) * max_q))
        return qty

    def _build_model_features(self):
        # build features in the same order as used in training
        inv_onhand = self.inv_level
        last_demand = int(self.last_demands[-1]) if len(self.last_demands) > 0 else 0
        last_action = int(self.last_actions[-1]) if len(self.last_actions) > 0 else 0
        dow_sin = math.sin(2 * math.pi * self.day_of_week / 7)
        dow_cos = math.cos(2 * math.pi * self.day_of_week / 7)
        promo_flag = float(self.df.iloc[self.current_idx].get('Promotion_Flag', 0) or 0)
        days_since_last_order = self.days_since_last_order
        stockout_last7 = float(self.df.iloc[self.current_idx].get('Stockout_Flag', 0) or 0)

        inv_onhand_norm = float(np.clip(inv_onhand / self.scalers['CAPACITY'], 0, 1))
        last_demand_norm = float(np.clip(last_demand / self.scalers['DEMAND_SCALE'], 0, 1))
        last_action_norm = float(np.clip(last_action / max(1, self.scalers['MAX_ORDER_QTY']), 0, 1))
        days_since_norm = float(np.clip(days_since_last_order / self.scalers['DAYS_MAX'], 0, 1))

        unit_price = float(self.df.iloc[self.current_idx].get('Unit_Price', 1.0) or 1.0)
        inventory_cost_pressure = (self.holding_cost / unit_price) * (inv_onhand / self.scalers['CAPACITY'])
        inventory_cost_pressure_norm = float(np.clip(inventory_cost_pressure, 0, 1))

        feat = np.array([inv_onhand_norm, last_demand_norm, last_action_norm,
                         dow_sin, dow_cos, promo_flag, days_since_norm, stockout_last7, inventory_cost_pressure_norm], dtype=np.float32)
        return feat

    def _build_state(self):
        feats = self._build_model_features()
        forecast_mu = 0.0
        forecast_var = 0.0
        if self.demand_model_pipe is not None:
            model_entry = self.demand_model_pipe
            # model_entry should be a dict with keys 'model' and 'feature_names' (joblib saved)
            model = model_entry['model'] if isinstance(model_entry, dict) else model_entry
            X_in = feats.reshape(1, -1)
            try:
                mu = float(model.predict(X_in)[0])
            except Exception:
                mu = 0.0
            forecast_mu = max(0.0, mu)
            forecast_var = forecast_mu  # Poisson var = mu

        mu_norm = float(np.clip(forecast_mu / self.scalers['DEMAND_SCALE'], 0, 1))
        var_norm = float(np.clip(forecast_var / (self.scalers['DEMAND_SCALE'] ** 2), 0, 1))

        state_vec = np.concatenate([feats, np.array([mu_norm, var_norm], dtype=np.float32)])
        return state_vec

    def step(self, action_idx):
        # map action index to actual qty and apply dynamic cap
        
        if self.current_idx >= self.n_total:
            return None, 0.0, True 
        order_qty = self._map_action_index_to_qty(action_idx)

        # compute inv_pos (on-hand + incoming pipeline)
        inv_pos = self.inv_level + sum([q for (_, q) in self.order_arrival_list])
        space_left = max(0, self.capacity - inv_pos)
        allowed_max = min(self.scalers['MAX_ORDER_QTY'], space_left)
        if order_qty > allowed_max:
            order_qty = allowed_max

        # place order
        if order_qty > 0:
            y = 1
            arrival_idx = self.current_idx + self.lead_time
            self.order_arrival_list.append([arrival_idx, order_qty])
        else:
            y = 0

        # process arrivals for current_idx
        arrivals_now = [o for o in self.order_arrival_list if o[0] == self.current_idx]
        for arr in arrivals_now:
            self.inv_level = min(self.capacity, self.inv_level + arr[1])
        # remove processed
        self.order_arrival_list = [o for o in self.order_arrival_list if o[0] != self.current_idx]

        # determine demand at this index
        if self.mode == 'replay':
            demand = int(self.df.iloc[self.current_idx]['Units_Sold'])
        else:
            if self.mode == 'sim' and self.demand_model_pipe is not None:
                model_entry = self.demand_model_pipe
                model = model_entry['model'] if isinstance(model_entry, dict) else model_entry
                feats = self._build_model_features()
                X_in = feats.reshape(1, -1)
                try:
                    mu = float(model.predict(X_in)[0])
                except Exception:
                    mu = 0.0
                mu = max(mu, 0.0)
                demand = int(self.rng.poisson(mu))
            else:
                demand = int(self.df.iloc[self.current_idx]['Units_Sold'])

        # sales and reward
        units_sold = min(demand, self.inv_level)
        inv_after=max(0, self.inv_level - units_sold)
        reward = (units_sold * self.unit_price - self.holding_cost * inv_after - y * self.fixed_order_cost)
        
        idx_for_row = min(self.current_idx, max(0, self.n_total - 1))
        row = self.df.iloc[idx_for_row].to_dict()
        log_row = {
            'global_idx': int(self.current_idx),
            'Date': row.get('Date'),
            'orig_Units_Sold': int(row.get('Units_Sold', np.nan)),
            'orig_Order_Quantity': int(row.get('Order_Quantity', 0)) if 'Order_Quantity' in row else 0,
            'action_idx': int(action_idx),
            'order_qty': int(order_qty),
            'demand_used': int(demand),                # sampled (sim) or dataset (replay)
            'units_sold': int(units_sold),
            'inv_before': int(self.inv_level),         # note: this is inventory at start of step (arrivals applied)
            'inv_after': int(inv_after),
            'reward': float(reward),
            'y_order_placed': int(y),
            'stockout_flag': int(row.get('Stockout_Flag', 0))
        }

        self.step_logs.append(log_row)

        # update inventory
        self.inv_level = inv_after

        # update history deques
        self.last_demands.append(units_sold)
        self.last_actions.append(order_qty)

        # advance time
        self.current_idx += 1
        if self.current_idx < self.n_total:
            self.day_of_week = int(self.df.iloc[self.current_idx]['Date'].dayofweek)
        # store
        state = self._build_state() if self.current_idx < self.n_total else None
        self.state_history.append(state)
        self.action_history.append(order_qty)
        self.reward_history.append(reward)
        # print(f"Step {self.current_idx}, mu={mu}, demand={demand}, inv_before={self.inv_level}")

        done = (self.current_idx >= min(self.start_idx + self.episode_length, self.n_total))

                # log step (capture original dataset row for debugging

        # row = self.df.iloc[self.current_idx].to_dict()


        return state, reward, done


# ------------------------------
# QNetwork, ReplayBuffer, Agent (unchanged)
# ------------------------------
class QNetwork(nn.Module):
    def __init__(self, state_size, action_size, seed, fc1_unit=128, fc2_unit=128):
        super(QNetwork, self).__init__()
        self.seed = torch.manual_seed(seed)
        self.fc1 = nn.Linear(state_size, fc1_unit)
        self.fc2 = nn.Linear(fc1_unit, fc2_unit)
        self.fc3 = nn.Linear(fc2_unit, action_size)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        return self.fc3(x)


class ReplayBuffer:
    def __init__(self, action_size, buffer_size, batch_size, seed):
        self.action_size = action_size
        self.memory = deque(maxlen=buffer_size)
        self.batch_size = batch_size
        self.experience = namedtuple("Experience", field_names=["state", "action", "reward", "next_state", "done"])
        self.seed = random.seed(seed)

    def add(self, state, action, reward, next_state, done):
        e = self.experience(state, action, reward, next_state, done)
        self.memory.append(e)

    def sample(self):
        experiences = random.sample(self.memory, k=self.batch_size)
        states = torch.from_numpy(np.vstack([e.state for e in experiences if e is not None])).float().to(device)
        actions = torch.from_numpy(np.vstack([e.action for e in experiences if e is not None])).long().to(device)
        rewards = torch.from_numpy(np.vstack([e.reward for e in experiences if e is not None])).float().to(device)
        next_states = torch.from_numpy(np.vstack([e.next_state for e in experiences if e is not None])).float().to(device)
        dones = torch.from_numpy(np.vstack([e.done for e in experiences if e is not None]).astype(np.uint8)).float().to(device)
        return (states, actions, rewards, next_states, dones)

    def __len__(self):
        return len(self.memory)


class Agent:
    def __init__(self, state_size, action_size, seed, lr=1e-4, buffer_size=int(5e5), batch_size=128, gamma=0.99, tau=1e-3, update_every=4):
        self.state_size = state_size
        self.action_size = action_size
        self.seed = random.seed(seed)
        self.lr = lr
        self.batch_size = batch_size
        self.gamma = gamma
        self.tau = tau
        self.update_every = update_every

        self.qnetwork_local = QNetwork(state_size, action_size, seed).to(device)
        self.qnetwork_target = QNetwork(state_size, action_size, seed).to(device)
        self.optimizer = optim.Adam(self.qnetwork_local.parameters(), lr=lr)
        self.memory = ReplayBuffer(action_size, buffer_size, batch_size, seed)
        self.t_step = 0

    def step(self, state, action, reward, next_state, done):

        self.memory.add(state, action, reward, next_state, done)
        self.t_step = (self.t_step + 1) % self.update_every
        if self.t_step == 0:
            if len(self.memory) > self.batch_size:
                experiences = self.memory.sample()
                self.learn(experiences)

    def act(self, state, eps=0.):
        state = torch.from_numpy(state).float().unsqueeze(0).to(device)
        self.qnetwork_local.eval()
        with torch.no_grad():
            action_values = self.qnetwork_local(state)
        self.qnetwork_local.train()
        if random.random() > eps:
            return np.argmax(action_values.cpu().data.numpy())
        else:
            return random.choice(np.arange(self.action_size))

    def learn(self, experiences):
        states, actions, rewards, next_states, dones = experiences
        Q_expected = self.qnetwork_local(states).gather(1, actions)
        Q_targets_next = self.qnetwork_target(next_states).detach().max(1)[0].unsqueeze(1)
        Q_targets = rewards + (self.gamma * Q_targets_next * (1 - dones))
        loss = F.mse_loss(Q_expected, Q_targets)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        for target_param, local_param in zip(self.qnetwork_target.parameters(), self.qnetwork_local.parameters()):
            target_param.data.copy_(self.tau * local_param.data + (1.0 - self.tau) * target_param.data)


# ------------------------------
# Training loop adapted to environment with dataset
# ------------------------------
def train_dqn(env, agent, n_episodes=300, eps_start=1.0, eps_end=0.01, eps_decay=0.995,
              start_once=True, sequential_start=True):
    """
    Train DQN.

    Args:
      env, agent: as before
      n_episodes: total episodes to run
      start_once: if True pick one random start index at beginning; else pick random each episode
      sequential_start: when start_once==True:
          - if True: episode k starts at start0 + (k-1)*episode_length (sequential windows)
          - if False: every episode uses the same start0 (fixed-start)
    """
    scores = []
    eps = eps_start

    # compute possible base starts (so that start + episode_length fits in dataset)
    max_start = max(0, env.n_total - env.episode_length)
    possible_starts = list(range(0, max(1, max_start+1)))

    # choose one random start if requested
    if start_once:
        # choose a single anchor start index uniformly from possible_starts
        if len(possible_starts) == 0:
            start0 = 0
        else:
            start0 = int(np.random.choice(possible_starts))
        # we'll advance from this anchor if sequential_start True
    else:
        start0 = None

    # aggregated logs holder (single CSV)
    all_logs = []

    for i_episode in range(1, n_episodes + 1):
        # decide start_idx for this episode
        if start_once:
            if sequential_start:
                # compute shifted start
                offset = (i_episode - 1) * env.episode_length
                start_idx = start0 + offset
                # if start_idx would exceed bounds, clamp so it fits
                if start_idx > max_start:
                    # clamp to the last allowed start to avoid overflow
                    start_idx = max_start
            else:
                # fixed-start: always same anchor
                start_idx = start0
        else:
            # original behaviour: random start each episode
            start_idx = int(np.random.choice(possible_starts)) if len(possible_starts) > 0 else 0

        # reset env to this start
        state = env.reset(start_idx=start_idx)
        score = 0

        # run one episode
        while True:
            action_idx = agent.act(state, eps)
            next_state, reward, done = env.step(action_idx)
            next_state_arr = np.zeros_like(state) if next_state is None else next_state
            agent.step(state, action_idx, reward, next_state_arr, done)
            state = next_state_arr
            score += reward
            if done:
                break

        # collect logs and score
        all_logs.extend(env.step_logs)
        scores.append(score)

        # epsilon decay and printing
        eps = max(eps * eps_decay, eps_end)
        if i_episode % 50 == 0:
            avg_score = np.mean(scores[-50:])
            print(f"Episode {i_episode}, AvgScore(last50)={avg_score:.2f}, eps={eps:.3f}")

    # save aggregated logs once
    all_logs_df = pd.DataFrame(all_logs)
    os.makedirs('results', exist_ok=True)
    all_logs_df.to_csv('results/all_episodes_logs.csv', index=False)
    print("Saved combined logs to results/all_episodes_logs.csv")

    return scores


def evaluate_sS_policy(s, S, df_slice, scalers):
    total_profit = 0
    inv_level = int(df_slice['Inventory_Level'].iloc[0]) if len(df_slice) > 0 else int(scalers['CAPACITY'] // 2)
    lead_time = int(df_slice['Supplier_Lead_Time_Days'].iloc[0]) if 'Supplier_Lead_Time_Days' in df_slice.columns else 14
    capacity = scalers['CAPACITY']
    holding_cost = scalers['HOLDING_COST_PER_UNIT']
    fixed_order_cost = 50
    unit_price = 30
    order_arrival_list = []

    for period in range(len(df_slice)):
        inv_pos = inv_level + sum([q for (_, q) in order_arrival_list])
        if inv_pos <= s:
            order_quantity = min(int(scalers['MAX_ORDER_QTY']), S - inv_pos)
            if order_quantity > 0:
                order_arrival_list.append([period + lead_time, order_quantity])
                y = 1
            else:
                y = 0
        else:
            order_quantity = 0
            y = 0
        # arrivals
        if order_arrival_list and period == order_arrival_list[0][0]:
            inv_level = min(capacity, inv_level + order_arrival_list[0][1])
            order_arrival_list.pop(0)
        demand = int(df_slice['Units_Sold'].iloc[period])
        units_sold = min(demand, inv_level)
        profit = (units_sold * unit_price - holding_cost * inv_level - y * fixed_order_cost)
        inv_level = max(0, inv_level - demand)
        total_profit += profit
    return total_profit


# ------------------------------
# Main: load data, compute scalers, train demand model, train DQN
# ------------------------------
def main():
    # path to your CSV (update if needed)
    data_path = '/Users/sujaynimmagadda/Documents/dqn_inventory_project/inventory-optimization/data/sku_24.csv'

    os.makedirs('models', exist_ok=True)
    os.makedirs('artifacts', exist_ok=True)
    os.makedirs('results', exist_ok=True)

    print('Loading dataset...')
    df = pd.read_csv(data_path, parse_dates=['Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    print(f'Dataset rows: {len(df)}')

    # compute scalers
    scalers = compute_scalers(df)
    json.dump(scalers, open('artifacts/scalers.json', 'w'))
    print('Scalers:', scalers)

    # train demand model (Poisson) and save
    model = train_poisson_model(df, scalers, save_path='models/poisson.joblib')
    demand_model_pipe = joblib.load('models/poisson.joblib')

    # create env and agent
    env = InvOptEnv(df, demand_model_pipe=demand_model_pipe, scalers=scalers, mode='sim', episode_length=30)
    state0 = env._build_state()
    state_size = state0.shape[0]
    action_size = 21
    agent = Agent(state_size=state_size, action_size=action_size, seed=0)

    print('Starting DQN training...')
    scores = train_dqn(env, agent, n_episodes=300)

    # save models
    torch.save(agent.qnetwork_local.state_dict(), 'models/dqn_inventory_model.pth')
    print('Saved DQN model to models/dqn_inventory_model.pth')

    # plot
    plt.plot(scores)
    plt.title('Training scores')
    plt.xlabel('Episode')
    plt.ylabel('Total reward')
    plt.savefig('results/training_scores.png', dpi=200)
    print('Saved training plot to results/training_scores.png')


if __name__ == '__main__':
    main()
