# Replenix — Intelligent Inventory Automated

A full-stack web application for **RL-based inventory optimization** with a human-in-the-loop approval workflow. Built with React, Express, and PostgreSQL.

---

## Features

| Stage | Page | Description |
|-------|------|-------------|
| **Stage 1** | `/` | Upload demand data (CSV), fit demand models per SKU |
| **Stage 2** | `/training` | Configure RL agent hyperparameters, run training, view learning curves |
| **Stage 3** | `/operations` | Live operations dashboard with human-in-the-loop agent decision approval |

- **Demand Simulator** — generates synthetic demand with festivals & seasonality
- **Agent Decision Queue** — agent proposes replenishment orders, human approves/rejects/overrides
- **Live Metrics** — cumulative profit, inventory levels, stockout tracking, fulfillment rate
- **CSV Upload** — bulk import historical demand data with validation

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, TailwindCSS, Radix UI, Recharts, Framer Motion |
| Backend | Express.js (TypeScript), `tsx` runner |
| Database | PostgreSQL via Drizzle ORM |
| Routing | Wouter (client), Express (server) |
| State | TanStack React Query |

---

## Prerequisites

- **Node.js** v20+ ([download](https://nodejs.org/))
- **PostgreSQL** database (local or cloud)
  - Recommended: [Supabase](https://supabase.com) (free tier)

---

## Getting Started

### 1. Clone the repository

```bash
git clone -b replenix-ui https://github.com/VNR-AIMLIOT-Projects/inventory-optimization.git
cd inventory-optimization
```

### 2. Install dependencies

```bash
npm install
```

### 3. Set up environment variables

Create a `.env` file in the project root:

```env
DATABASE_URL=postgresql://username:password@host:5432/database_name
```

> Replace with your actual PostgreSQL/Supabase connection string.

### 4. Push the database schema

```bash
npx drizzle-kit push
```

> This creates all the required tables in your database.

### 5. Run the app

```bash
npm run dev
```

The app will be available at **http://localhost:5000**.

---

## Project Structure

```
├── client/                  # React frontend
│   ├── src/
│   │   ├── components/      # Reusable UI components (Sidebar, Cards, etc.)
│   │   ├── hooks/           # React Query hooks for API calls
│   │   ├── pages/           # Page components (Stage1, Stage2, Stage3)
│   │   └── lib/             # Utilities
│   └── index.html
├── server/                  # Express backend
│   ├── index.ts             # Server entry point
│   ├── routes.ts            # API route handlers
│   ├── storage.ts           # Database access layer (Drizzle ORM)
│   ├── simulation.ts        # Inventory environment simulator
│   └── db.ts                # Database connection
├── shared/                  # Shared between client & server
│   ├── schema.ts            # Drizzle table definitions & types
│   └── routes.ts            # API route contracts
├── .env                     # Environment variables (not committed)
├── drizzle.config.ts        # Drizzle ORM config
└── package.json
```

---


## License

MIT
