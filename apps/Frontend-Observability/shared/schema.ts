import { pgTable, text, serial, integer, boolean, timestamp, jsonb, decimal } from "drizzle-orm/pg-core";
import { createInsertSchema } from "drizzle-zod";
import { z } from "zod";

// === TABLE DEFINITIONS ===

// Stores user accounts
export const users = pgTable("users", {
  id: serial("id").primaryKey(),
  username: text("username").notNull().unique(), // We treat username as email logically
  firstName: text("first_name"),
  lastName: text("last_name"),
  password: text("password").notNull(),
});

// Stores the history of the simulation (daily stats)
export const simulationHistory = pgTable("simulation_history", {
  id: serial("id").primaryKey(),
  day: integer("day").notNull(),
  date: timestamp("date").notNull(),
  demand: integer("demand").notNull(),
  inventoryLevel: integer("inventory_level").notNull(),
  unitsSold: integer("units_sold").notNull(),
  lostSales: integer("lost_sales").notNull(),
  replenishmentOrders: integer("replenishment_orders").default(0),
  reward: decimal("reward").notNull(),
  isFestival: boolean("is_festival").default(false),
  createdAt: timestamp("created_at").defaultNow(),
});

// Stores decisions made by the agent
export const agentDecisions = pgTable("agent_decisions", {
  id: serial("id").primaryKey(),
  simulationDay: integer("simulation_day").notNull(),
  proposedAction: integer("proposed_action").notNull(),
  confidence: decimal("confidence"),
  reasoning: text("reasoning"),
  status: text("status", { enum: ["pending", "approved", "rejected", "overridden"] }).default("pending").notNull(),
  finalAction: integer("final_action"),
  reviewedAt: timestamp("reviewed_at"),
  createdAt: timestamp("created_at").defaultNow(),
});

// Stores demand upload metadata (file paths, not raw data)
export const demandUploads = pgTable("demand_uploads", {
  id: serial("id").primaryKey(),
  filename: text("filename").notNull(),
  filepath: text("filepath").notNull(),
  fileType: text("file_type").notNull(),           // csv / xlsx
  skus: jsonb("skus").default([]),                   // detected SKU names
  rowCount: integer("row_count").default(0),
  createdAt: timestamp("created_at").defaultNow(),
});

// Stores fitted demand models per SKU
export const demandModels = pgTable("demand_models", {
  id: serial("id").primaryKey(),
  sku: text("sku").notNull().unique(),
  festivals: jsonb("festivals").notNull(), // Array of { name, start, end }
  seasonality: text("seasonality").notNull(), // 'summer', 'winter', 'none'
  noiseLevel: decimal("noise_level").default("0.1"),
  windowSize: integer("window_size").default(7),
  createdAt: timestamp("created_at").defaultNow(),
});

// Stores training configuration and results
export const trainingConfigs = pgTable("training_configs", {
  id: serial("id").primaryKey(),
  stockoutPenalty: decimal("stockout_penalty").default("100").notNull(),
  holdingCost: decimal("holding_cost").default("2").notNull(),
  learningRate: decimal("learning_rate").default("0.001").notNull(),
  episodes: integer("episodes").default(100).notNull(),
  status: text("status", { enum: ["idle", "training", "completed", "failed"] }).default("idle").notNull(),
  learningCurve: jsonb("learning_curve"), // Array of numbers (rewards per episode)
  lastTrainedAt: timestamp("last_trained_at"),
});

// === SCHEMAS ===

export const insertUserSchema = createInsertSchema(users).omit({ id: true });
export const insertSimulationHistorySchema = createInsertSchema(simulationHistory).omit({ id: true, createdAt: true });
export const insertAgentDecisionSchema = createInsertSchema(agentDecisions).omit({ id: true, reviewedAt: true, createdAt: true });
export const insertDemandUploadSchema = createInsertSchema(demandUploads).omit({ id: true, createdAt: true });
export const insertDemandModelSchema = createInsertSchema(demandModels).omit({ id: true, createdAt: true });
export const insertTrainingConfigSchema = createInsertSchema(trainingConfigs).omit({ id: true, lastTrainedAt: true });

// === TYPES ===

export type User = typeof users.$inferSelect;
export type SimulationDay = typeof simulationHistory.$inferSelect;
export type AgentDecision = typeof agentDecisions.$inferSelect;
export type DemandUpload = typeof demandUploads.$inferSelect;
export type DemandModel = typeof demandModels.$inferSelect;
export type TrainingConfig = typeof trainingConfigs.$inferSelect;

export type InsertUser = z.infer<typeof insertUserSchema>;
export type InsertSimulationDay = z.infer<typeof insertSimulationHistorySchema>;
export type InsertAgentDecision = z.infer<typeof insertAgentDecisionSchema>;
export type InsertDemandUpload = z.infer<typeof insertDemandUploadSchema>;
export type InsertDemandModel = z.infer<typeof insertDemandModelSchema>;
export type InsertTrainingConfig = z.infer<typeof insertTrainingConfigSchema>;
