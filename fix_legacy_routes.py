import re

with open('Backend-RL/src/api/routers/legacy_routes.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace FastAPI with APIRouter
content = content.replace('from fastapi import FastAPI', 'from fastapi import APIRouter')

# Replace app = FastAPI(...) with router = APIRouter()
content = re.sub(r'app\s*=\s*FastAPI\([^)]*\)', 'router = APIRouter()', content, flags=re.MULTILINE)

# Replace @app. with @router.
content = content.replace('@app.', '@router.')

# Remove CORS and error handler from legacy_routes since they are in main.py
content = re.sub(r'app\.add_middleware\([\s\S]*?\)', '', content)
content = re.sub(r'@router\.exception_handler[\s\S]*?return JSONResponse\([\s\S]*?\)', '', content)

with open('Backend-RL/src/api/routers/legacy_routes.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Updated legacy_routes.py")
