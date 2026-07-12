"""
Automated Insights Agent — Replenix
=====================================
Fetches real metrics from Prometheus, builds a structured HTML report with
per-pod/container tables, and sends via Resend. Uses exact metric names and
label sets confirmed against the live cluster.

Usage:
    python -m services.monitoring_agent
    PROMETHEUS_URL=http://localhost:9090 python -m services.monitoring_agent
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Union, Dict, List, Any

import requests
import groq

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

NAMESPACE = os.environ.get("NAMESPACE", "replenix-prod")

# ── Prometheus helpers ────────────────────────────────────────────────────────

def _query(base_url: str, promql: str, timeout: int = 12) -> List[dict]:
    """Run a Prometheus instant query. Returns result list or [] on failure."""
    try:
        r = requests.get(
            f"{base_url}/api/v1/query",
            params={"query": promql},
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json().get("data", {}).get("result", [])
    except Exception as e:
        logger.warning(f"[InsightsAgent] Query failed ({promql[:70]}): {e}")
        return []


def _scalar(results: List[dict]) -> float:
    try:
        return round(float(results[0]["value"][1]), 2)
    except (IndexError, KeyError, ValueError):
        return 0.0


def _series(results: List[dict], *label_keys: str) -> List[dict]:
    """Convert Prometheus results into [{label_key: val, ..., 'value': float}]."""
    out = []
    for r in results:
        entry = {k: r["metric"].get(k, "—") for k in label_keys}
        try:
            entry["value"] = round(float(r["value"][1]), 2)
        except (KeyError, ValueError):
            entry["value"] = 0.0
        out.append(entry)
    return sorted(out, key=lambda x: x.get(label_keys[0], "") if label_keys else "")


# ── Metric collection ─────────────────────────────────────────────────────────

def fetch_all_metrics(prometheus_url: str) -> Dict[str, Any]:
    """
    Pull a comprehensive snapshot using exact metric names confirmed against
    the live cluster. All failures return 0 / empty list gracefully.
    """
    q = lambda promql: _query(prometheus_url, promql)  # noqa: E731

    # ── 1. Node-level ────────────────────────────────────────────────────────
    node_cpu = _series(
        q('100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'),
        "instance",
    )
    node_ram_used = _series(
        q('(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1073741824'),
        "instance",
    )
    node_ram_total = _series(
        q('node_memory_MemTotal_bytes / 1073741824'),
        "instance",
    )
    # Confirmed working: mountpoint="/" gives correct disk usage
    node_disk = _series(
        q('100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)'),
        "instance",
    )

    # ── 2. Pod status (== 1 filters to pods actually IN that phase) ──────────
    # kube_pod_status_phase returns 1 for the current phase, 0 for others
    pod_running = _series(
        q(f'kube_pod_status_phase{{namespace="{NAMESPACE}",phase="Running"}} == 1'),
        "pod",
    )
    pod_failed = _series(
        q(f'kube_pod_status_phase{{namespace="{NAMESPACE}",phase="Failed"}} == 1'),
        "pod",
    )
    pod_pending = _series(
        q(f'kube_pod_status_phase{{namespace="{NAMESPACE}",phase="Pending"}} == 1'),
        "pod",
    )
    # Pod restarts — all containers, filter non-zero in display
    pod_restarts = _series(
        q(f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}"}}'),
        "pod", "container",
    )

    # ── 3. Deployments ───────────────────────────────────────────────────────
    deploy_desired   = _series(q(f'kube_deployment_spec_replicas{{namespace="{NAMESPACE}"}}'), "deployment")
    deploy_available = _series(q(f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}"}}'), "deployment")
    deploy_unav      = _series(q(f'kube_deployment_status_replicas_unavailable{{namespace="{NAMESPACE}"}}'), "deployment")

    # ── 4. Container resources ────────────────────────────────────────────────
    # Confirmed working: these exact selectors return data for replenix-prod
    container_cpu = _series(
        q(f'rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}",container!="",container!="POD"}}[5m]) * 100'),
        "pod", "container",
    )
    container_ram = _series(
        q(f'container_memory_working_set_bytes{{namespace="{NAMESPACE}",container!="",container!="POD"}} / 1048576'),
        "pod", "container",
    )
    container_ram_limit = _series(
        q(f'kube_pod_container_resource_limits{{namespace="{NAMESPACE}",resource="memory",unit="byte"}} / 1048576'),
        "pod", "container",
    )

    # ── 5. RabbitMQ — confirmed metric names from label discovery ─────────────
    # rabbitmq_connections, rabbitmq_channels, rabbitmq_consumers are global metrics
    # rabbitmq_queue_messages_ready is per-queue (no 'queue' label — it's a gauge)
    rmq_connections   = _scalar(q(f'sum(rabbitmq_connections{{namespace="{NAMESPACE}"}})'))
    rmq_channels      = _scalar(q(f'sum(rabbitmq_channels{{namespace="{NAMESPACE}"}})'))
    rmq_consumers     = _scalar(q(f'sum(rabbitmq_consumers{{namespace="{NAMESPACE}"}})'))
    rmq_queue_ready   = _scalar(q(f'sum(rabbitmq_queue_messages_ready{{namespace="{NAMESPACE}"}})'))
    rmq_queue_unacked = _scalar(q(f'sum(rabbitmq_channel_messages_unacked{{namespace="{NAMESPACE}"}})'))
    rmq_publish_rate  = _scalar(q(f'sum(rate(rabbitmq_channel_messages_published_total{{namespace="{NAMESPACE}"}}[5m]))'))
    rmq_deliver_rate  = _scalar(q(f'sum(rate(rabbitmq_channel_messages_delivered_ack_total{{namespace="{NAMESPACE}"}}[5m]))'))

    # ── 6. RL Worker (custom metrics — may not exist yet) ────────────────────
    rl_success    = _scalar(q(f'sum(rl_jobs_processed_total{{namespace="{NAMESPACE}",status="success"}}) or vector(0)'))
    rl_failure    = _scalar(q(f'sum(rl_jobs_processed_total{{namespace="{NAMESPACE}",status="failure"}}) or vector(0)'))
    rl_in_flight  = _scalar(q(f'rl_jobs_in_flight{{namespace="{NAMESPACE}"}} or vector(0)'))
    rl_best_reward = _series(q(f'rl_best_reward{{namespace="{NAMESPACE}"}}'), "sku")
    rl_vs_oracle   = _series(q(f'rl_vs_oracle_pct{{namespace="{NAMESPACE}"}}'), "sku")
    total_rl = rl_success + rl_failure
    rl_failure_rate = round(rl_failure / total_rl * 100, 1) if total_rl > 0 else 0.0

    # ── 7. API HTTP performance ───────────────────────────────────────────────
    # http_request_duration_highr_seconds confirmed present; using starlette-style
    api_rps       = _scalar(q(f'sum(rate(http_request_duration_highr_seconds_count{{namespace="{NAMESPACE}"}}[5m]))'))
    api_p50_ms    = _scalar(q(f'histogram_quantile(0.50, sum by(le) (rate(http_request_duration_highr_seconds_bucket{{namespace="{NAMESPACE}"}}[5m]))) * 1000'))
    api_p99_ms    = _scalar(q(f'histogram_quantile(0.99, sum by(le) (rate(http_request_duration_highr_seconds_bucket{{namespace="{NAMESPACE}"}}[5m]))) * 1000'))
    api_error_rate = _scalar(q(f'sum(rate(http_request_duration_highr_seconds_count{{namespace="{NAMESPACE}",status=~"5.."}}[5m])) / sum(rate(http_request_duration_highr_seconds_count{{namespace="{NAMESPACE}"}}[5m])) * 100'))

    # ── 8. PVC storage ────────────────────────────────────────────────────────
    # Confirmed: kubelet_volume_stats_used_bytes returns replenix-prod PVCs
    pvc_used     = _series(q(f'kubelet_volume_stats_used_bytes{{namespace="{NAMESPACE}"}} / 1073741824'), "persistentvolumeclaim")
    pvc_capacity = _series(q(f'kubelet_volume_stats_capacity_bytes{{namespace="{NAMESPACE}"}} / 1073741824'), "persistentvolumeclaim")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "namespace": NAMESPACE,
        "nodes": {
            "cpu": node_cpu,
            "ram_used_gb": node_ram_used,
            "ram_total_gb": node_ram_total,
            "disk_pct": node_disk,
        },
        "pods": {
            "running": len(pod_running),
            "failed": len(pod_failed),
            "pending": len(pod_pending),
            "running_names": [p["pod"] for p in pod_running],
            "failed_names":  [p["pod"] for p in pod_failed],
            "pending_names": [p["pod"] for p in pod_pending],
            "restarts": [r for r in pod_restarts if r["value"] > 0],
        },
        "deployments": {
            "desired":   {d["deployment"]: int(d["value"]) for d in deploy_desired},
            "available": {d["deployment"]: int(d["value"]) for d in deploy_available},
            "unavailable":{d["deployment"]: int(d["value"]) for d in deploy_unav},
        },
        "containers": {
            "cpu":       container_cpu,
            "ram_mb":    container_ram,
            "ram_limit": container_ram_limit,
        },
        "rabbitmq": {
            "connections":   rmq_connections,
            "channels":      rmq_channels,
            "consumers":     rmq_consumers,
            "queue_ready":   rmq_queue_ready,
            "queue_unacked": rmq_queue_unacked,
            "publish_rate":  rmq_publish_rate,
            "deliver_rate":  rmq_deliver_rate,
        },
        "rl": {
            "jobs_success":        int(rl_success),
            "jobs_failure":        int(rl_failure),
            "jobs_in_flight":      int(rl_in_flight),
            "failure_rate_pct":    rl_failure_rate,
            "best_reward_by_sku":  rl_best_reward,
            "vs_oracle_pct_by_sku": rl_vs_oracle,
        },
        "api": {
            "rps":            api_rps,
            "error_rate_pct": api_error_rate,
            "p50_ms":         api_p50_ms,
            "p99_ms":         api_p99_ms,
        },
        "storage": {
            "used_gb":     pvc_used,
            "capacity_gb": pvc_capacity,
        },
    }


# ── LLM analysis ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior SRE analyst for Replenix, an inventory optimization platform on Kubernetes.
You receive a JSON snapshot of Prometheus metrics. Write a concise, technical health report.

Format (strict markdown):

## Health Status: Green / Yellow / Red
One sentence verdict.

## Key Observations
- Bullet list of the 3-5 most notable findings with exact metric values.
- Only mention what stands out — skip healthy baselines.

## Issues & Risks
- Specific anomalies with pod names, values, counts.
- If none: "None."

## Recommended Actions
- Concrete next steps if issues exist.
- If none: "No action required."

Rules:
- No emojis.
- Max 350 words.
- Use exact values from the data (e.g. "backend pod at 7 restarts", "CPU at 71.5%").
- Be direct, no filler."""


