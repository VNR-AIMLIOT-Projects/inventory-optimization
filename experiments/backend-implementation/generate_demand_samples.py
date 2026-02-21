"""
Utility script to generate N demand sample graphs using generate_demand().

Usage:
    python generate_demand_samples.py                   # 10 images, both seasons
    python generate_demand_samples.py -n 20             # 20 images
    python generate_demand_samples.py -n 5 --season summer
    python generate_demand_samples.py -n 5 --season winter
    python generate_demand_samples.py -n 10 --output my_folder
"""

import argparse
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from demand import generate_demand


def plot_demand(df, title, filepath):
    """Save a 2-panel demand overview (time-series + histogram) to filepath."""
    demand = df["Demand"].values
    dates  = df["Date"]
    avg    = np.mean(demand)

    fig, axes = plt.subplots(2, 1, figsize=(14, 8),
                             gridspec_kw={"height_ratios": [3, 1]})

    # --- Top: time-series ---
    ax = axes[0]
    ax.plot(dates, demand, color="steelblue", linewidth=0.9, label="Daily Demand")
    ax.axhline(avg, color="orange", linestyle="--", linewidth=1,
               label=f"Mean = {avg:.0f}")
    ax.fill_between(dates, demand, alpha=0.12, color="steelblue")
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Demand (units)")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.3)

    # Stats annotation
    stats = (f"min={demand.min()}  max={demand.max()}  "
             f"std={demand.std():.0f}  days={len(demand)}")
    ax.annotate(stats, xy=(0.01, 0.02), xycoords="axes fraction",
                fontsize=8, color="gray")

    # --- Bottom: histogram ---
    ax2 = axes[1]
    ax2.hist(demand, bins=40, color="steelblue", edgecolor="white", alpha=0.8)
    ax2.axvline(avg, color="orange", linestyle="--", linewidth=1)
    ax2.set_xlabel("Demand (units)")
    ax2.set_ylabel("Frequency")
    ax2.set_title("Demand Distribution")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(filepath, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Generate N synthetic demand sample graphs."
    )
    parser.add_argument(
        "-n", "--num",
        type=int,
        default=10,
        help="Number of demand graphs to generate (default: 10)"
    )
    parser.add_argument(
        "--season",
        choices=["summer", "winter", "both"],
        default="both",
        help="Season type to generate (default: both)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days per demand sample (default: 365)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="demands",
        help="Output folder name (default: demands)"
    )
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Determine which seasons to generate
    if args.season == "both":
        # Alternate summer/winter so we get a mix
        seasons = ["summer" if i % 2 == 0 else "winter" for i in range(args.num)]
    else:
        seasons = [args.season] * args.num

    print(f"Generating {args.num} demand graph(s) → '{args.output}/'")
    print(f"  Season : {args.season}  |  Days : {args.days}")

    for i in range(args.num):
        season = seasons[i]
        seed   = i + 1          # deterministic but varied across samples

        df = generate_demand(
            season_type=season,
            num_days=args.days,
            seed=seed
        )

        filename = os.path.join(args.output, f"demand_{i+1:03d}_{season}_seed{seed}.png")
        title    = f"Sample {i+1}/{args.num} — {season.upper()}  (seed={seed})"

        plot_demand(df, title, filename)
        print(f"  [{i+1:>{len(str(args.num))}}/{args.num}] Saved: {filename}")

    print(f"\nDone. {args.num} image(s) saved to '{args.output}/'")


if __name__ == "__main__":
    main()
