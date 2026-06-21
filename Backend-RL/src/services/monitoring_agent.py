"""
Automated Insights Agent
========================
Fetches key metrics from Prometheus, generates a markdown health report
via Groq LLM, and sends it via Resend email API.

Can be run as a standalone script (by the k8s CronJob) or imported
and called directly from the FastAPI trigger endpoint.

Usage:
    python -m services.monitoring_agent
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Union

import requests
import groq

logger = logging.getLogger(__name__)

# ── Thresholds for anomaly highlighting ───────────────────────────────────────
THRESHOLDS = {
    "cpu_pct":        {"yellow": 60,  "red": 80},
    "ram_pct":        {"yellow": 70,  "red": 85},
    "queue_depth":    {"yellow": 20,  "red": 100},
    "failure_rate":   {"yellow": 5,   "red": 10},   # percentage
    "rl_vs_oracle":   {"yellow": 85,  "red": 70},   # lower is worse
    "p99_latency_ms": {"yellow": 500, "red": 2000},
}

# ── Prometheus queries ────────────────────────────────────────────────────────
_PROM_QUERIES = {
    "cpu_pct": '100 - avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100',
    "ram_pct": '(1 - avg(node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100',
    "queue_depth": 'rabbitmq_queue_messages_ready{queue="rl_jobs"}',
    "rl_jobs_success": 'rl_jobs_processed_total{status="success"}',
    "rl_jobs_failure": 'rl_jobs_processed_total{status="failure"}',
    "rl_jobs_in_flight": "rl_jobs_in_flight",
    "rl_best_reward": "rl_best_reward",
    "rl_vs_oracle_pct": "rl_vs_oracle_pct",
    "p99_latency_ms": 'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) * 1000',
}

_SYSTEM_PROMPT = """You are a concise infrastructure health analyst for the Replenix inventory optimization system.
You will receive a JSON snapshot of real-time Prometheus metrics.

Your task:
1. Output an overall health score: 🟢 Green, 🟡 Yellow, or 🔴 Red at the very top.
2. Write a brief executive summary (2-3 sentences max).
3. List ONLY anomalies or metrics that are out of bounds — skip metrics that are healthy.
4. End with a "Recommended Actions" section (bullet points, only if there are issues).

Thresholds:
- CPU: Green <60%, Yellow 60-80%, Red >80%
- RAM: Green <70%, Yellow 70-85%, Red >85%
- RabbitMQ queue: Green <20, Yellow 20-100, Red >100 messages
- RL job failure rate: Green <5%, Yellow 5-10%, Red >10%
- RL vs Oracle: Green >85%, Yellow 70-85%, Red <70%
- API p99 latency: Green <500ms, Yellow 500ms-2s, Red >2s

