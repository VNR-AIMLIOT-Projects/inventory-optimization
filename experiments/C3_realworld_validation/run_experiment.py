#!/usr/bin/env python3
"""
Experiment C3 Runner — Real-World Validation
=============================================
Runs both retail store validation and UCI online retail multi-SKU training sequentially.

Usage:
    py run_experiment.py
    py run_experiment.py --smoke-test
"""

import sys
import subprocess
from pathlib import Path

HERE = Path(__file__).parent

def main():
    smoke = "--smoke-test" in sys.argv
    episodes = None
    if "--episodes" in sys.argv:
        try:
            idx = sys.argv.index("--episodes")
            episodes = sys.argv[idx + 1]
        except (ValueError, IndexError):
            pass

    print("\n" + "=" * 55)
    print("  EXPERIMENT C3 - Real-World Validation")
    print("=" * 55)

    # 1. Dataset 1: Retail Store
    print("\n[C3] Running Dataset 1 (Retail Store Validation)...")
    runner1 = HERE / "dataset1_retail_store" / "run_validation.py"
    cmd1 = [sys.executable, str(runner1)]
    res1 = subprocess.run(cmd1, cwd=str(HERE / "dataset1_retail_store"))
    if res1.returncode != 0:
        print("[FAIL] Dataset 1 validation failed.")
        sys.exit(res1.returncode)
    print("[OK] Dataset 1 validation complete.")

    # 2. Dataset 2: UCI Online Retail
    print("\n[C3] Running Dataset 2 (UCI Online Multi-SKU)...")
    runner2 = HERE / "dataset2_uci_online" / "run_dataset_2.py"
    cmd2 = [sys.executable, str(runner2)]
    if smoke:
        cmd2.append("--smoke-test")
    elif episodes:
        cmd2 += ["--episodes", episodes]
    
    res2 = subprocess.run(cmd2, cwd=str(HERE / "dataset2_uci_online"))
    if res2.returncode != 0:
        print("[FAIL] Dataset 2 validation failed.")
        sys.exit(res2.returncode)
    print("[OK] Dataset 2 validation complete.")

    print("\n[OK] Experiment C3 complete.")

if __name__ == "__main__":
    main()
