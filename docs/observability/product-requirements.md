# Product Requirements Document (PRD): Observability Enhancements

## 1. What are we building?
We are extending the existing Frontend-Observability application for the Replenix platform to include three new core features:
1. **Real-Time Logs Viewer**: A dedicated dashboard for fetching, streaming, and filtering raw pod logs from Kubernetes.
2. **Alerts & Alarms Dashboard**: A dashboard to monitor system health deviations, displaying active alerts, historical alarms, and their statuses.
3. **Trace Visualizations**: A UI to query, list, and visualize distributed traces from the backend API, allowing engineers to drill down into bottlenecks.

## 2. Why are we building it?
Currently, the observability dashboard provides high-level metrics and basic Kubernetes pod states. However, when an issue occurs (e.g., a 500 error or a pod crash), engineers lack the tools within the dashboard to diagnose the root cause. By adding Logs, Alerts, and Traces directly into the Observability UI, we reduce the mean time to resolution (MTTR) and remove the need to context-switch to raw `kubectl` commands or external tools.

## 3. User Personas
- **DevOps/SRE Engineers**: Need to see alerts and view pod logs immediately when a deployment fails or performance degrades.
- **Backend Engineers**: Need to inspect trace details for slow endpoints or failed ML model training runs.

## 4. Key Features & Requirements

### 4.1 Real-Time Logs Viewer
- **Pod Selection**: Users can select an environment (`preprod` or `prod`) and a specific pod from a dropdown.
- **Log Display**: A terminal-like display that shows the recent logs of the selected pod.
- **Controls**: Ability to refresh logs, wrap text, and filter by keywords (e.g., "error", "exception").

### 4.2 Alerts & Alarms Dashboard
- **Active Alerts**: Display a list of currently firing alerts (e.g., High CPU, Out of Memory, High Error Rate).
- **Severity Indicators**: Visual color-coding based on severity (Critical, Warning, Info).
- **Mock Integration**: Initially mock the alert data, building the UI foundation for a future integration with Prometheus AlertManager.

### 4.3 Trace Visualizations
- **Trace Search**: A search interface to fetch recent traces by time range (e.g., last 24 hours).
- **Trace List**: A table showing Trace ID, Root Span Name, Duration, and Status (Success/Error).
- **Span Detail View**: Clicking a trace displays its spans in a waterfall or detailed timeline view, showcasing where time was spent (e.g., DB queries vs. HTTP requests).

## 5. Non-Goals
- We are not deploying a full Jaeger/Zipkin backend in this phase. We will rely on the custom traces endpoint already provided by the Replenix backend (`/observability/traces`).
- We are not implementing WebSocket-based log streaming yet; we will rely on a polling or manual refresh mechanism via the `/api/k8s/logs` endpoint.
