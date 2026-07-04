import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

// Intercept fetch to automatically add CSRF token
const originalFetch = window.fetch;
let csrfPromise: Promise<string | null> | null = null;
let cachedCsrfToken: string | null = null;

async function getCsrfToken() {
  if (cachedCsrfToken) return cachedCsrfToken;
  if (!csrfPromise) {
    csrfPromise = originalFetch("/api/csrf-token", { credentials: "include" })
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        cachedCsrfToken = data?.token || null;
        return cachedCsrfToken;
      })
      .catch(() => null);
  }
  return csrfPromise;
}

window.fetch = async (input, init) => {
  const url = typeof input === "string" ? input : (input instanceof Request ? input.url : "");
  const method = init?.method || (input instanceof Request ? input.method : "GET");
  const isMutating = method.toUpperCase() !== "GET" && method.toUpperCase() !== "HEAD" && method.toUpperCase() !== "OPTIONS";
  const isApi = url.includes("/api") && !url.includes("/api/csrf-token");

  if (isMutating && isApi) {
    const token = await getCsrfToken();
    if (token) {
      if (input instanceof Request) {
        input.headers.set("x-csrf-token", token);
      } else {
        init = init || {};
        const newHeaders = new Headers(init.headers);
        newHeaders.set("x-csrf-token", token);
        init.headers = newHeaders;
      }
    }
  }
  
  const response = await originalFetch(input, init);
  
  if (url.includes("/api/logout") || response.status === 403) {
    cachedCsrfToken = null;
    csrfPromise = null;
  }
  
  return response;
};

createRoot(document.getElementById("root")!).render(<App />);
