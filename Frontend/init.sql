-- Idempotent schema bootstrap for Docker production.
-- Run before starting the Node server. Safe to re-run (IF NOT EXISTS everywhere).

CREATE TABLE IF NOT EXISTS "users" (
  "id" serial PRIMARY KEY,
  "username" text NOT NULL UNIQUE,
  "password" text NOT NULL
);

CREATE TABLE IF NOT EXISTS "session" (
  "sid" varchar NOT NULL COLLATE "default",
  "sess" json NOT NULL,
  "expire" timestamp(6) NOT NULL,
  CONSTRAINT "session_pkey" PRIMARY KEY ("sid")
);
CREATE INDEX IF NOT EXISTS "IDX_session_expire" ON "session" ("expire");

CREATE TABLE IF NOT EXISTS "simulation_history" (
  "id" serial PRIMARY KEY,
  "day" integer NOT NULL,
  "date" timestamp NOT NULL,
  "demand" integer NOT NULL,
  "inventory_level" integer NOT NULL,
  "units_sold" integer NOT NULL,
  "lost_sales" integer NOT NULL,
  "replenishment_orders" integer DEFAULT 0,
  "reward" decimal NOT NULL,
  "is_festival" boolean DEFAULT false,
  "created_at" timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "agent_decisions" (
  "id" serial PRIMARY KEY,
  "simulation_day" integer NOT NULL,
  "proposed_action" integer NOT NULL,
  "confidence" decimal,
  "reasoning" text,
  "status" text NOT NULL DEFAULT 'pending',
  "final_action" integer,
  "reviewed_at" timestamp,
  "created_at" timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "demand_uploads" (
  "id" serial PRIMARY KEY,
  "filename" text NOT NULL,
  "filepath" text NOT NULL,
  "file_type" text NOT NULL,
  "skus" jsonb DEFAULT '[]',
  "row_count" integer DEFAULT 0,
  "created_at" timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "demand_models" (
  "id" serial PRIMARY KEY,
  "sku" text NOT NULL UNIQUE,
  "festivals" jsonb NOT NULL,
  "seasonality" text NOT NULL,
  "noise_level" decimal DEFAULT '0.1',
  "window_size" integer DEFAULT 7,
  "created_at" timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "training_configs" (
  "id" serial PRIMARY KEY,
  "stockout_penalty" decimal NOT NULL DEFAULT '100',
  "holding_cost" decimal NOT NULL DEFAULT '2',
  "learning_rate" decimal NOT NULL DEFAULT '0.001',
  "episodes" integer NOT NULL DEFAULT 100,
  "status" text NOT NULL DEFAULT 'idle',
  "learning_curve" jsonb,
  "last_trained_at" timestamp
);