def generate_llm_analysis(metrics: Dict, groq_api_key: str) -> str:
    compact = {
        "namespace": metrics["namespace"],
        "timestamp": metrics["timestamp"],
        "nodes": [
            {
                "node": n["instance"],
                "cpu_pct": n["value"],
                "ram_used_gb": next((r["value"] for r in metrics["nodes"]["ram_used_gb"] if r["instance"] == n["instance"]), 0),
                "ram_total_gb": next((r["value"] for r in metrics["nodes"]["ram_total_gb"] if r["instance"] == n["instance"]), 0),
                "disk_pct": next((r["value"] for r in metrics["nodes"]["disk_pct"] if r["instance"] == n["instance"]), 0),
            }
            for n in metrics["nodes"]["cpu"]
        ],
        "pods": {
            "running": metrics["pods"]["running"],
            "failed": metrics["pods"]["failed"],
            "pending": metrics["pods"]["pending"],
            "restarts": metrics["pods"]["restarts"],
            "failed_names": metrics["pods"]["failed_names"],
        },
        "deployments": metrics["deployments"],
        "containers_top_cpu": sorted(metrics["containers"]["cpu"], key=lambda x: -x["value"])[:8],
        "containers_top_ram": sorted(metrics["containers"]["ram_mb"], key=lambda x: -x["value"])[:8],
        "rabbitmq": metrics["rabbitmq"],
        "rl_training": metrics["rl"],
        "api": metrics["api"],
    }
    client = groq.Groq(api_key=groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"```json\n{json.dumps(compact, indent=2)}\n```"},
        ],
        temperature=0.1,
        max_tokens=700,
    )
    return response.choices[0].message.content.strip()


