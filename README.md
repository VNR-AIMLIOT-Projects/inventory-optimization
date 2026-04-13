# Replenix - Intelligent Inventory Optimization (Development)

Welcome to the **development** repository for **Replenix**, a reinforcement learning-powered supply chain dynamics optimization engine.

**🌐 View Live Production Deployment:** [https://www.replenix.app/](https://www.replenix.app/)

## Overview
This branch (`dev`) contains the active developer workspace. It separates staging configurations, testing artifacts, and source code development files from the restrictive `prod` environments.

## Local Setup & Development Workflow

To boot the system locally using our orchestration profile:

1. Clone the repository and checkout the `dev` branch.
2. Initialize the containerized application:
   ```bash
   docker compose up --build
   ```
3. Access points:
   - Frontend: `http://localhost:3000`
   - Backend API Docs: `http://localhost:8000/docs`
   - RabbitMQ Management: `http://localhost:15672`

## Local Database Management (Drizzle)

Changes made to the backend schema locally should be pushed globally via Drizzle. If you are updating database columns:
1. Revise `./Frontend/shared/schema.ts`
2. Run database push locally.
   ```bash
   npm run db:push
   ```

## Development Pipeline & Releases
Before merging to `prod`, ensure the application tests smoothly locally. For an overview of our history, features, and fixes, check our version control logging in [RELEASES.md](./RELEASES.md).
