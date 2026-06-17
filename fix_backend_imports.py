import os
import glob
import re

replacements = [
    (r'^from database import ', r'from core.database import '),
    (r'^import database\b', r'from core import database'),
    
    (r'^from models import ', r'from models.domain import '),
    (r'^import models\b', r'from models import domain as models'),
    
    (r'^from schemas import ', r'from models.schemas import '),
    (r'^import schemas\b', r'from models import schemas'),
    
    (r'^from extracts_demand import ', r'from data_processing.extracts_demand import '),
    (r'^import extracts_demand\b', r'from data_processing import extracts_demand'),
    
    (r'^from demand import ', r'from data_processing.demand import '),
    (r'^import demand\b', r'from data_processing import demand'),
    
    (r'^from demand_modifier import ', r'from data_processing.demand_modifier import '),
    (r'^import demand_modifier\b', r'from data_processing import demand_modifier'),
    
    (r'^from dqn import ', r'from rl.dqn import '),
    (r'^import dqn\b', r'from rl import dqn'),
    
    (r'^from environment import ', r'from rl.environment import '),
    (r'^import environment\b', r'from rl import environment'),
    
    (r'^from trainer import ', r'from rl.trainer import '),
    (r'^import trainer\b', r'from rl import trainer'),
    
    (r'^from deployment_simulator import ', r'from rl.deployment_simulator import '),
    (r'^import deployment_simulator\b', r'from rl import deployment_simulator'),
    
    (r'^from queue_service import ', r'from services.queue_service import '),
    (r'^import queue_service\b', r'from services import queue_service'),
    
    (r'^from storage_service import ', r'from services.storage_service import '),
    (r'^import storage_service\b', r'from services import storage_service'),
    
    (r'^from export_service import ', r'from services.export_service import '),
    (r'^import export_service\b', r'from services import export_service'),
    
    (r'^from chatbot import ', r'from services.chat.chatbot import '),
    (r'^import chatbot\b', r'from services.chat import chatbot'),
    
    (r'^from copilot import ', r'from services.chat.copilot import '),
    (r'^import copilot\b', r'from services.chat import copilot'),
    
    (r'^from worker import ', r'from worker.celery_app import '),
    (r'^import worker\b', r'from worker import celery_app as worker'),
    
    (r'^from upload_security import ', r'from core.security import '),
    (r'^import upload_security\b', r'from core import security as upload_security'),
]

files = glob.glob('Backend-RL/tests/**/*.py', recursive=True)

for filepath in files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    lines = new_content.split('\n')
    for i, line in enumerate(lines):
        for pattern, replacement in replacements:
            lines[i] = re.sub(pattern, replacement, lines[i])
            
    new_content = '\n'.join(lines)
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")
