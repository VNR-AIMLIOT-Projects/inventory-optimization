import numpy as np
from collections import deque


class InventoryEnvironment:
   def __init__(self,
                historical_data,
                lead_time=2,
                max_order_qty=2000,
                action_step=20,
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

       # Demand-proportional max inventory (~10 days supply)
       avg_demand = self.data['demand'].mean() * demand_scale
       self.max_inventory = int(avg_demand * 10)

       # Action Space
       self.action_space = list(range(0, self.max_order_qty + self.action_step, self.action_step))
       self.action_size = len(self.action_space)

       # --- FIX: Dynamic reward scaling based on demand magnitude ---
       # Instead of a fixed 0.0001, scale so that a "typical" reward maps to ~[-1, +1]
       # Typical best-case reward per step ≈ price * avg_demand
       self.reward_scale_factor = 1.0 / max(1.0, self.p * avg_demand)

       self.order_pipeline = deque([0] * lead_time, maxlen=lead_time)
       self.reset()


   def reset(self):
       # --- FIX: Start with demand-proportional inventory, not hardcoded 500 ---
       avg_demand = self.data['demand'].mean() * self.demand_scale
       self.current_step = 0
       self.inv_onhand = int(avg_demand * 3)  # ~3 days of supply
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
      
       norm_inv = np.clip(self.inv_onhand / self.max_inventory, 0, 1)
       norm_demand = np.clip(self.last_demand / self.max_order_qty, 0, 1)
       norm_action = self.last_action / self.max_order_qty

       # --- FIX: Add pipeline inventory to state so agent knows orders are coming ---
       norm_pipeline = np.clip(sum(self.order_pipeline) / self.max_order_qty, 0, 1)

       state = np.array([
           norm_inv,
           norm_demand,     
           norm_action,
           norm_pipeline,    # NEW: agent can see pending orders
           *day_onehot,
           row["promo_flag"],
           self.days_since_last_order / 10.0,
           self.stockout_flag_last
       ], dtype=np.float32)
      
       return state


   def step(self, action_index):
       action = self.action_space[action_index]
      
       # Hard block on hoarding
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

       # --- FIX: Stronger, cleaner holding cost ---
       # Safety buffer = ~2 days demand (reasonable safety stock)
       safety_buffer = demand * 2
       excess = max(0, self.inv_onhand - safety_buffer)
       
       # Linear cost on all inventory + STRONG quadratic on excess
       # Coefficient 0.1 (not 0.01) makes excess of 500 cost:
       #   linear: 5*500 = 2,500
       #   quadratic: 0.5 * 500² = 125,000
       # vs stockout of 150: 200*150 = 30,000
       # Now over-stocking by 500 is 4x WORSE than a full stockout
       holding = self.h * self.inv_onhand + (self.h * 0.1) * (excess ** 2)
       
       stockout_penalty = self.c_stockout * lost_sales
       order_cost = self.f if action > 0 else 0
      
       real_reward = revenue - holding - stockout_penalty - order_cost
      
       # 4. Scale Reward (now dynamic, not fixed 0.0001)
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