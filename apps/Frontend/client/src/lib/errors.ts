/**
 * Centralized error classifier for user-facing messages.
 *
 * Maps raw backend error strings (FastAPI detail messages, Python exceptions,
 * network errors) to clear, actionable messages that make sense to end users.
 *
 * Usage:
 *   toast({ title: "Upload Failed", description: friendlyError(err), variant: "destructive" })
 */

type ErrorContext =
  | "upload"
  | "generate"
  | "training"
  | "evaluation"
  | "deployment"
  | "params"
  | "sku"
  | "chatbot"
  | "general";

interface ErrorRule {
  /** Substring or regex to match against the raw error message (case-insensitive) */
  match: string | RegExp;
  /** Human-readable message to show the user */
  message: string;
  /** Optional: only apply this rule for certain contexts */
  contexts?: ErrorContext[];
}

const ERROR_RULES: ErrorRule[] = [
  // ─── File / Upload errors ─────────────────────────────────────────────────
  {
    match: /unsupported file type|\.csv|\.xlsx|\.xls|invalid file/i,
    message:
      "Only CSV (.csv) and Excel (.xlsx, .xls) files are supported. Please convert your file before uploading.",
    contexts: ["upload"],
  },
  {
    match: /required columns|missing column|column not found|date.*column|sku.*column|demand.*column/i,
    message:
      'Your file is missing required columns. Download the template and ensure your file has "Date", "SKU", and "Demand" columns.',
    contexts: ["upload"],
  },
  {
    match: /at least \d+ day|365 day|minimum.*day|not enough.*day|too few day/i,
    message:
      "Your file needs at least 1 year (365 days) of data. Please upload a longer dataset, or use 'Generate Synthetic Data' to create sample data.",
    contexts: ["upload"],
  },
  {
    match: /empty file|no data|empty dataframe|zero row/i,
    message:
      "The uploaded file appears to be empty or contains no valid rows. Please check the file contents and try again.",
    contexts: ["upload"],
  },
  {
    match: /parse.*error|invalid date|date format|cannot parse/i,
    message:
      "Could not parse dates in your file. Dates must be in YYYY-MM-DD format (e.g. 2025-06-15).",
    contexts: ["upload"],
  },
  {
    match: /file too large|size limit|max.*mb/i,
    message:
      "The file is too large. Please reduce the file size or split it into smaller uploads.",
    contexts: ["upload"],
  },
  {
    match: /sku.*not found|no sku|unknown sku/i,
    message:
      "The selected SKU was not found in this file. Please re-upload the file and select a valid SKU.",
    contexts: ["upload", "sku"],
  },
  {
    match: /duplicate.*sku|sku.*duplicate/i,
    message:
      "Duplicate SKU entries were detected in the file. Ensure each SKU-Date combination is unique.",
    contexts: ["upload"],
  },

  // ─── No data loaded ───────────────────────────────────────────────────────
  {
    match: /no demand data|no file.*uploaded|upload.*first|no data.*loaded|demand.*not.*load/i,
    message:
      "No demand data is loaded. Go back to Step 1 and upload or generate demand data first.",
  },
  {
    match: /no (current|active) sku|sku.*not.*selected/i,
    message:
      "No SKU is currently selected. Go back to Step 1 and select a SKU from your uploaded file.",
  },

  // ─── Training errors ──────────────────────────────────────────────────────
  {
    match: /already running|training.*in progress|another.*training/i,
    message:
      "A training run is already in progress. Stop the current run before starting a new one.",
    contexts: ["training"],
  },
  {
    match: /no.*model.*train|model.*not.*found|no.*trained.*model/i,
    message:
      "No trained model is available. Complete training in Step 2 first before evaluating.",
    contexts: ["evaluation", "deployment"],
  },
  {
    match: /no.*model.*load|model.*not.*loaded/i,
    message:
      "No model is loaded. Select a training run from the history panel and load it.",
    contexts: ["evaluation", "deployment"],
  },
  {
    match: /cancelled|canceled|training.*stop/i,
    message:
      "This training run was cancelled. Start a new run to continue training.",
    contexts: ["training"],
  },
  {
    match: /episode.*invalid|episodes.*must|invalid.*episode/i,
    message:
      "Invalid number of episodes. Please enter a value between 1 and 5,000.",
    contexts: ["training"],
  },
  {
    match: /out of memory|cuda.*memory|memory.*error/i,
    message:
      "The system ran out of memory during training. Try reducing the number of episodes or restarting the backend.",
    contexts: ["training"],
  },

  // ─── Deployment / Simulation errors ──────────────────────────────────────
  {
    match: /no.*session|session.*not.*found|invalid.*session/i,
    message:
      "No active simulation session found. Please start a new deployment session.",
    contexts: ["deployment"],
  },
  {
    match: /simulation.*complete|already.*complete|day.*exceed/i,
    message:
      "The simulation has already completed all days. Reset it to start over.",
    contexts: ["deployment"],
  },
  {
    match: /override.*past.*day|cannot.*override.*past/i,
    message:
      "You cannot override a day that has already been simulated. Override future days only.",
    contexts: ["deployment"],
  },
  {
    match: /no.*completed.*run|no.*run.*available|no.*training.*run/i,
    message:
      "No completed training run is available. Train a model in Step 2 first, then come back to deploy.",
    contexts: ["deployment"],
  },

  // ─── Parameters errors ────────────────────────────────────────────────────
  {
    match: /no.*param|param.*not.*found|detected.*param.*miss/i,
    message:
      "No demand parameters found. Upload or generate demand data first, then return to this page.",
    contexts: ["params"],
  },
  {
    match: /invalid.*param|param.*invalid|value.*out.*of.*range/i,
    message:
      "One or more parameter values are invalid. Please check that all values are positive numbers within a reasonable range.",
    contexts: ["params"],
  },

  // ─── AI Chatbot errors ────────────────────────────────────────────────────
  {
    match: /gemini_api_key|api.*key.*not|not.*configured/i,
    message:
      "The AI assistant is not configured. Please contact the administrator to set up the Gemini API key.",
    contexts: ["chatbot"],
  },
  {
    match: /quota.*exceeded|rate.*limit|429/i,
    message:
      "The AI service is temporarily busy. Please wait a moment and try again.",
    contexts: ["chatbot"],
  },

  // ─── Network errors ───────────────────────────────────────────────────────
  {
    match: /failed to fetch|networkerror|network.*error|econnrefused|err_connection/i,
    message:
      "Cannot reach the server. Please check your connection and ensure the backend is running.",
  },
  {
    match: /timeout|timed out|request.*timeout/i,
    message:
      "The request timed out. The server may be busy — please try again in a moment.",
  },
  {
    match: /500|internal server error/i,
    message:
      "The server encountered an unexpected error. Please try again. If the issue persists, restart the backend.",
  },
  {
    match: /503|service unavailable/i,
    message:
      "The server is temporarily unavailable. Please wait a moment and try again.",
  },
  {
    match: /401|unauthorized|not authenticated/i,
    message:
      "Your session has expired. Please log in again.",
  },
  {
    match: /403|forbidden|permission denied/i,
    message:
      "You do not have permission to perform this action.",
  },
  {
    match: /404|not found/i,
    message:
      "The requested resource was not found. It may have been deleted or not yet created.",
  },
];

