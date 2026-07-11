# Technical Specification: Observability Enhancements

## 1. Architecture Overview
The Observability dashboard is a React (Vite) single-page application served by an Express backend. The backend acts as a proxy to Kubernetes APIs and the main Replenix API backend (`api_rl`). 
We will introduce three new React components under `apps/Frontend-Observability/client/src/pages/`:
- `LogsDashboard.tsx`
- `AlertsDashboard.tsx`
- `TracesDashboard.tsx`

The sidebar navigation component (`App.tsx`) will be updated to include links to these new pages.

## 2. API & Data Models

### 2.1 Logs
- **Frontend Component**: `LogsDashboard.tsx`
- **Existing API**: `GET /api/k8s/logs?env=<namespace>&pod=<pod_name>`
- **Logic**: 
  - Call `/api/k8s/pods?env=<namespace>` to populate a pod dropdown.
  - Call `/api/k8s/logs` when a pod is selected.
  - Implement a simple auto-refresh interval (e.g., every 5 seconds) or a manual "Refresh" button.
  - Provide a client-side search input to filter lines.

### 2.2 Alerts
- **Frontend Component**: `AlertsDashboard.tsx`
- **New API Mock**: `GET /api/metrics/alerts`
  - *Location*: Added to `apps/Frontend-Observability/server/routes.ts`
  - *Response Format*:
    ```json
    [
      { "id": "1", "name": "CPU Throttling", "severity": "warning", "status": "firing", "labels": {"pod": "backend-xyz"} },
      { "id": "2", "name": "OOMKilled", "severity": "critical", "status": "resolved", "labels": {"pod": "rl-worker-abc"} }
    ]
    ```
- **Logic**: Render a modern table or card layout. Use Shadcn UI badges for severity (Red for Critical, Yellow for Warning).

### 2.3 Traces
- **Frontend Component**: `TracesDashboard.tsx`
- **Existing API**: The RL backend exposes `/observability/traces` directly. The frontend proxy already forwards `/api_rl/` traffic to the backend.
- **Proxied Endpoint**: `GET /api_rl/observability/traces?hours=24`
- **Logic**:
  - The API returns an array of span/trace objects (we will infer the schema by interacting with it, or assume a flat list of spans).
  - Group spans by `trace_id` if necessary.
  - Display a summary table of traces.
  - Allow expanding a row to see the raw JSON or a timeline of the trace's internal spans.

## 3. Deployment Strategy
- **Branch**: `feature/observability-enhancements`
- **Process**:
  1. Implement the mock Alerts API in `server/routes.ts`.
  2. Build the UI components using Lucide icons, Shadcn UI cards, and standard React patterns.
  3. Wire the UIs to their respective backend proxy endpoints.
  4. Ensure `App.tsx` routes properly.
  5. Commit and push to `feature/observability-enhancements`.
  6. Wait for CI checks, then merge to `preprod` and `prod`.

## 4. UI/UX Considerations
- Use the existing dark-mode layout pattern established in `KubernetesDashboard.tsx` and `MetricsDashboard.tsx`.
- For logs, use a monospaced font with a dark background to simulate a terminal (`bg-zinc-950 text-green-400 font-mono p-4 rounded-md overflow-y-auto`).
