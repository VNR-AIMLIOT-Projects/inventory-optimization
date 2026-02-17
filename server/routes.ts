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

// --- Smart column detection helpers ---

const SKU_ALIASES = ['sku', 'sku_id', 'skuid', 'product', 'product_id', 'productid', 'product_name', 'productname', 'item', 'item_id', 'itemid', 'item_name', 'itemname', 'item_code', 'itemcode', 'material', 'material_id', 'part', 'part_number', 'partnumber', 'upc', 'barcode', 'asin', 'article', 'article_id', 'code', 'id', 'name'];
const DATE_ALIASES = ['date', 'dates', 'day', 'time', 'timestamp', 'datetime', 'date_time', 'period', 'order_date', 'orderdate', 'sale_date', 'saledate', 'transaction_date', 'transactiondate', 'created', 'created_at', 'createdat', 'week', 'month', 'year'];
const VALUE_ALIASES = ['value', 'values', 'demand', 'quantity', 'qty', 'units', 'units_sold', 'unitssold', 'sales', 'amount', 'count', 'volume', 'orders', 'order_qty', 'orderqty', 'sold', 'consumption', 'usage', 'total', 'num', 'number'];
const CATEGORY_ALIASES = ['category', 'categories', 'type', 'group', 'class', 'segment', 'department', 'dept', 'family', 'subcategory', 'sub_category', 'classification', 'brand', 'vendor', 'supplier', 'channel', 'region', 'store', 'location', 'warehouse'];

function detectColumn(headers: string[], aliases: string[]): string | null {
  const normalized = headers.map(h => h.toLowerCase().replaceAll(/[^a-z0-9]/g, ''));
  for (const alias of aliases) {
    const clean = alias.replaceAll(/[^a-z0-9]/g, '');
    const idx = normalized.indexOf(clean);
    if (idx !== -1) return headers[idx];
  }
  // Fuzzy: check if any header contains an alias as substring
  for (const alias of aliases) {
    const clean = alias.replaceAll(/[^a-z0-9]/g, '');
    const idx = normalized.findIndex(h => h.includes(clean) || clean.includes(h));
    if (idx !== -1) return headers[idx];
  }
  return null;
}

function parseFlexibleDate(raw: string): string {
  if (!raw) return new Date().toISOString().split('T')[0];
  const trimmed = raw.trim();

  // Already ISO: 2024-01-15 or 2024-01-15T...
  if (/^\d{4}-\d{2}-\d{2}/.test(trimmed)) return trimmed.split('T')[0];

  // MM/DD/YYYY or M/D/YYYY
  let m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(trimmed);
  if (m) return `${m[3]}-${m[1].padStart(2,'0')}-${m[2].padStart(2,'0')}`;

  // DD-MM-YYYY or DD.MM.YYYY
  m = /^(\d{1,2})[.-](\d{1,2})[.-](\d{4})$/.exec(trimmed);
  if (m) {
    const a = Number.parseInt(m[1]);
    // Heuristic: if first > 12, it's DD-MM-YYYY
    if (a > 12) return `${m[3]}-${m[2].padStart(2,'0')}-${m[1].padStart(2,'0')}`;
    // Otherwise treat as MM-DD-YYYY
    return `${m[3]}-${m[1].padStart(2,'0')}-${m[2].padStart(2,'0')}`;
  }

  // YYYY/MM/DD
  m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(trimmed);
  if (m) return `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`;

  // Month name formats: "Jan 15, 2024" / "15 Jan 2024" / "January 15 2024"
  const months: Record<string, string> = { jan:'01',feb:'02',mar:'03',apr:'04',may:'05',jun:'06',jul:'07',aug:'08',sep:'09',oct:'10',nov:'11',dec:'12' };
  const monthPattern = /([a-zA-Z]+)[\s,]+(\d{1,2})[\s,]+(\d{4})/.exec(trimmed);
  if (monthPattern) {
    const mon = months[monthPattern[1].slice(0,3).toLowerCase()];
    if (mon) return `${monthPattern[3]}-${mon}-${monthPattern[2].padStart(2,'0')}`;
  }
  const monthPattern2 = /(\d{1,2})[\s,]+([a-zA-Z]+)[\s,]+(\d{4})/.exec(trimmed);
  if (monthPattern2) {
    const mon = months[monthPattern2[2].slice(0,3).toLowerCase()];
    if (mon) return `${monthPattern2[3]}-${mon}-${monthPattern2[1].padStart(2,'0')}`;
  }

  // YYYYMMDD (compact)
  m = /^(\d{4})(\d{2})(\d{2})$/.exec(trimmed);
  if (m) return `${m[1]}-${m[2]}-${m[3]}`;

  // Fallback: try JS Date constructor
  const d = new Date(trimmed);
  if (!Number.isNaN(d.getTime())) return d.toISOString().split('T')[0];

  // Last resort
  return trimmed;
}

