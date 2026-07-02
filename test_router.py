import sys
sys.path.append("Backend-RL/src")
from services.chat.agents.orchestrator import handle_copilot_message

res = handle_copilot_message(
    page="stage1",
    user_message="Help me train the model.",
    context={},
    history=[]
)
print("Scenario 1 Output:", res["action"])

res2 = handle_copilot_message(
    page="modify",
    user_message="Decrease order cost by 5.",
    context={},
    history=[]
)
print("Scenario 2 Output:", res2["action"])
