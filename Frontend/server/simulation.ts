import { addDays, format } from "date-fns";

// Ported from the Python InventoryEnvironment logic
export class InventoryEnvironment {
  currentStep: number = 0;
  invOnhand: number = 100;
  lastDemand: number = 0;
  leadTime: number = 2;
  orderPipeline: number[] = [];
  maxOrderQty: number = 20;
  
  // Costs/Prices
  holdingCost: number = 2;
  stockoutPenalty: number = 100;
  orderFixedCost: number = 10;
  price: number = 100;

  startDate: Date = new Date("2025-01-01");

  constructor() {
    this.reset();
  }

  reset() {
    this.currentStep = 0;
    this.invOnhand = 100;
    this.lastDemand = 0;
    this.orderPipeline = new Array(this.leadTime).fill(0);
  }

  isFestival(dayIndex: number): boolean {
    // Mock festival logic from PDF: 
    // (15, 19), (200, 204), (250, 254), (310, 314)
    // Plus some seasonal logic
    const festivals = [
      [15, 19], [60, 64], [120, 124], [180, 184], 
      [200, 204], [220, 224], [250, 254], [300, 304], [310, 314]
    ];
    
    return festivals.some(([start, end]) => dayIndex >= start && dayIndex <= end);
  }

  getDemand(dayIndex: number): number {
    // Generate demand based on seasonality and festivals
    // Logic ported from `generate_yearly_challenging_demand`
    
    let baseDemand = 14;
    
    // Summer Season (roughly days 59 to 148)
    if (dayIndex >= 59 && dayIndex <= 148) {
      baseDemand = 40;
    } else {
      // Off season random noise
      baseDemand = 14 + Math.floor(Math.random() * 5) - 2; // 14 +/- noise
    }

    if (this.isFestival(dayIndex)) {
      baseDemand = 40; // Festival spike
    }

    // Add some random noise
    const demand = Math.max(1, Math.floor(baseDemand * (0.8 + Math.random() * 0.4)));
    return demand;
  }

  getState() {
    return {
      inventory: this.invOnhand,
      lastDemand: this.lastDemand,
      step: this.currentStep
    };
  }

  step(action: number) {
    const demand = this.getDemand(this.currentStep);
    const currentDate = addDays(this.startDate, this.currentStep);
    
    // Arrivals
    const incoming = this.orderPipeline.shift() || 0;
    this.invOnhand += incoming;

    // Sales
    const unitsSold = Math.min(demand, this.invOnhand);
    this.invOnhand -= unitsSold;
    const lostSales = demand - unitsSold;

    // Reward Calc
    const revenue = this.price * unitsSold;
    const holding = this.holdingCost * this.invOnhand;
    const stockout = this.stockoutPenalty * lostSales;
    const orderCost = action > 0 ? this.orderFixedCost : 0;
    
    const reward = revenue - holding - stockout - orderCost;

    // Add new order to pipeline
    this.orderPipeline.push(action);

    // Update state
    this.lastDemand = demand;
    const result = {
      day: this.currentStep,
      date: currentDate.toISOString(),
      demand,
      inventory: this.invOnhand,
      unitsSold,
      lostSales,
      reward,
      replenishmentArrived: incoming,
      isFestival: this.isFestival(this.currentStep)
    };

    this.currentStep++;
    return result;
  }
}