function detectValueColumn(headers: string[], results: any[], skuCol: string | null, dateCol: string | null): string | null {
  for (const h of headers) {
    const sample = results.slice(0, 5).map(r => r[h]);
    if (sample.every(v => v !== undefined && v !== '' && !Number.isNaN(Number(v)))) {
      return h;
    }
  }
  return null;
}

function detectDateColumn(headers: string[], results: any[], skuCol: string | null, valueCol: string | null): string | null {
  for (const h of headers) {
    if (h === valueCol || h === skuCol) continue;
    const sample = results.slice(0, 5).map(r => r[h]);
    const looksLikeDate = sample.every(v => {
      if (!v) return false;
      const d = new Date(v);
      return !Number.isNaN(d.getTime()) || /\d{4}/.test(v) || /\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}/.test(v);
    });
    if (looksLikeDate) return h;
  }
  return null;
}

function detectSkuColumn(headers: string[], results: any[], valueCol: string | null, dateCol: string | null): string | null {
  for (const h of headers) {
    if (h === valueCol || h === dateCol) continue;
    const sample = results.slice(0, 5).map(r => r[h]);
    const looksLikeId = sample.every(v => v !== undefined && v !== '' && Number.isNaN(Number(v)));
    if (looksLikeId) return h;
  }
  return null;
}

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
    const csvContent = "product_id,date,demand\nSKU001,2024-01-01,15\nSKU001,2024-01-02,20\nSKU002,2024-01-01,10\n";
    res.setHeader("Content-Type", "text/csv");
    res.setHeader("Content-Disposition", "attachment; filename=demand_template.csv");
    res.send(csvContent);
  });


  app.post(api.demand.upload.path, upload.single('file'), async (req, res) => {
    if (!req.file) return res.status(400).json({ message: "No file uploaded" });
    
    const results: any[] = [];
    fs.createReadStream(req.file.path)
      .pipe(parse({ columns: true, trim: true, skip_empty_lines: true, relax_column_count: true }))
      .on('data', (data) => results.push(data))
      .on('error', (err) => {
        res.status(400).json({ message: "Error parsing CSV: " + err.message });
      })
      .on('end', async () => {
        try {
          if (results.length === 0) {
            return res.status(400).json({ message: "The uploaded file contains no data rows." });
          }

          const headers = Object.keys(results[0]);

          // Smart column detection — first by alias, then by content heuristics
          const skuCol = detectColumn(headers, SKU_ALIASES);
          const dateCol = detectColumn(headers, DATE_ALIASES);
          const valueCol = detectColumn(headers, VALUE_ALIASES);
          const categoryCol = detectColumn(headers, CATEGORY_ALIASES);

          const resolvedValueCol = valueCol ?? detectValueColumn(headers, results, skuCol, dateCol);
          const resolvedDateCol = dateCol ?? detectDateColumn(headers, results, skuCol, resolvedValueCol);
          const resolvedSkuCol = skuCol ?? detectSkuColumn(headers, results, resolvedValueCol, resolvedDateCol);

          if (!resolvedValueCol) {
            return res.status(400).json({
              message: `Could not identify a numeric demand/value column. Found columns: [${headers.join(', ')}]. Please include a column with numeric demand values.`,
            });
          }

          // Build mapping info for the response
          const mapping: Record<string, string> = {};
          if (resolvedSkuCol) mapping['sku'] = resolvedSkuCol;
          if (resolvedDateCol) mapping['date'] = resolvedDateCol;
          mapping['value'] = resolvedValueCol;
          if (categoryCol) mapping['category'] = categoryCol;

          const formatted = results.map(r => {
            const val = r[resolvedValueCol];
            return {
              sku: resolvedSkuCol ? String(r[resolvedSkuCol]) : 'DEFAULT',
              date: resolvedDateCol ? parseFlexibleDate(String(r[resolvedDateCol])) : new Date().toISOString().split('T')[0],
              value: Number.parseInt(val) || Math.round(Number.parseFloat(val)) || 0,
              category: categoryCol ? String(r[categoryCol]) : 'uploaded',
              notes: 'Imported via CSV',
            };
          });

          // Filter out rows where sku is empty (likely bad rows)
          const cleaned = formatted.filter(r => r.sku && r.sku !== 'undefined' && r.sku !== 'null');

          if (cleaned.length === 0) {
            return res.status(400).json({ message: "No valid data rows found after processing." });
          }

          await storage.addDemandData(cleaned);
          const skuLabel = resolvedSkuCol || 'DEFAULT';
          const dateLabel = resolvedDateCol || 'auto';
          const catSuffix = categoryCol ? ', Category=' + categoryCol : '';
          res.status(201).json({
            count: cleaned.length,
            columnsDetected: mapping,
            message: `Successfully imported ${cleaned.length} records. Column mapping: SKU=${skuLabel}, Date=${dateLabel}, Value=${resolvedValueCol}${catSuffix}`
          });
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
