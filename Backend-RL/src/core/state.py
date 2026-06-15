from fastapi import WebSocket
import asyncio
from models.schemas import TrainingStatus

_store = {
    "raw_df": None,
    "modifier": None,
    "sku": None,
    "trained_agent": None,
    "train_rewards": [],
    "train_max_order": None,
    "train_action_step": None,
    "train_holding_cost": 5,
    "train_stockout_penalty": 200,
    "train_status": {
        "status": TrainingStatus.IDLE,
        "current_episode": 0,
        "total_episodes": 0,
        "best_reward": 0.0,
        "latest_reward": 0.0,
        "avg_reward_last_50": 0.0,
        "message": "",
    },
    "eval_results": None,
    "uploaded_filepath": None,
    "detected_params": None,
    "modified_params": None,
    "training_stop_requested": False,
    "train_started_at": None,
    "uploaded_file_id": None,
    "current_run_id": None,
    "per_sku_detected_params": {},
    "per_sku_modified_params": {},
    "per_sku_raw_dfs": {},
    "per_sku_modifiers": {},
    "multi_sku_status": {},
    "multi_sku_overall": TrainingStatus.IDLE,
    "multi_sku_agents": {},
    "multi_sku_rewards": {},
    "multi_sku_configs": {},
    "multi_sku_eval_results": {},
    "multi_sku_stop_requested": False,
}

class TrainingWSManager:
    def __init__(self):
        self.connections = []
        self._loop = None
        self._broadcast_count = 0

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        self._loop = asyncio.get_running_loop()
        print(f"[WS] Client connected. Total connections: {len(self.connections)}")
        try:
            await ws.send_json({"type": "connected", "message": "WebSocket connected"})
        except Exception:
            pass

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        print(f"[WS] Client disconnected. Total connections: {len(self.connections)}")

    def broadcast_from_thread(self, data: dict):
        if not self.connections or self._loop is None:
            return
        self._broadcast_count += 1
        if self._broadcast_count <= 3 or self._broadcast_count % 100 == 0:
            print(f"[WS] Broadcasting #{self._broadcast_count} to {len(self.connections)} client(s)")
        asyncio.run_coroutine_threadsafe(self._broadcast(data), self._loop)

    async def _broadcast(self, data: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception as e:
                print(f"[WS] send_json failed: {e}")
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = TrainingWSManager()
