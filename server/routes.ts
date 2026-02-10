import type { Express } from "express";
import type { Server } from "http";
import { storage } from "./storage";
import { api } from "@shared/routes";
import { z } from "zod";
import { InventoryEnvironment } from "./simulation";
import multer from "multer";
import { parse } from "csv-parse";
import fs from "fs";

const upload = multer({ dest: '/tmp/' });

// Initialize the environment simulation
const env = new InventoryEnvironment();

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {

  // --- Simulation Routes ---

  app.get(api.simulation.state.path, async (req, res) => {
    const history = await storage.getSimulationHistory(50);
    const lastState = await storage.getLastSimulationState();
    
    res.json({
      currentDay: env.currentStep,
      inventory: env.invOnhand,
      lastDemand: env.lastDemand,
      isFestival: env.isFestival(env.currentStep),
      recentHistory: history
    });
  });

  app.post(api.simulation.reset.path, async (req, res) => {
    env.reset();
    await storage.resetSimulation();
    res.json({ message: "Simulation reset successfully" });
  });

  // This endpoint advances the simulation ONLY IF there are no pending decisions that block it.
  // In a real RL loop, this would be called by the agent loop.
  // Here, we can trigger it manually or have a background interval.
  app.post(api.simulation.nextStep.path, async (req, res) => {
    // Check if there are pending decisions for the current day
    const pending = await storage.getPendingDecisions();
    if (pending.length > 0) {
      return res.status(400).json({ message: "Cannot advance: Pending decisions exist." });
    }

    // Agent Logic (Heuristic / RL Mock)
    // 1. Observe state
    const state = env.getState();
    
    // 2. Decide action (Mock Agent)
    // Simple heuristic: if inventory < 30 or festival coming, order max.
    let action = 0;
    const isFestivalSoon = env.isFestival(env.currentStep + 2) || env.isFestival(env.currentStep + 5);
    
    if (state.inventory < 30 || isFestivalSoon) {
      action = Math.min(20, 100 - state.inventory); // Cap at max order
    }

    // 3. Propose action to human
    // We create a PENDING decision. The simulation does NOT advance yet. 
    // Ideally, the user approves this, and THEN we step.
    // For this prototype, we'll auto-approve if it's small, but pause for big orders?
    // User asked for approval flow. So we will create a pending decision and STOP.
    
    const decision = await storage.createAgentDecision({
      simulationDay: env.currentStep,
      proposedAction: Math.round(action),
      confidence: "0.85",
      reasoning: isFestivalSoon ? "Anticipating festival demand" : "Restocking low inventory",
      status: "pending"
    });

    // Return the decision, not the step result yet
    res.json({ message: "Agent proposed an action", decision });
  });

  // --- Decision Routes ---

  app.get(api.decisions.listPending.path, async (req, res) => {
    const pending = await storage.getPendingDecisions();
    res.json(pending);
  });

  app.post(api.decisions.review.path, async (req, res) => {
    const { id } = req.params;
    const { status, overrideValue } = req.body;
    
    const decision = await storage.getDecisionById(Number(id));
    if (!decision) return res.status(404).json({ message: "Decision not found" });

    let finalAction = decision.proposedAction;
    if (status === "rejected") finalAction = 0;
    if (status === "overridden" && overrideValue !== undefined) finalAction = overrideValue;

    // Update decision in DB
    const updated = await storage.updateAgentDecision(Number(id), {
      status,
      finalAction,
      reviewedAt: new Date()
    });

    // NOW execute the step in the environment with the FINAL action
    const stepResult = env.step(finalAction);
    
    // Save simulation step to DB
    await storage.addSimulationDay({
      day: stepResult.day,
      date: new Date(stepResult.date),
      demand: stepResult.demand,
      inventoryLevel: stepResult.inventory,
      unitsSold: stepResult.unitsSold,
      lostSales: stepResult.lostSales,
      reward: stepResult.reward.toString(),
      isFestival: stepResult.isFestival,
      replenishmentOrders: stepResult.replenishmentArrived 
    });

    res.json(updated);
  });

  // --- Demand / Stats Routes ---

  app.get(api.demand.list.path, async (req, res) => {
    const data = await storage.getDemandData();
    res.json(data);
  });

  app.get("/api/template", (req, res) => {
    const csvContent = "sku,date,value\nSKU001,2024-01-01,15\nSKU001,2024-01-02,20\nSKU002,2024-01-01,10\n";
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=demand_template.csv");
    res.send(csvContent);
  });

  app.post(api.demand.upload.path, upload.single('file'), async (req, res) => {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });
    
    const results: any[] = [];
    fs.createReadStream(req.file.path)
      .pipe(parse({ columns: true, trim: true }))
      .on('data', (data) => results.push(data))
      .on('error', (err) => {
        res.status(400).json({ message: "Error parsing CSV: " + err.message });
      })
      .on('end', async () => {
        try {
          // Validation: Check required columns
          if (results.length > 0) {
            const first = results[0];
            const hasSku = first.sku !== undefined;
            const hasDate = first.date !== undefined;
            const hasValue = first.value !== undefined || first.demand !== undefined || first.Value !== undefined;
            
            if (!hasSku || !hasDate || !hasValue) {
              return res.status(400).json({ message: "Invalid format. Required columns: sku, date, value" });
            }
          }

          // Validation: Minimum 1 year (365 days) of data
          // This is a rough check based on row count per SKU or unique dates
          const uniqueDates = new Set(results.map(r => r.date));
          if (uniqueDates.size < 365) {
            return res.status(400).json({ message: "At least 1 year (365 days) of demand data is required to start processing." });
          }

          const formatted = results.map(r => ({
            sku: r.sku,
            date: r.date,
            value: parseInt(r.value || r.demand || r.Value || "0"),
            category: "uploaded",
            notes: "Imported via CSV"
          }));
          
          await storage.addDemandData(formatted);
          res.status(201).json({ count: formatted.length });
        } catch (e) {
          res.status(400).json({ message: "Error processing CSV data: " + (e as Error).message });
        } finally {
          if (fs.existsSync(req.file!.path)) fs.unlinkSync(req.file!.path);
        }
      });
  });

  app.get(api.stats.get.path, async (req, res) => {
    const stats = await storage.getDashboardStats();
    res.json(stats);
  });

  // --- Demand Model Fitting ---

  app.get(api.demand.getModel.path, async (req, res) => {
    const model = await storage.getDemandModel(req.params.sku);
    if (!model) return res.status(404).json({ message: "Model not found" });
    res.json(model);
  });

  app.post(api.demand.fitModel.path, async (req, res) => {
    const sku = req.params.sku;
    // Mock fitting logic
    const model = await storage.upsertDemandModel({
      sku,
      festivals: req.body.festivals || [
        { name: "Festival A", start: 15, end: 19 },
        { name: "Festival B", start: 200, end: 204 }
      ],
      seasonality: req.body.seasonality || "summer",
      noiseLevel: req.body.noiseLevel || "0.1",
      windowSize: req.body.windowSize || 7
    });
    res.json(model);
  });

  // --- Training Routes ---

  app.get(api.training.getConfig.path, async (req, res) => {
    const config = await storage.getTrainingConfig();
    res.json(config);
  });

  app.post(api.training.updateConfig.path, async (req, res) => {
    const config = await storage.updateTrainingConfig(req.body);
    res.json(config);
  });

  app.post(api.training.start.path, async (req, res) => {
    await storage.updateTrainingConfig({ status: "training", learningCurve: [] });
    
    // Simulate training progress
    let rewards: number[] = [];
    let currentReward = -500;
    
    const interval = setInterval(async () => {
      currentReward += Math.random() * 50 - 10;
      rewards.push(currentReward);
      
      if (rewards.length >= 100) {
        clearInterval(interval);
        await storage.updateTrainingConfig({ 
          status: "completed", 
          learningCurve: rewards,
          lastTrainedAt: new Date()
        });
      } else {
        await storage.updateTrainingConfig({ learningCurve: rewards });
      }
    }, 100);

    res.json({ message: "Training started" });
  });

  return httpServer;
}
