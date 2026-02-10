
import { storage } from "../server/storage";
import { InventoryEnvironment } from "../server/simulation";
import { db } from "../server/db";
import { simulationHistory, agentDecisions } from "@shared/schema";

async function seed() {
  console.log("Seeding database...");
  
  // Clear existing
  await storage.resetSimulation();
  
  const env = new InventoryEnvironment();
  
  // Simulate 30 days
  for (let i = 0; i < 30; i++) {
    // Simple mock policy for seeding
    let action = 0;
    const state = env.getState();
    if (state.inventory < 30) {
      action = Math.min(20, 100 - state.inventory);
    }
    
    // Step environment
    const result = env.step(action);
    
    // Save to DB
    await storage.addSimulationDay({
      day: result.day,
      date: new Date(result.date),
      demand: result.demand,
      inventoryLevel: result.inventory,
      unitsSold: result.unitsSold,
      lostSales: result.lostSales,
      reward: result.reward.toString(),
      isFestival: result.isFestival,
      replenishmentOrders: result.replenishmentArrived
    });
  }
  
  // Add a pending decision
  await storage.createAgentDecision({
    simulationDay: 30,
    proposedAction: 20,
    confidence: "0.92",
    reasoning: "Low inventory detected (25 units). Replenishment needed to avoid stockout.",
    status: "pending"
  });

  console.log("Seeding complete!");
  process.exit(0);
}

seed().catch(console.error);
