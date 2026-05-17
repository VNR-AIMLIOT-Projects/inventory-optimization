#!/usr/bin/env python3
"""
run_all_experiments.py — Sequential master runner
==================================================
Runs A1-v2, A2, A3, B1 back-to-back with 500 episodes each.
Results are written into each experiment's results/ and plots/ folders.

Usage:
    python3 run_all_experiments.py
    python3 run_all_experiments.py --smoke-test    # 50 eps each (~8 min total)
"""

import subprocess, sys, time, json
from pathlib import Path

HERE = Path(__file__).parent
EXPERIMENTS = [
    ("A1_two_echelon_linear",  "Experiment A1 — 2-Echelon Linear DDQN (re-run, tuned)"),
    ("A2_three_echelon_linear","Experiment A2 — 3-Echelon Linear DDQN"),
    ("A3_divergent_one_to_two","Experiment A3 — Divergent 1→2 DDQN"),
    ("B1_state_ablation",      "Experiment B1 — IS vs ES State Ablation"),
]


def run_experiment(folder, label, smoke=False):
    runner = HERE / folder / "run_experiment.py"
    args   = [sys.executable, str(runner)]
    if smoke:
        args.append("--smoke-test")
    else:
        args += ["--episodes", "500"]

    print(f"\n{'#'*66}")
    print(f"  STARTING: {label}")
    print(f"  Folder  : {folder}")
    print(f"{'#'*66}")
    t0 = time.time()

    result = subprocess.run(args, cwd=str(HERE / folder))
    elapsed = time.time() - t0

    if result.returncode == 0:
        print(f"\n  ✅  {label} — DONE in {elapsed/60:.1f} min")
        return True, elapsed
    else:
        print(f"\n  ❌  {label} — FAILED (exit code {result.returncode})")
        return False, elapsed


def main():
    smoke = "--smoke-test" in sys.argv

    print(f"\n{'='*66}")
    print(f"  REPLENIX MULTI-ECHELON EXPERIMENT SUITE")
    print(f"  Mode: {'SMOKE TEST (50 eps each)' if smoke else 'FULL RUN (500 eps each)'}")
    print(f"{'='*66}")

    summary = []
    total_t = time.time()

    for folder, label in EXPERIMENTS:
        ok, elapsed = run_experiment(folder, label, smoke)
        summary.append({"experiment": folder, "label": label,
                         "success": ok, "runtime_min": round(elapsed/60, 2)})

    total_elapsed = time.time() - total_t

    print(f"\n{'='*66}")
    print(f"  ALL EXPERIMENTS COMPLETE — Total: {total_elapsed/60:.1f} min")
    print(f"{'='*66}")
    for s in summary:
        icon = "✅" if s["success"] else "❌"
        print(f"  {icon}  {s['label']:<45} {s['runtime_min']:>6.1f} min")

    (HERE / "run_summary.json").write_text(
        json.dumps({"smoke": smoke, "experiments": summary,
                    "total_runtime_min": round(total_elapsed/60, 2)}, indent=2)
    )
    print(f"\n  Run summary → {HERE/'run_summary.json'}")


if __name__ == "__main__":
    main()
