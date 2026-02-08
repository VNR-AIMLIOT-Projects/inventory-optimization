import numpy as np
from collections import deque


class InventoryEnvironment:
   def __init__(self,
                historical_data,
                lead_time=2,
                max_order_qty=2000,
                action_step=50,
                holding_cost=5,
                stockout_penalty=200,
                order_fixed_cost=10,
                price=100,
                demand_scale=1.0):
      
       self.data = historical_data.reset_index(drop=True)
       self.lead_time = lead_time
       self.max_order_qty = max_order_qty
       self.action_step = action_step
      
       # Costs
       self.h = holding_cost
       self.c_stockout = stockout_penalty
       self.f = order_fixed_cost
       self.p = price
       self.demand_scale = demand_scale


       # --- KEY FIX 1: Define a Max Inventory Capacity ---
       # Prevents the "infinite hoarding" bug.
       # If stock > 10,000, the agent is physically blocked from ordering more.
       self.max_inventory = 10000


       # Action Space
       self.action_space = list(range(0, self.max_order_qty + self.action_step, self.action_step))
       self.action_size = len(self.action_space)


       # Reward Scaling (Prevents gradient explosion)
       self.reward_scale_factor = 0.0001


       self.order_pipeline = deque([0] * lead_time, maxlen=lead_time)
       self.reset()


   def reset(self):
       self.current_step = 0
       self.inv_onhand = 500
       self.last_demand = 0
       self.last_action = 0
       self.days_since_last_order = 0
       self.stockout_flag_last = 0
       self.order_pipeline = deque([0] * self.lead_time, maxlen=self.lead_time)
       return self._get_state()


   def _get_state(self):
       if self.current_step >= len(self.data):
           return None
          
       row = self.data.iloc[self.current_step]
       day_onehot = np.zeros(7)
       day_onehot[int(row["day_of_week"])] = 1
      
       # --- KEY FIX 2: Correct Normalization ---
       # We normalize inventory by MAX_INVENTORY (10,000), not max_order (2,000).
       # This keeps the Neural Network input between 0.0 and 1.0.
       norm_inv = np.clip(self.inv_onhand / self.max_inventory, 0, 1)
       norm_demand = np.clip(self.last_demand / self.max_order_qty, 0, 1)
       norm_action = self.last_action / self.max_order_qty


       state = np.array([
           norm_inv,         # Fixed normalization
           norm_demand,     
           norm_action,    
           *day_onehot,
           row["promo_flag"],
           self.days_since_last_order / 10.0,
           self.stockout_flag_last
       ], dtype=np.float32)
      
       return state


   def step(self, action_index):
       action = self.action_space[action_index]
      
       # --- KEY FIX 3: Hard Block on Hoarding ---
       # If we are already overstocked, FORCE action to 0.
       if self.inv_onhand > self.max_inventory:
           action = 0


       row = self.data.iloc[self.current_step]
       demand = int(row['demand'] * self.demand_scale)
      
       # 1. Arrivals
       incoming = self.order_pipeline.popleft()
       self.inv_onhand += incoming
      
       # 2. Sales
       units_sold = min(demand, self.inv_onhand)
       self.inv_onhand -= units_sold
       lost_sales = demand - units_sold
      
       # 3. Rewards
       revenue = self.p * units_sold
       holding = self.h * self.inv_onhand
       stockout_penalty = self.c_stockout * lost_sales
       order_cost = self.f if action > 0 else 0
      
       real_reward = revenue - holding - stockout_penalty - order_cost
      
       # 4. Scale Reward for Agent
       scaled_reward = real_reward * self.reward_scale_factor


       # 5. Pipeline & Memory
       self.order_pipeline.append(action)
       self.last_demand = demand
       self.last_action = action
       self.stockout_flag_last = int(lost_sales > 0)
       self.days_since_last_order = 0 if action > 0 else self.days_since_last_order + 1
      
       self.current_step += 1
       done = self.current_step >= len(self.data)
      
       info = {
           "date": row["date"],
           "demand": demand,
           "units_sold": units_sold,
           "inventory": self.inv_onhand,
           "action_order_qty": action
       }
      
       return self._get_state(), scaled_reward, done, info

