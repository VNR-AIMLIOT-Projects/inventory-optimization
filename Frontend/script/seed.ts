import "dotenv/config";
import { storage } from "../server/storage";
import { InventoryEnvironment } from "../server/simulation";

async function seed() {
  console.log("🌱 Seeding database...\n");

  // ==========================================
  // STAGE 1: Demand Data (for SKU charts)
  // ==========================================
  console.log("📦 Stage 1: Inserting demand data...");

  const skus = ["SKU001", "SKU002", "SKU003"];
  const demandRows: {
    sku: string;
    date: string;
    value: number;
    category: string;
    notes: string;
  }[] = [];

  for (const sku of skus) {
    const baseDate = new Date("2024-01-01");
    const baseDemand = sku === "SKU001" ? 20 : sku === "SKU002" ? 35 : 15;

    for (let day = 0; day < 365; day++) {
      const date = new Date(baseDate);
      date.setDate(date.getDate() + day);

      // Seasonality: higher demand in summer (days 150-240)
      let seasonal = 0;
      if (day >= 150 && day <= 240) seasonal = 15;

      // Festival spikes
      let festivalBoost = 0;
      const festivals = [
        [15, 19],
        [60, 64],
        [120, 124],
        [200, 204],
        [250, 254],
        [310, 314],
      ];
      for (const [start, end] of festivals) {
        if (day >= start && day <= end) {
          festivalBoost = 20 + Math.floor(Math.random() * 10);
          break;
        }
      }

      // Weekly pattern (lower on weekends)
      const dayOfWeek = date.getDay();
      const weekendDip = dayOfWeek === 0 || dayOfWeek === 6 ? -5 : 0;

      const noise = Math.floor(Math.random() * 10) - 5;
      const value = Math.max(
        1,
        baseDemand + seasonal + festivalBoost + weekendDip + noise
      );

      demandRows.push({
        sku,
        date: date.toISOString().split("T")[0],
        value,
        category: festivalBoost > 0 ? "festival" : "general",
        notes:
          festivalBoost > 0
            ? "Festival period"
            : seasonal > 0
              ? "Summer season"
              : "Regular",
      });
    }
  }

  await storage.addDemandData(demandRows);
  console.log(`   ✅ Inserted ${demandRows.length} demand records for ${skus.length} SKUs\n`);

  // ==========================================
  // STAGE 3: Simulation History + Decisions
  // ==========================================
  console.log("🎮 Stage 3: Running simulation...");

  // Clear existing simulation data
  await storage.resetSimulation();

  const env = new InventoryEnvironment();

  // Simulate 60 days of operations
  for (let i = 0; i < 60; i++) {
    const state = env.getState();
    let action = 0;

    // Smarter heuristic agent
    const isFestivalSoon =
      env.isFestival(env.currentStep + 2) ||
      env.isFestival(env.currentStep + 5);

    if (state.inventory < 30 || isFestivalSoon) {
      action = Math.min(20, 100 - state.inventory);
    } else if (state.inventory < 50) {
      action = Math.min(10, 100 - state.inventory);
    }

    const result = env.step(action);

    await storage.addSimulationDay({
      day: result.day,
      date: new Date(result.date),
      demand: result.demand,
      inventoryLevel: result.inventory,
      unitsSold: result.unitsSold,
      lostSales: result.lostSales,
      reward: result.reward.toString(),
      isFestival: result.isFestival,
      replenishmentOrders: result.replenishmentArrived,
    });

    // Create some historical approved/rejected decisions
    if (action > 0) {
      const statuses = ["approved", "approved", "approved", "overridden"] as const;
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      await storage.createAgentDecision({
        simulationDay: result.day,
        proposedAction: action,
        confidence: (0.7 + Math.random() * 0.25).toFixed(2),
        reasoning: isFestivalSoon
          ? "Festival demand anticipated — pre-stocking recommended"
          : state.inventory < 30
            ? `Low inventory alert (${state.inventory} units) — replenishment needed`
            : `Moderate inventory (${state.inventory} units) — small top-up suggested`,
        status,
      });
    }
  }

  // Add 2 pending decisions for the human-in-the-loop panel
  await storage.createAgentDecision({
    simulationDay: 60,
    proposedAction: 18,
    confidence: "0.91",
    reasoning:
      "Inventory at 22 units — below safety threshold. Festival period approaching in 3 days. Recommend maximum replenishment.",
    status: "pending",
  });

  await storage.createAgentDecision({
    simulationDay: 61,
    proposedAction: 12,
    confidence: "0.78",
    reasoning:
      "Moderate demand forecast for next week. Current stock adequate but proactive restocking advised to maintain 95%+ fulfillment rate.",
    status: "pending",
  });

  console.log("   ✅ Simulated 60 days of operations");
  console.log("   ✅ Created agent decisions (approved + pending)\n");

  console.log("🎉 Seeding complete! Restart the dev server to see all data.");
  process.exit(0);
}

seed().catch((err) => {
  console.error("❌ Seeding failed:", err);
  process.exit(1);
});
