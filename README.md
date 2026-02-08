# Project Setup Instructions

## 1. Create a Virtual Environment

Open a terminal in the project root directory and run:

```
python3 -m venv venv
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

Navigate to the relevant implementation folder (e.g., `experiments/backend-implementation/` or `experiments/baseline-implementation/`) and install dependencies:

```
pip install -r requirements.txt
```

## 4. Run the Project

Example (from backend-implementation):
```
python main.py
```

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
