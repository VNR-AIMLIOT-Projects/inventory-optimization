import ast
import os

with open("Backend-RL/src/app.py", "r", encoding="utf-8") as f:
    source = f.read()

tree = ast.parse(source)

routers = {
    "demand": [],
    "training": [],
    "evaluation": [],
    "deployment": [],
    "history": [],
    "chat": [],
    "system": [],
    "export": []
}

def get_router_name(path):
    if "/api/demand" in path:
        return "demand"
    elif "/api/copilot" in path or "/api/demand/chat" in path:
        return "chat"
    elif "/api/train" in path or "/ws/train" in path:
        return "training"
    elif "/api/evaluate" in path:
        return "evaluation"
    elif "/api/deploy" in path:
        return "deployment"
    elif "/api/runs" in path or "/api/history" in path or "/api/uploads" in path:
        return "history"
    elif "/api/export" in path:
        return "export"
    else:
        return "system"

for node in tree.body:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                if decorator.func.value.id == "app":
                    path = decorator.args[0].value if decorator.args else ""
                    router = get_router_name(path)
                    
                    # We won't literally extract using ast because preserving comments and formatting is hard
                    # We just note where they are.
print("Parsed routes successfully.")
