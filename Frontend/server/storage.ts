import { db } from "./db";
import {
  simulationHistory,
  agentDecisions,
  demandData,
  demandModels,
  trainingConfigs,
  type InsertSimulationDay,
  type InsertAgentDecision,
  type InsertDemandData,
  type InsertDemandModel,
  type AgentDecision,
  type SimulationDay,
  type DemandPoint,
  type DemandModel,
  type TrainingConfig
} from "@shared/schema";
import { eq, desc, asc, sql } from "drizzle-orm";

export interface IStorage {
  // Simulation History
  addSimulationDay(day: InsertSimulationDay): Promise<SimulationDay>;
  getSimulationHistory(limit?: number): Promise<SimulationDay[]>;
  getLastSimulationState(): Promise<SimulationDay | undefined>;
  resetSimulation(): Promise<void>;

  // Agent Decisions
  createAgentDecision(decision: InsertAgentDecision): Promise<AgentDecision>;
  getPendingDecisions(): Promise<AgentDecision[]>;
  updateAgentDecision(id: number, updates: Partial<AgentDecision>): Promise<AgentDecision>;
  getDecisionById(id: number): Promise<AgentDecision | undefined>;

  // Demand Data
  addDemandData(data: InsertDemandData[]): Promise<void>;
  getDemandData(): Promise<DemandPoint[]>;

  // Demand Models
  getDemandModel(sku: string): Promise<DemandModel | undefined>;
  upsertDemandModel(model: InsertDemandModel): Promise<DemandModel>;

  // Training
  getTrainingConfig(): Promise<TrainingConfig>;
  updateTrainingConfig(updates: Partial<TrainingConfig>): Promise<TrainingConfig>;

  // Aggregates
  getDashboardStats(): Promise<{
    totalRevenue: number;
    stockoutDays: number;
    averageInventory: number;
    totalDays: number;
  }>;
}

export class DatabaseStorage implements IStorage {
  async addSimulationDay(day: InsertSimulationDay): Promise<SimulationDay> {
    const [entry] = await db.insert(simulationHistory).values(day).returning();
    return entry;
  }

  async getSimulationHistory(limit = 30): Promise<SimulationDay[]> {
    return await db.select()
      .from(simulationHistory)
      .orderBy(asc(simulationHistory.day))
      .limit(limit);
  }

  async getLastSimulationState(): Promise<SimulationDay | undefined> {
    const [last] = await db.select()
      .from(simulationHistory)
      .orderBy(desc(simulationHistory.day))
      .limit(1);
    return last;
  }

  async resetSimulation(): Promise<void> {
    await db.delete(simulationHistory);
    await db.delete(agentDecisions);
  }

  async createAgentDecision(decision: InsertAgentDecision): Promise<AgentDecision> {
    const [entry] = await db.insert(agentDecisions).values(decision).returning();
    return entry;
  }

  async getPendingDecisions(): Promise<AgentDecision[]> {
    return await db.select()
      .from(agentDecisions)
      .where(eq(agentDecisions.status, "pending"))
      .orderBy(asc(agentDecisions.simulationDay));
  }

  async updateAgentDecision(id: number, updates: Partial<AgentDecision>): Promise<AgentDecision> {
    const [entry] = await db.update(agentDecisions)
      .set(updates)
      .where(eq(agentDecisions.id, id))
      .returning();
    return entry;
  }

  async getDecisionById(id: number): Promise<AgentDecision | undefined> {
    const [entry] = await db.select().from(agentDecisions).where(eq(agentDecisions.id, id));
    return entry;
  }

  async addDemandData(data: InsertDemandData[]): Promise<void> {
    if (data.length === 0) return;
    await db.insert(demandData).values(data);
  }

  async getDemandData(): Promise<DemandPoint[]> {
    return await db.select().from(demandData).orderBy(asc(demandData.date));
  }

  async getDemandModel(sku: string): Promise<DemandModel | undefined> {
    const [model] = await db.select().from(demandModels).where(eq(demandModels.sku, sku));
    return model;
  }

  async upsertDemandModel(model: InsertDemandModel): Promise<DemandModel> {
    const [existing] = await db.select().from(demandModels).where(eq(demandModels.sku, model.sku));
    if (existing) {
      const [updated] = await db.update(demandModels).set(model).where(eq(demandModels.sku, model.sku)).returning();
      return updated;
    }
    const [inserted] = await db.insert(demandModels).values(model).returning();
    return inserted;
  }

  async getTrainingConfig(): Promise<TrainingConfig> {
    let [config] = await db.select().from(trainingConfigs);
    if (!config) {
      [config] = await db.insert(trainingConfigs).values({}).returning();
    }
    return config;
  }

  async updateTrainingConfig(updates: Partial<TrainingConfig>): Promise<TrainingConfig> {
    const config = await this.getTrainingConfig();
    const [updated] = await db.update(trainingConfigs).set(updates).where(eq(trainingConfigs.id, config.id)).returning();
    return updated;
  }

  async getDashboardStats() {
    const history = await db.select().from(simulationHistory);
    const pending = await db.select().from(agentDecisions).where(eq(agentDecisions.status, "pending"));

    if (history.length === 0) {
      return { totalRevenue: 0, stockoutDays: 0, averageInventory: 0, totalDays: 0, pendingDecisions: 0 };
    }

    const totalRevenue = history.reduce((acc, curr) => acc + Number(curr.reward), 0); // Using reward as proxy for revenue/profit
    const stockoutDays = history.filter(d => d.lostSales > 0).length;
    const averageInventory = history.reduce((acc, curr) => acc + curr.inventoryLevel, 0) / history.length;

    return {
      totalRevenue,
      stockoutDays,
      averageInventory,
      totalDays: history.length,
      pendingDecisions: pending.length
    };
  }
}

export const storage = new DatabaseStorage();