# ── HTML report builder ───────────────────────────────────────────────────────

def _status_color(value: float, yellow: float, red: float, reverse: bool = False) -> str:
    if reverse:
        return "#DC2626" if value < red else "#D97706" if value < yellow else "#16A34A"
    return "#DC2626" if value >= red else "#D97706" if value >= yellow else "#16A34A"


def _badge(value: float, yellow: float, red: float, unit: str = "", reverse: bool = False) -> str:
    c = _status_color(value, yellow, red, reverse)
    return f'<span style="color:{c};font-weight:700">{value}{unit}</span>'


def _table(headers: list, rows: list) -> str:
    th = "".join(
        f'<th style="padding:12px 16px;text-align:left;border-bottom:1px solid #E5E7EB;font-size:12px;font-weight:600;color:#6B7280;text-transform:uppercase;letter-spacing:0.05em">{h}</th>'
        for h in headers
    )
    body = ""
    for i, row in enumerate(rows):
        bg = "#F9FAFB" if i % 2 == 0 else "#FFFFFF"
        td = "".join(
            f'<td style="padding:12px 16px;border-bottom:1px solid #F3F4F6;font-size:13px;color:#374151">{c}</td>'
            for c in row
        )
        body += f'<tr style="background-color:{bg}">{td}</tr>'
    if not rows:
        body = f'<tr><td colspan="{len(headers)}" style="padding:16px;text-align:center;color:#9CA3AF;font-size:13px;font-style:italic">No data available</td></tr>'
    return f'<div style="border:1px solid #E5E7EB;border-radius:8px;overflow:hidden;margin:12px 0 24px"><table style="width:100%;border-collapse:collapse;background:#FFF">\n<thead><tr style="background-color:#F3F4F6">{th}</tr></thead>\n<tbody>{body}</tbody>\n</table></div>'


