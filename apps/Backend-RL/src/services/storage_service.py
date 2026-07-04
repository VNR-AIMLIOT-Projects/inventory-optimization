"""
Local file storage service for model weights, training logs, and uploads.
"""

import os
import shutil
from datetime import datetime

STORAGE_DIR = os.environ.get("STORAGE_DIR")
if not STORAGE_DIR:
    raise ValueError("STORAGE_DIR environment variable is required.")

UPLOADS_DIR = os.path.join(STORAGE_DIR, "uploads")
MODELS_DIR = os.path.join(STORAGE_DIR, "models")
LOGS_DIR = os.path.join(STORAGE_DIR, "logs")

for d in [UPLOADS_DIR, MODELS_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)


def save_upload(filename: str, content: bytes) -> str:
    """Save an uploaded file and return the storage path."""
    filepath = os.path.join(UPLOADS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath


def save_model(agent, sku: str, run_id: int) -> str:
    """Save a trained DQN agent's weights and return the file path."""
    import torch
    filename = f"run_{run_id}_{sku}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pt"
    filepath = os.path.join(MODELS_DIR, filename)
    torch.save(agent.policy_net.state_dict(), filepath)
    return filepath


def load_model_weights(filepath: str):
    """Load model weights from a .pt file."""
    import torch
    return torch.load(filepath, map_location="cpu", weights_only=True)


def save_eval_graph(fig, sku: str, run_id: int) -> str:
    """Save an evaluation graph and return the file path."""
    filename = f"eval_run_{run_id}_{sku}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(LOGS_DIR, filename)
    fig.savefig(filepath, format="png", bbox_inches="tight", dpi=120)
    return filepath


def get_upload_path(filename: str) -> str:
    """Return the full path for an upload filename."""
    return os.path.join(UPLOADS_DIR, filename)
