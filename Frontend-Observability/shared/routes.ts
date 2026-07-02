import { z } from 'zod';
import { 
  insertAgentDecisionSchema, 
  insertDemandUploadSchema, 
  insertDemandModelSchema,
  insertTrainingConfigSchema,
  simulationHistory, 
  agentDecisions, 
  demandUploads,
  demandModels,
  trainingConfigs
} from './schema';

export const errorSchemas = {
  validation: z.object({
    message: z.string(),
    field: z.string().optional(),
  }),
  notFound: z.object({
    message: z.string(),
  }),
  internal: z.object({
    message: z.string(),
  }),
};

export const api = {
  simulation: {
    state: {
      method: 'GET' as const,
      path: '/api/simulation/state',
      responses: {
        200: z.object({
          currentDay: z.number(),
          inventory: z.number(),
          lastDemand: z.number(),
          isFestival: z.boolean(),
          recentHistory: z.array(z.custom<typeof simulationHistory.$inferSelect>())
        }),
      },
    },
    reset: {
      method: 'POST' as const,
      path: '/api/simulation/reset',
      responses: {
        200: z.object({ message: z.string() }),
      },
    },
    nextStep: {
      method: 'POST' as const,
      path: '/api/simulation/step',
      input: z.object({ action: z.number().optional() }).optional(), 
      responses: {
        200: z.custom<typeof simulationHistory.$inferSelect>(),
      },
    },
  },
  decisions: {
    listPending: {
      method: 'GET' as const,
      path: '/api/decisions/pending',
      responses: {
        200: z.array(z.custom<typeof agentDecisions.$inferSelect>()),
      },
    },
    review: {
      method: 'POST' as const,
      path: '/api/decisions/:id/review',
      input: z.object({
        status: z.enum(["approved", "rejected", "overridden"]),
        overrideValue: z.number().optional(),
      }),
      responses: {
        200: z.custom<typeof agentDecisions.$inferSelect>(),
        404: errorSchemas.notFound,
      },
    },
  },
  demand: {
    list: {
      method: 'GET' as const,
      path: '/api/demand',
      responses: {
        200: z.array(z.custom<typeof demandUploads.$inferSelect>()),
      },
    },
    upload: {
      method: 'POST' as const,
      path: '/api/demand/upload',
      responses: {
        201: z.object({ count: z.number() }),
        400: errorSchemas.validation,
      },
    },
    getModel: {
      method: 'GET' as const,
      path: '/api/demand/model/:sku',
      responses: {
        200: z.custom<typeof demandModels.$inferSelect>(),
        404: errorSchemas.notFound,
      },
    },
    fitModel: {
      method: 'POST' as const,
      path: '/api/demand/model/:sku/fit',
      input: insertDemandModelSchema.partial(),
      responses: {
        200: z.custom<typeof demandModels.$inferSelect>(),
      },
    },
  },
  training: {
    getConfig: {
      method: 'GET' as const,
      path: '/api/training/config',
      responses: {
        200: z.custom<typeof trainingConfigs.$inferSelect>(),
      },
    },
    updateConfig: {
      method: 'POST' as const,
      path: '/api/training/config',
      input: insertTrainingConfigSchema.partial(),
      responses: {
        200: z.custom<typeof trainingConfigs.$inferSelect>(),
      },
    },
    start: {
      method: 'POST' as const,
      path: '/api/training/start',
      responses: {
        200: z.object({ message: z.string() }),
      },
    },
  },
  stats: {
    get: {
      method: 'GET' as const,
      path: '/api/stats',
      responses: {
        200: z.object({
          totalRevenue: z.number(),
          stockoutDays: z.number(),
          averageInventory: z.number(),
          pendingDecisions: z.number(),
        }),
      },
    },
  }
};

export function buildUrl(path: string, params?: Record<string, string | number>): string {
  let url = path;
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (url.includes(`:${key}`)) {
        url = url.replace(`:${key}`, String(value));
      }
    });
  }
  return url;
}