/**
 * Convert a raw error (from a catch block or API response) to a user-friendly string.
 *
 * @param err   - The caught error (Error, string, or unknown)
 * @param context - Optional context hint to narrow which rules apply
 * @returns     A human-friendly error message string
 */
export function friendlyError(err: unknown, context?: ErrorContext): string {
  const raw = extractRawMessage(err);

  for (const rule of ERROR_RULES) {
    // Context filter: if rule has contexts and a context is provided, check match
    if (rule.contexts && context && !rule.contexts.includes(context)) {
      continue;
    }

    const matched =
      typeof rule.match === "string"
        ? raw.toLowerCase().includes(rule.match.toLowerCase())
        : rule.match.test(raw);

    if (matched) {
      return rule.message;
    }
  }

  // Fallback: show the raw message if it's short and seems safe, otherwise generic
  if (raw && raw.length < 120 && !raw.includes("Traceback") && !raw.includes("File ")) {
    return raw;
  }

  return "Something went wrong. Please try again. If the issue persists, refresh the page.";
}

/** Extract a string message from various error shapes */
function extractRawMessage(err: unknown): string {
  if (!err) return "";
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message;
  if (typeof err === "object") {
    const e = err as Record<string, unknown>;
    return String(e.message || e.detail || e.error || JSON.stringify(err));
  }
  return String(err);
}
