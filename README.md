# Inventory Optimization — quick start

This is a minimal README with steps to create the Python virtual environment used for experiments (`dqn_env`) and run the project scripts.

1) Create the virtual environment (macOS / Linux)

```bash
python3 -m venv dqn_env
```

2) Activate the virtual environment

```bash
source dqn_env/bin/activate
```

3) Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

4) Run the main training script

```bash
python experiments/basic-dqn-agent/dqn_inventory_complete.py
```

5) Deactivate environment when done

```bash
deactivate
```

Notes:
- If you use macOS with Apple Silicon and encounter issues with PyTorch, follow official PyTorch installation instructions for the correct wheel or use `pip` instructions from https://pytorch.org.
- If you already have a virtual environment with a different name, either rename it to `dqn_env` or update `.gitignore` to match.