def _section(title: str, content: str) -> str:
    return f'''<div style="margin-bottom:32px">
  <h3 style="margin:0 0 12px;font-size:15px;font-weight:700;color:#111827;text-transform:uppercase;letter-spacing:0.05em;border-bottom:2px solid #F3F4F6;padding-bottom:8px">{title}</h3>
  {content}
</div>'''


def _stat_row(*stats) -> str:
    boxes = "".join(
        f'<td style="width:{100/len(stats)}%;padding:16px;text-align:center;border-right:1px solid #E5E7EB">'
        f'<div style="font-size:24px;font-weight:800;color:#111827;line-height:1.2">{val}</div>'
        f'<div style="font-size:11px;font-weight:600;color:#6B7280;margin-top:4px;text-transform:uppercase;letter-spacing:0.05em">{label}</div>'
        f'</td>'
        for label, val in stats
    )
    return f'<div style="border:1px solid #E5E7EB;border-radius:8px;overflow:hidden;margin-bottom:24px;background:#F9FAFB"><table style="width:100%;border-collapse:collapse"><tr>{boxes}</tr></table></div>'


def _md_to_html(md: str) -> str:
    try:
        import markdown as md_lib
        return md_lib.markdown(md)
    except ImportError:
        import re
        html = re.sub(r"^## (.+)$", r"<h4 style='font-size:14px;font-weight:700;margin:12px 0 6px;color:#111827'>\1</h4>", md, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"^[-*] (.+)$", r"<li style='margin:4px 0'>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"(<li[^>]*>.*?</li>)", r"<ul style='margin:6px 0 12px 20px;padding:0;color:#4B5563'>\1</ul>", html, flags=re.DOTALL)
        return html.replace("\n\n", "<br><br>")


def build_html_report(metrics: dict, llm_analysis: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ns = metrics["namespace"]

    if "Red" in llm_analysis[:60]:
        accent = "#DC2626"
        status_label = "CRITICAL"
        bg_accent = "#FEF2F2"
    elif "Yellow" in llm_analysis[:60]:
        accent = "#D97706"
        status_label = "WARNING"
        bg_accent = "#FFFBEB"
    else:
        accent = "#16A34A"
        status_label = "HEALTHY"
        bg_accent = "#F0FDF4"

    llm_section = _section("Analysis & Insights",
        f'<div style="background-color:{bg_accent};border-left:4px solid {accent};border-radius:6px;padding:20px;font-size:14px;line-height:1.6;color:#1F2937">'
        f'{_md_to_html(llm_analysis)}'
        f'</div>')

    cpu_map   = {n["instance"]: n["value"] for n in metrics["nodes"]["cpu"]}
    used_map  = {n["instance"]: n["value"] for n in metrics["nodes"]["ram_used_gb"]}
    total_map = {n["instance"]: n["value"] for n in metrics["nodes"]["ram_total_gb"]}
    disk_map  = {n["instance"]: n["value"] for n in metrics["nodes"]["disk_pct"]}
    node_rows = []
    for node in sorted(cpu_map):
        cpu  = cpu_map.get(node, 0.0)
        used = used_map.get(node, 0.0)
        tot  = total_map.get(node, 0.0)
        disk = disk_map.get(node, 0.0)
        rp   = round(used / tot * 100, 1) if tot > 0 else 0.0
        node_rows.append([
            f'<code style="font-size:12px;color:#4F46E5">{node}</code>',
            _badge(cpu, 60, 80, unit="%"),
            f'{_badge(rp, 70, 85, unit="%")} <span style="color:#9CA3AF;font-size:12px">({used:.1f} / {tot:.1f} GB)</span>',
            _badge(disk, 60, 80, unit="%"),
        ])
    node_section = _section("Cluster Nodes", _table(["Node", "CPU", "Memory", "Disk"], node_rows))

    p = metrics["pods"]
    failed_color = "#DC2626" if p["failed"] > 0 else "#9CA3AF"
    pend_color   = "#D97706" if p["pending"] > 0 else "#9CA3AF"
    pod_stats = _stat_row(
        ("Running", f'<span style="color:#16A34A">{p["running"]}</span>'),
        ("Failed",  f'<span style="color:{failed_color}">{p["failed"]}</span>'),
        ("Pending", f'<span style="color:{pend_color}">{p["pending"]}</span>'),
    )
    restart_rows = [
        [r["pod"], r["container"], _badge(r["value"], 3, 10, unit=" restarts")]
        for r in sorted(p["restarts"], key=lambda x: -x["value"])
    ]
    restart_block = (
        _table(["Pod", "Container", "Restarts"], restart_rows)
        if restart_rows else
        '<p style="font-size:13px;color:#16A34A;margin:8px 0;font-weight:500">✅ No restarts recorded.</p>'
    )
    pod_section = _section("Pod Status", pod_stats + restart_block)

    desired   = metrics["deployments"]["desired"]
    available = metrics["deployments"]["available"]
    unav      = metrics["deployments"]["unavailable"]
    deploy_rows = []
    for d in sorted(desired):
        des = desired.get(d, 0)
        avl = available.get(d, 0)
        un  = unav.get(d, 0)
        status = (
            '<span style="color:#DC2626;font-weight:700">Degraded</span>'
            if un > 0 else
            '<span style="color:#16A34A;font-weight:600">Healthy</span>'
        )
        deploy_rows.append([d, str(des), str(avl), status])
    deploy_section = _section("Deployments",
        _table(["Deployment", "Desired", "Available", "Status"], deploy_rows))

    cpu_lk   = {(c["pod"], c["container"]): c["value"] for c in metrics["containers"]["cpu"]}
    ram_lk   = {(c["pod"], c["container"]): c["value"] for c in metrics["containers"]["ram_mb"]}
    limit_lk = {(c["pod"], c["container"]): c["value"] for c in metrics["containers"]["ram_limit"]}
    all_keys = sorted(set(cpu_lk) | set(ram_lk))
    cont_rows = []
    for pod, container in all_keys:
        cpu  = cpu_lk.get((pod, container), 0.0)
        ram  = ram_lk.get((pod, container), 0.0)
        lim  = limit_lk.get((pod, container), 0.0)
        rp   = round(ram / lim * 100, 1) if lim > 0 else 0.0
        ram_str = (
            f'{ram:.0f} MB / {lim:.0f} MB &nbsp; {_badge(rp, 70, 85, unit="%")}'
            if lim > 0 else f'{ram:.0f} MB'
        )
        cont_rows.append([
            f'<code style="font-size:11px;color:#6B7280">{pod}</code>',
            container,
            _badge(cpu, 50, 80, unit="%"),
            ram_str,
        ])
    cont_section = _section("Container Resources",
        _table(["Pod", "Container", "CPU", "Memory"], cont_rows))

    rmq = metrics["rabbitmq"]
    rmq_stats = _stat_row(
        ("Connections",   str(int(rmq["connections"]))),
        ("Channels",      str(int(rmq["channels"]))),
        ("Consumers",     str(int(rmq["consumers"]))),
        ("Queue Depth",   _badge(rmq["queue_ready"], 20, 100, unit=" msgs")),
        ("Unacked",       str(int(rmq["queue_unacked"]))),
        ("Publish/s",     f'{rmq["publish_rate"]:.1f}'),
        ("Deliver/s",     f'{rmq["deliver_rate"]:.1f}'),
    )
    rmq_section = _section("RabbitMQ", rmq_stats)

    rl = metrics["rl"]
    rl_stats = _stat_row(
        ("Jobs Success",   f'<span style="color:#16A34A">{rl["jobs_success"]}</span>'),
        ("Jobs Failed",    f'<span style="color:{"#DC2626" if rl["jobs_failure"]>0 else "#9CA3AF"}">{rl["jobs_failure"]}</span>'),
        ("In Flight",      str(rl["jobs_in_flight"])),
        ("Failure Rate",   _badge(rl["failure_rate_pct"], 5, 10, unit="%")),
    )
    rl_rows = []
    oracle_lk = {r["sku"]: r["value"] for r in rl["vs_oracle_pct_by_sku"]}
    for r in rl["best_reward_by_sku"]:
        sku = r["sku"]
        op  = oracle_lk.get(sku, 0.0)
        rl_rows.append([sku, f'{r["value"]:,.0f}', _badge(op, 85, 70, unit="%", reverse=True)])
    rl_table = _table(["SKU", "Best Reward", "vs Oracle"], rl_rows)
    rl_section = _section("RL Training", rl_stats + (rl_table if rl_rows else '<p style="font-size:13px;color:#9CA3AF;margin:8px 0;font-style:italic">No RL job data yet.</p>'))

    api = metrics["api"]
    api_stats = _stat_row(
        ("Req/s",       f'{api["rps"]:.2f}'),
        ("5xx Rate",    _badge(api["error_rate_pct"], 1, 5, unit="%")),
        ("p50 Latency", f'{api["p50_ms"]:.0f} ms'),
        ("p99 Latency", _badge(api["p99_ms"], 500, 2000, unit=" ms")),
    )
    api_section = _section("API Performance", api_stats)

    used_lk = {p["persistentvolumeclaim"]: p["value"] for p in metrics["storage"]["used_gb"]}
    cap_lk  = {p["persistentvolumeclaim"]: p["value"] for p in metrics["storage"]["capacity_gb"]}
    pvc_rows = []
    for pvc in sorted(set(used_lk) | set(cap_lk)):
        used = used_lk.get(pvc, 0.0)
        cap  = cap_lk.get(pvc, 0.0)
        pct  = round(used / cap * 100, 1) if cap > 0 else 0.0
        pvc_rows.append([pvc, f'{used:.2f} GB', f'{cap:.2f} GB', _badge(pct, 60, 80, unit="%")])
    storage_section = _section("Persistent Volumes",
        _table(["PVC", "Used", "Capacity", "Usage"], pvc_rows))

    return f"""<!DOCTYPE html>
<html><body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;margin:0;padding:40px 20px;background-color:#F3F4F6;color:#111827">
  <div style="max-width:800px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1),0 2px 4px -1px rgba(0,0,0,0.06)">
    
    <!-- Header -->
    <div style="background-color:{accent};padding:32px 40px;color:#FFFFFF">
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td style="vertical-align:middle">
            <h1 style="margin:0;font-size:28px;font-weight:800;letter-spacing:-0.02em">Replenix Health Report</h1>
            <div style="font-size:13px;opacity:0.9;margin-top:6px;font-weight:500">{ts} &nbsp;&middot;&nbsp; Namespace: <code style="background:rgba(255,255,255,0.2);padding:2px 6px;border-radius:4px">{ns}</code></div>
          </td>
          <td style="vertical-align:middle;text-align:right;width:120px">
            <span style="display:inline-block;background-color:#FFFFFF;color:{accent};font-size:12px;font-weight:800;letter-spacing:0.1em;padding:6px 14px;border-radius:9999px;text-transform:uppercase;box-shadow:0 2px 4px rgba(0,0,0,0.1)">
              {status_label}
            </span>
          </td>
        </tr>
      </table>
    </div>

    <!-- Body -->
    <div style="padding:40px">
      {llm_section}
      {node_section}
      {pod_section}
      {deploy_section}
      {cont_section}
      {rmq_section}
      {rl_section}
      {api_section}
      {storage_section}
    </div>

    <!-- Footer -->
    <div style="background-color:#F9FAFB;border-top:1px solid #E5E7EB;padding:24px 40px;text-align:center">
      <p style="font-size:13px;color:#6B7280;margin:0;line-height:1.5">
        Automated report from the <strong>Replenix Insights Agent</strong>.<br>
        Source: Prometheus (<code style="font-size:12px">{ns}</code>)
      </p>
    </div>
  </div>
</body></html>"""


# ── Email delivery ────────────────────────────────────────────────────────────

def send_email(html_body: str, subject: str, resend_api_key: str,
               to_emails: List[str], from_address: str) -> None:
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {resend_api_key}", "Content-Type": "application/json"},
        json={"from": from_address, "to": to_emails, "subject": subject, "html": html_body},
        timeout=15,
    )
    resp.raise_for_status()
    logger.info(f"[InsightsAgent] Email sent. Resend ID: {resp.json().get('id')}")


# ── Full pipeline ─────────────────────────────────────────────────────────────

def run_insights_pipeline() -> str:
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
    metrics = fetch_all_metrics(prometheus_url)

    logger.info("[InsightsAgent] Running LLM analysis...")
    analysis = generate_llm_analysis(metrics, groq_api_key)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ns = metrics["namespace"]
    status = "RED" if "Red" in analysis[:60] else ("YELLOW" if "Yellow" in analysis[:60] else "GREEN")
    subject = f"[{status}] Replenix Health Report ({ns}) — {ts}"

    logger.info(f"[InsightsAgent] Sending to {to_emails}")
    html_body = build_html_report(metrics, analysis)
    send_email(html_body, subject, resend_api_key, to_emails, from_address)

    return analysis


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = run_insights_pipeline()
    print("\n" + "=" * 60 + "\n" + report)
