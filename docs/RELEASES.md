# Release Documentation

This document tracks technical implementations and features merged into production.

---

## [Release v1.4] - CI/CD Unification & Architecture Hardening
**Pipeline Consolidation**
- Consolidated redundant CI/CD workflows (`test.yml`, `deploy-k8s.yml`) into a single, unified `ci-cd.yml` pipeline.
- Enforced strict deployment gating: E2E and Backend Pytest suites must pass on `preprod` and `prod` before any Docker images are built or deployed to Kubernetes.
- Rectified relative Docker build contexts in `setup/docker-compose.yml` (`../Backend-RL`, `../Frontend`), resolving localized build failures.

**Infrastructure Stability**
- Eliminated legacy VM deployment artifacts and strictly enforced Kubernetes adoption across Preprod and Prod.
- Resolved cluster CPU starvation and `Pending` pod states by strictly capping container CPU requests (`50m`) to accommodate DigitalOcean node limitations.
- Cleansed the `dev` branch of Kubernetes-specific manifests (`k8s/`), isolating deployment infrastructure purely to deployment branches (`preprod`, `prod`).
- Re-architected root-level configuration files (Docker Compose, Alerts) into a dedicated `setup/` directory for developer hygiene.

---

## [Release v1.3] - Automated Notifications & Landing Redesign
**Automated Event Notifications**
- Engineered an automated Node.js SMTP transport pipeline via Nodemailer to deliver real-time system alerts.
- Configured dynamic login notification triggers to enhance account security awareness.
- Developed a robust webhook integration between the Python RL Worker and Express backend to securely pass training completion telemetry.
- Designed dynamic HTML email templates highlighting real-time RL metrics (Episodes, Reward Deltas, Oracle Performance %) bypassing Base64 limitations.
- Enforced strict credential security by stripping hardcoded values and offloading to localized `.env` and environment-specific GitHub Secrets injected via Docker Compose.
- Patched webhook communication pipeline to process emails asynchronously (fire-and-forget), eliminating RL worker connection timeouts.
- Migrated email infrastructure from Nodemailer SMTP to Resend HTTPS API, bypassing DigitalOcean firewall restrictions.
- Verified and configured custom domain (`replenix.app`) DNS records (DKIM, SPF, DMARC) enabling reliable email delivery to all active system users.

**Landing Interface Redesign**
- Overhauled the `/` pre-login presentation layer substituting legacy technical jargon (e.g., "DQN") with higher-level semantic copy.
- Implemented a modern dark-mode glassmorphic aesthetic architecture across the landing stage to heighten premium user impression.
- Refactored Landing Page CSS to eliminate hardcoded colors/gradients and align perfectly with the application's global Shadcn UI design system.
- Generated and integrated a dynamic SVG favicon across the client layer to maintain brand cohesion.

---

## [Release v1.2] - Latest Current Production Pipeline
**UI/UX Enhancements & Global Routing Dynamics**
- Implemented state-persisted collapsible sidebar layout utilizing centralized global React hooks for layout spacing computation (`use-sidebar`).
- Applied advanced dynamic flex-box scaling across 8 active workflow pages bridging Stage 1 to Deployment.
- Remapped global navigation pointers solving "Upload" component URL routing conflicts, fully separating the landing presentation space from operational data entry sequences.

**Authentication & Security Upgrade**
- Upgraded Drizzle DB `users` schema architecture adding `firstName` and `lastName` persistence alongside standard metrics.
- Developed the *My Profile* page interface supporting isolated authentication patching/edits securely over `/api/user`.
- Replaced basic HTML input forms with the Ethereal Utilitarian component library enforcing responsive glass-morphic elements across authentication fields.

**CI/CD Telemetry**
- Programmed end-to-end event listeners routing CI/CD action statistics (success/failures) securely to maintaining developers (Sujay, Rishit, Nishanth) using GitHub Actions SMTP relay workflows. 

---

## [Release v1.1] - Backend & DQN Stability
- Standardized reinforcement learning worker pipeline communication architecture via RabbitMQ exchanges.
- Containerized Postgres storage definitions handling automated healing overrides on password mismatch detection.

---

## [Release v1.0] - Foundation Architecture
- Base skeleton React frontend to FastAPI integration with `docker-compose`. 
- Implementation of the `REPLENIX` analytical modeling shell structure.
