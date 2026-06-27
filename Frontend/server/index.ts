import "dotenv/config";
import express, { type Request, Response, NextFunction } from "express";
import { registerRoutes } from "./routes";
import { setupAuth, apiLimiter, csrfSynchronisedProtection } from "./auth";
import { serveStatic } from "./static";
import { createServer } from "http";
import { createProxyMiddleware } from "http-proxy-middleware";
import { registerWebhookRoutes } from "./webhook_routes";
import { setupNotifications } from "./notifications";
import { Server as SocketIOServer } from "socket.io";
import rateLimit from "express-rate-limit";
import { collectDefaultMetrics, Registry, Counter, Gauge, Histogram } from 'prom-client';

// ── Prometheus metrics registry ─────────────────────────────────────────────
const metricsRegistry = new Registry();
collectDefaultMetrics({ register: metricsRegistry }); // Node.js process metrics

export const httpRequestDuration = new Histogram({
  name: 'http_request_duration_seconds',
  help: 'Express HTTP request latency',
  labelNames: ['method', 'route', 'status_code'],
  buckets: [0.05, 0.1, 0.3, 0.5, 1, 2, 5],
  registers: [metricsRegistry],
});

export const wsConnectionsActive = new Gauge({
  name: 'websocket_connections_active',
  help: 'Number of active Socket.io connections (live training streams)',
  registers: [metricsRegistry],
});

export const emailNotificationsSent = new Counter({
  name: 'email_notifications_sent_total',
  help: 'Total emails dispatched via Resend',
  labelNames: ['type'], // training_complete | login | export
  registers: [metricsRegistry],
});

export const trainingJobsSubmitted = new Counter({
  name: 'training_jobs_submitted_total',
  help: 'Total DQN training jobs submitted to RabbitMQ',
  registers: [metricsRegistry],
});

const app = express();

// ── /metrics — Prometheus scrape endpoint (no auth, no CSRF) ─────────────────
// Must be registered BEFORE any auth/rate-limit middleware.
app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', metricsRegistry.contentType);
  res.end(await metricsRegistry.metrics());
});

// Initialize UI Notifications RabbitMQ Relay
setupNotifications();

const globalLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 2000,
  standardHeaders: true,
  legacyHeaders: false,
  validate: { trustProxy: false },
});
app.use(globalLimiter);

const httpServer = createServer(app);

// Initialize Socket.io instance
export const io = new SocketIOServer(httpServer, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

io.on("connection", (socket) => {
  wsConnectionsActive.inc();
  console.log(`🔌 Client connected to Socket.io: ${socket.id}`);
  socket.on("disconnect", () => {
    wsConnectionsActive.dec();
    console.log(`🔌 Client disconnected: ${socket.id}`);
  });
});

declare module "http" {
  interface IncomingMessage {
    rawBody: unknown;
  }
}

// Intercept Python RL API traffic BEFORE body parsers!
// This solves Mixed Content / CORS in production without needing NGINX.
const rawBackendUrl = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";
let backendUrl: string;
try {
  const parsedUrl = new URL(rawBackendUrl);
  if (!["http:", "https:"].includes(parsedUrl.protocol)) {
    throw new Error("Invalid protocol");
  }
  backendUrl = rawBackendUrl;
} catch {
  console.warn("[Security] Invalid BACKEND_INTERNAL_URL, using default");
  backendUrl = "http://backend:8000";
}

const rlProxy = createProxyMiddleware({
  target: backendUrl,
  changeOrigin: true,
  // We do NOT use global ws: true here because it intercepts Socket.io
  // We will manually pass upgrade requests below.
  pathRewrite: {
    "^/api_rl/api": "/api", // Rewrite /api_rl/api to /api for HTTP requests
    "^/api_rl": "/api",     // Fallback
    "^/ws_rl/ws": "/ws",    // Rewrite /ws_rl/ws to /ws for WebSockets
  },
  headers: {
    "X-API-Key": process.env.API_KEY || "replenix-secret-key"
  }
});

app.use("/api", apiLimiter);

const addApiKey = (req: any, res: any, next: any) => {
  req.headers["x-api-key"] = process.env.API_KEY || "replenix-secret-key";
  next();
};

app.use("/api_rl", addApiKey, rlProxy);
app.use("/ws_rl", addApiKey, rlProxy);

app.use(
  express.json({
    verify: (req, _res, buf) => {
      req.rawBody = buf;
    },
  }),
);

app.use(express.urlencoded({ extended: false }));

export function log(message: string, source = "express") {
  const formattedTime = new Date().toLocaleTimeString("en-US", {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });

  console.log(`${formattedTime} [${source}] ${message}`);
}

app.use((req, res, next) => {
  const start = Date.now();
  const path = req.path;
  let capturedJsonResponse: Record<string, any> | undefined = undefined;

  const originalResJson = res.json;
  res.json = function (bodyJson, ...args) {
    capturedJsonResponse = bodyJson;
    return originalResJson.apply(res, [bodyJson, ...args]);
  };

  res.on("finish", () => {
    const duration = Date.now() - start;
    if (path.startsWith("/api")) {
      let logLine = `${req.method} ${path} ${res.statusCode} in ${duration}ms`;
      if (capturedJsonResponse) {
        logLine += ` :: ${JSON.stringify(capturedJsonResponse)}`;
      }

      log(logLine);
    }
  });

  next();
});

(async () => {
  // Register ERP Webhooks before auth so they don't require CSRF/session
  registerWebhookRoutes(app);

  // Setup auth first (creates session table in Postgres if needed)
  await setupAuth(app);
  
  await registerRoutes(httpServer, app);

  app.use((err: any, _req: Request, res: Response, next: NextFunction) => {
    const status = err.status || err.statusCode || 500;
    const message = err.message || "Internal Server Error";

    console.error("Internal Server Error:", err);

    if (res.headersSent) {
      return next(err);
    }

    return res.status(status).json({ message });
  });

  // importantly only setup vite in development and after
  // setting up all the other routes so the catch-all route
  // doesn't interfere with the other routes
  if (process.env.NODE_ENV === "production") {
    serveStatic(app);
  } else {
    const { setupVite } = await import("./vite");
    await setupVite(httpServer, app);
  }

  // ALWAYS serve the app on the port specified in the environment variable PORT
  // Other ports are firewalled. Default to 5000 if not specified.
  // this serves both the API and the client.
  // It is the only port that is not firewalled.
  const port = parseInt(process.env.PORT || "5000", 10);
  
  // Explicitly proxy WebSockets for the Python RL backend
  httpServer.on("upgrade", (req, socket, head) => {
    if (req.url && req.url.startsWith("/ws_rl")) {
      rlProxy.upgrade(req as any, socket as any, head);
    }
  });

  httpServer.listen(
    {
      port,
      host: "0.0.0.0",
    },
    () => {
      log(`serving on port ${port}`);
    },
  );
})();