Format output as clean markdown. Be concise — max 300 words total. No filler text."""


def _prom_query(prometheus_url: str, query: str) -> list:
    """Execute a single instant Prometheus query. Returns list of result dicts."""
    try:
        resp = requests.get(
            f"{prometheus_url}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("result", [])
    except Exception as e:
        logger.warning(f"[InsightsAgent] Prometheus query failed ({query[:50]}...): {e}")
        return []


def _extract_scalar(results: list, label_key: Optional[str] = None) -> Optional[Union[dict, float]]:
    """
    Extract value(s) from Prometheus result list.
    If label_key given, returns {label_value: float}.
    Otherwise returns a single float or None.
    """
    if not results:
        return None
    if label_key:
        return {
            r["metric"].get(label_key, "unknown"): float(r["value"][1])
            for r in results
            if "value" in r
        }
    # Single scalar
    try:
        return float(results[0]["value"][1])
    except (IndexError, KeyError, ValueError):
        return None


def fetch_prometheus_metrics(prometheus_url: str) -> dict:
    """
    Pull a compact snapshot of key metrics from Prometheus.
    Returns a dict ready to be serialised into the LLM prompt.
    """
    raw = {k: _prom_query(prometheus_url, q) for k, q in _PROM_QUERIES.items()}

    success = _extract_scalar(raw["rl_jobs_success"]) or 0.0
    failure = _extract_scalar(raw["rl_jobs_failure"]) or 0.0
    total = success + failure
    failure_rate_pct = round((failure / total * 100), 1) if total > 0 else 0.0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_pct": round(_extract_scalar(raw["cpu_pct"]) or 0.0, 1),
        "ram_pct": round(_extract_scalar(raw["ram_pct"]) or 0.0, 1),
        "queue_depth": _extract_scalar(raw["queue_depth"]) or 0,
        "rl_jobs_in_flight": _extract_scalar(raw["rl_jobs_in_flight"]) or 0,
        "rl_jobs_success_total": int(success),
        "rl_jobs_failure_total": int(failure),
        "rl_failure_rate_pct": failure_rate_pct,
        "rl_best_reward_by_sku": _extract_scalar(raw["rl_best_reward"], label_key="sku") or {},
        "rl_vs_oracle_pct_by_sku": _extract_scalar(raw["rl_vs_oracle_pct"], label_key="sku") or {},
        "api_p99_latency_ms": round(_extract_scalar(raw["p99_latency_ms"]) or 0.0, 1),
        "thresholds": THRESHOLDS,
    }


def generate_health_report(metrics: dict, groq_api_key: str) -> str:
    """
    Send metric snapshot to Groq → get back a markdown health report.
    Returns raw markdown string.
    """
    # Compact payload — drop thresholds dict (LLM has them in system prompt)
    payload = {k: v for k, v in metrics.items() if k != "thresholds"}
    metrics_json = json.dumps(payload, indent=2)

    client = groq.Groq(api_key=groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Metrics snapshot:\n```json\n{metrics_json}\n```"},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


def _md_to_html(md: str) -> str:
    """
    Convert markdown to HTML. Uses `markdown` lib if available,
    otherwise falls back to minimal regex-based conversion.
    """
    try:
        import markdown as md_lib  # type: ignore
        return md_lib.markdown(md, extensions=["nl2br"])
    except ImportError:
        pass

    # Minimal fallback
    import re
    html = md
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$",  r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$",   r"<h1>\1</h1>", html, flags=re.MULTILINE)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"^- (.+)$",   r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", html, flags=re.DOTALL)
    html = html.replace("\n\n", "<br><br>").replace("\n", "<br>")
    return html


def send_email_report(
    report_md: str,
    resend_api_key: str,
    to_emails: list[str],
    from_address: str,
) -> None:
    """
    Send the health report via Resend REST API.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Pick subject emoji based on first emoji in report
    if "🔴" in report_md:
        emoji = "🔴"
    elif "🟡" in report_md:
        emoji = "🟡"
    else:
        emoji = "🟢"

    subject = f"{emoji} Replenix Health Report — {now}"
    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 700px; margin: auto; padding: 24px;">
      <h2 style="border-bottom: 2px solid #eee; padding-bottom: 8px;">
        Replenix Automated Health Report
      </h2>
      <p style="color: #666; font-size: 12px;">Generated: {now} (IST+5:30)</p>
      <div style="background: #f9f9f9; border-radius: 8px; padding: 16px; margin-top: 16px;">
        {_md_to_html(report_md)}
      </div>
      <p style="color: #aaa; font-size: 11px; margin-top: 24px;">
        This is an automated report from the Replenix Insights Agent.
        Metrics sourced from Prometheus.
      </p>
    </body></html>
    """

    payload = {
        "from": from_address,
        "to": to_emails,
        "subject": subject,
        "html": html_body,
    }

    resp = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    logger.info(f"[InsightsAgent] Email sent. Resend ID: {resp.json().get('id')}")


def run_insights_pipeline() -> str:
    """
    Full pipeline: fetch → generate → send.
    Returns the generated markdown report for logging / API response.
    Reads config from environment variables.
    """
    prometheus_url = os.environ.get(
        "PROMETHEUS_URL",
        "http://replenix-prometheus-kube-p-prometheus.monitoring.svc.cluster.local:9090",
    )
    groq_api_key   = os.environ["GROQ_API_KEY"]
    resend_api_key = os.environ["RESEND_API_KEY"]
    from_address   = os.environ.get("RESEND_FROM", "Replenix System <noreply@replenix.app>")
    to_raw         = os.environ.get("REPORT_EMAIL_TO", "sujaynsv@gmail.com,rishitsura@gmail.com")
    to_emails      = [e.strip() for e in to_raw.split(",") if e.strip()]

    logger.info(f"[InsightsAgent] Fetching metrics from {prometheus_url}")
    metrics = fetch_prometheus_metrics(prometheus_url)

    logger.info("[InsightsAgent] Generating LLM health report...")
    report_md = generate_health_report(metrics, groq_api_key)

    logger.info(f"[InsightsAgent] Sending email to {to_emails}")
    send_email_report(report_md, resend_api_key, to_emails, from_address)

    return report_md


# ── Standalone entrypoint (used by CronJob) ───────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = run_insights_pipeline()
    print("\n" + "=" * 60)
    print("GENERATED REPORT:")
    print("=" * 60)
    print(report)
