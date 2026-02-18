# Project Setup Instructions

## 1. Create a Virtual Environment

Open a terminal in the project root directory and run:

```
python -m venv venv
```

## 2. Activate the Virtual Environment

On macOS/Linux:
```
source venv/bin/activate
```
On Windows:
```
venv\Scripts\activate
```

## 3. Install Required Packages

```
cd experiments/backend-implementation
pip install -r requirements.txt
```

## 4. Run the Project

```
uvicorn app:app --reload --port 8000
```

API Docs: http://localhost:8000/docs

## Notes
- Ensure you are using the virtual environment for all Python commands.
- To deactivate the environment, run:
  ```
  deactivate
  ```
- If you add new packages, update the `requirements.txt` file with:
  ```
  pip freeze > requirements.txt
  ```