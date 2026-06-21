"""
Automated Insights Agent — Comprehensive Edition
=================================================
Fetches detailed metrics from Prometheus (pod status, per-container CPU/RAM,
deployments, RabbitMQ, RL training, API perf), builds an HTML report with
metric tables + an LLM-generated analysis section, and sends via Resend.

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

# ── Prometheus helpers ────────────────────────────────────────────────────────

def _query(base_url: str, promql: str, timeout: int = 10) -> List[dict]:
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
        logger.warning(f"[InsightsAgent] Query failed ({promql[:60]}): {e}")
        return []


def _scalar(results: List[dict]) -> float:
    """Extract a single float from a Prometheus result."""
    try:
        return round(float(results[0]["value"][1]), 2)
    except (IndexError, KeyError, ValueError):
        return 0.0


def _series(results: List[dict], *label_keys: str) -> List[dict]:
    """
    Convert Prometheus results into a list of dicts:
    { label_key: label_value, ..., "value": float }
    """
    out = []
    for r in results:
        entry = {k: r["metric"].get(k, "—") for k in label_keys}
        try:
            entry["value"] = round(float(r["value"][1]), 2)
        except (KeyError, ValueError):
            entry["value"] = 0.0
        out.append(entry)
    return sorted(out, key=lambda x: x.get(label_keys[0], ""))


# ── Metric collection ─────────────────────────────────────────────────────────

NAMESPACE = "replenix-prod"  # adjust if needed


def fetch_all_metrics(prometheus_url: str) -> Dict[str, Any]:
    """
    Pull a comprehensive snapshot across all dashboard categories.
    All failures are handled gracefully (returns 0 / empty list).
    """
    q = lambda promql: _query(prometheus_url, promql)  # noqa: E731

    # ── 1. Node-level ────────────────────────────────────────────────────────
    node_cpu_pct = _series(
        q('100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)'),
        "instance",
    )
    node_ram_used_gb = _series(
        q('(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1073741824'),
        "instance",
    )
    node_ram_total_gb = _series(
        q('node_memory_MemTotal_bytes / 1073741824'),
        "instance",
    )
    node_disk_pct = _series(
        q('100 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"} * 100)'),
        "instance",
    )
    node_network_rx = _series(
        q('sum by(instance) (rate(node_network_receive_bytes_total[5m])) / 1024'),
        "instance",
    )
    node_network_tx = _series(
        q('sum by(instance) (rate(node_network_transmit_bytes_total[5m])) / 1024'),
        "instance",
    )

    # ── 2. Pod / Deployment status ───────────────────────────────────────────
    pods_running = _series(
        q(f'kube_pod_status_phase{{namespace="{NAMESPACE}",phase="Running"}}'),
        "pod", "phase",
    )
    pods_failed = _series(
        q(f'kube_pod_status_phase{{namespace="{NAMESPACE}",phase="Failed"}}'),
        "pod", "phase",
    )
    pods_pending = _series(
        q(f'kube_pod_status_phase{{namespace="{NAMESPACE}",phase="Pending"}}'),
        "pod", "phase",
    )
    pod_restarts = _series(
        q(f'kube_pod_container_status_restarts_total{{namespace="{NAMESPACE}"}}'),
        "pod", "container",
    )
    pod_restarts = [p for p in pod_restarts if p["value"] > 0]  # only non-zero

    # Deployment desired vs available
    deploy_desired = _series(
        q(f'kube_deployment_spec_replicas{{namespace="{NAMESPACE}"}}'),
        "deployment",
    )
    deploy_available = _series(
        q(f'kube_deployment_status_replicas_available{{namespace="{NAMESPACE}"}}'),
        "deployment",
    )
    deploy_unavailable = _series(
        q(f'kube_deployment_status_replicas_unavailable{{namespace="{NAMESPACE}"}}'),
        "deployment",
    )

    # ── 3. Container-level CPU & RAM ─────────────────────────────────────────
    container_cpu_pct = _series(
        q(f'round(rate(container_cpu_usage_seconds_total{{namespace="{NAMESPACE}",container!="",container!="POD"}}[5m]) * 100, 0.01)'),
        "pod", "container",
    )
    container_ram_mb = _series(
        q(f'container_memory_working_set_bytes{{namespace="{NAMESPACE}",container!="",container!="POD"}} / 1048576'),
        "pod", "container",
    )
    container_ram_limit_mb = _series(
        q(f'kube_pod_container_resource_limits{{namespace="{NAMESPACE}",resource="memory",unit="byte"}} / 1048576'),
        "pod", "container",
    )

    # ── 4. RabbitMQ ──────────────────────────────────────────────────────────
    rmq_ready = _series(q('rabbitmq_queue_messages_ready'), "queue", "vhost")
    rmq_unacked = _series(q('rabbitmq_queue_messages_unacknowledged'), "queue", "vhost")
    rmq_consumers = _series(q('rabbitmq_queue_consumers'), "queue")
    rmq_connections = _scalar(q('rabbitmq_connections'))
    rmq_publish_rate = _scalar(q('rate(rabbitmq_global_messages_published_total[5m])'))
    rmq_deliver_rate = _scalar(q('rate(rabbitmq_global_messages_delivered_total[5m])'))

    # ── 5. RL Worker metrics ──────────────────────────────────────────────────
    rl_success = _scalar(q('sum(rl_jobs_processed_total{status="success"}) or vector(0)'))
    rl_failure = _scalar(q('sum(rl_jobs_processed_total{status="failure"}) or vector(0)'))
    rl_in_flight = _scalar(q('rl_jobs_in_flight or vector(0)'))
    rl_best_reward = _series(q('rl_best_reward'), "sku")
    rl_vs_oracle = _series(q('rl_vs_oracle_pct'), "sku")
    rl_duration_p50 = _scalar(q('histogram_quantile(0.50, rate(rl_training_duration_seconds_bucket[1h]))'))
    rl_duration_p99 = _scalar(q('histogram_quantile(0.99, rate(rl_training_duration_seconds_bucket[1h]))'))
    total_rl = rl_success + rl_failure
    rl_failure_rate = round((rl_failure / total_rl * 100), 1) if total_rl > 0 else 0.0

    # ── 6. FastAPI performance ────────────────────────────────────────────────
    api_rps = _scalar(q('sum(rate(http_requests_total[5m]))'))
    api_error_rate = _scalar(q(
        'sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100'
    ))
    api_p50_ms = _scalar(q(
        'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000'
    ))
    api_p99_ms = _scalar(q(
        'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000'
    ))
    api_slowest = _series(
        q('topk(5, histogram_quantile(0.99, sum by(handler, le) (rate(http_request_duration_seconds_bucket[5m]))) * 1000)'),
        "handler",
    )

    # ── 7. PVC / Storage ─────────────────────────────────────────────────────
    pvc_used_gb = _series(
        q(f'kubelet_volume_stats_used_bytes{{namespace="{NAMESPACE}"}} / 1073741824'),
        "persistentvolumeclaim",
    )
    pvc_capacity_gb = _series(
        q(f'kubelet_volume_stats_capacity_bytes{{namespace="{NAMESPACE}"}} / 1073741824'),
        "persistentvolumeclaim",
    )

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "namespace": NAMESPACE,
        "nodes": {
            "cpu_pct": node_cpu_pct,
            "ram_used_gb": node_ram_used_gb,
            "ram_total_gb": node_ram_total_gb,
            "disk_pct": node_disk_pct,
            "net_rx_kbps": node_network_rx,
            "net_tx_kbps": node_network_tx,
        },
        "pods": {
            "running": len(pods_running),
            "failed": len(pods_failed),
            "pending": len(pods_pending),
            "running_list": [p["pod"] for p in pods_running],
            "failed_list": [p["pod"] for p in pods_failed],
            "pending_list": [p["pod"] for p in pods_pending],
            "restarts": pod_restarts,
        },
        "deployments": {
            "desired": {d["deployment"]: int(d["value"]) for d in deploy_desired},
            "available": {d["deployment"]: int(d["value"]) for d in deploy_available},
            "unavailable": {d["deployment"]: int(d["value"]) for d in deploy_unavailable},
        },
        "containers": {
            "cpu_pct": container_cpu_pct,
            "ram_mb": container_ram_mb,
            "ram_limit_mb": container_ram_limit_mb,
        },
        "rabbitmq": {
            "connections": rmq_connections,
            "publish_rate": rmq_publish_rate,
            "deliver_rate": rmq_deliver_rate,
            "queues_ready": rmq_ready,
            "queues_unacked": rmq_unacked,
            "consumers": rmq_consumers,
        },
        "rl": {
            "jobs_success": int(rl_success),
            "jobs_failure": int(rl_failure),
            "jobs_in_flight": int(rl_in_flight),
            "failure_rate_pct": rl_failure_rate,
            "best_reward_by_sku": rl_best_reward,
            "vs_oracle_pct_by_sku": rl_vs_oracle,
            "train_duration_p50_s": rl_duration_p50,
            "train_duration_p99_s": rl_duration_p99,
        },
        "api": {
            "rps": api_rps,
            "error_rate_pct": api_error_rate,
            "p50_latency_ms": api_p50_ms,
            "p99_latency_ms": api_p99_ms,
            "slowest_endpoints": api_slowest,
        },
        "storage": {
            "pvc_used_gb": pvc_used_gb,
            "pvc_capacity_gb": pvc_capacity_gb,
        },
    }


# ── LLM analysis ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior SRE analyst for the Replenix inventory optimization platform running on Kubernetes.
You receive a comprehensive JSON snapshot of real Prometheus metrics covering nodes, pods, containers, RabbitMQ, RL training, and API performance.

Your output MUST follow this exact markdown structure:

## Overall Health: 🟢 Green / 🟡 Yellow / 🔴 Red
[one sentence verdict]

## Key Findings
[bullet list of the 3-5 most important observations — only mention metrics that are notable, unusual, or warrant attention. Skip metrics that are perfectly normal.]

## Anomalies & Risks
[bullet list of specific issues with exact values, e.g. "Pod backend-7d4c-xyz restarted 3 times in the last hour". If none, write "None detected."]

## Recommendations
[bullet list of concrete actions if any issues found. If everything is healthy, write "No actions required."]

Rules:
- Be specific: include exact metric values (e.g. "CPU at 73.4%", "RAM 2.1/4.0 GB")
- Maximum 400 words total
- Skip sections that have nothing to report
- Do NOT repeat all metrics verbatim — only highlight what matters"""


def generate_llm_analysis(metrics: Dict, groq_api_key: str) -> str:
    """Send compact metric snapshot to Groq → get back structured markdown analysis."""
    # Build a compact summary for the LLM (exclude raw per-item lists that are shown in tables)
    compact = {
        "timestamp": metrics["timestamp"],
        "namespace": metrics["namespace"],
        "node_cpu_pct_by_node": {n["instance"]: n["value"] for n in metrics["nodes"]["cpu_pct"]},
        "node_ram_usage_gb_by_node": {
            n["instance"]: f"{u['value']:.1f}/{t['value']:.1f}"
            for n, u, t in zip(
                metrics["nodes"]["cpu_pct"],
                metrics["nodes"]["ram_used_gb"],
                metrics["nodes"]["ram_total_gb"],
            )
        },
        "pods_running": metrics["pods"]["running"],
        "pods_failed": metrics["pods"]["failed"],
        "pods_pending": metrics["pods"]["pending"],
        "pods_with_restarts": metrics["pods"]["restarts"],
        "deployments": metrics["deployments"],
        "top_containers_by_cpu": sorted(
            metrics["containers"]["cpu_pct"], key=lambda x: -x["value"]
        )[:8],
        "top_containers_by_ram_mb": sorted(
            metrics["containers"]["ram_mb"], key=lambda x: -x["value"]
        )[:8],
        "rabbitmq_connections": metrics["rabbitmq"]["connections"],
        "rabbitmq_queue_depth": metrics["rabbitmq"]["queues_ready"],
        "rl_jobs_success": metrics["rl"]["jobs_success"],
        "rl_jobs_failure": metrics["rl"]["jobs_failure"],
        "rl_failure_rate_pct": metrics["rl"]["failure_rate_pct"],
        "rl_in_flight": metrics["rl"]["jobs_in_flight"],
        "rl_vs_oracle": metrics["rl"]["vs_oracle_pct_by_sku"],
        "api_rps": metrics["api"]["rps"],
        "api_error_rate_pct": metrics["api"]["error_rate_pct"],
        "api_p50_ms": metrics["api"]["p50_latency_ms"],
        "api_p99_ms": metrics["api"]["p99_latency_ms"],
        "api_slowest_endpoints": metrics["api"]["slowest_endpoints"],
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

def _badge(value: float, yellow: float, red: float, reverse: bool = False, unit: str = "") -> str:
    """Return a coloured badge span. reverse=True means lower is worse (e.g. RL vs oracle)."""
    if reverse:
        color = "#e53e3e" if value < red else "#d69e2e" if value < yellow else "#38a169"
    else:
        color = "#e53e3e" if value >= red else "#d69e2e" if value >= yellow else "#38a169"
    bg = color + "22"
    return f'<span style="color:{color};background:{bg};padding:2px 6px;border-radius:4px;font-weight:600">{value}{unit}</span>'


def _table(headers: List[str], rows: List[List[str]]) -> str:
    """Render a simple HTML table."""
    th = "".join(f'<th style="padding:6px 12px;text-align:left;border-bottom:2px solid #e2e8f0;font-size:12px;color:#718096;text-transform:uppercase">{h}</th>' for h in headers)
    body = ""
    for i, row in enumerate(rows):
        bg = "#f7fafc" if i % 2 == 0 else "#ffffff"
        td = "".join(f'<td style="padding:6px 12px;border-bottom:1px solid #e2e8f0;font-size:13px">{c}</td>' for c in row)
        body += f'<tr style="background:{bg}">{td}</tr>'
    if not rows:
        body = f'<tr><td colspan="{len(headers)}" style="padding:8px 12px;color:#a0aec0;font-style:italic;font-size:13px">No data available</td></tr>'
    return f'<table style="width:100%;border-collapse:collapse;margin-bottom:20px"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>'


def _section(title: str, icon: str, content: str) -> str:
    return f'''
    <div style="margin-bottom:28px">
      <h3 style="margin:0 0 10px 0;font-size:15px;font-weight:700;color:#2d3748;border-left:4px solid #667eea;padding-left:10px">{icon} {title}</h3>
      {content}
    </div>'''


def _md_to_html(md: str) -> str:
    try:
        import markdown as md_lib  # type: ignore
        return md_lib.markdown(md, extensions=["nl2br"])
    except ImportError:
        import re
        html = re.sub(r"^## (.+)$", r"<h2 style='font-size:14px;margin:12px 0 6px'>\1</h2>", md, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"^- (.+)$", r"<li style='margin-bottom:4px'>\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"(<li.*</li>)", r"<ul style='margin:6px 0 6px 16px;padding:0'>\1</ul>", html, flags=re.DOTALL)
        return html.replace("\n\n", "<br>")


def build_html_report(metrics: Dict, llm_analysis: str) -> str:
    """Build a rich, multi-section HTML email body."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ns = metrics["namespace"]

    # ── LLM analysis section ─────────────────────────────────────────────────
    # Extract overall status emoji from LLM output for header colour
    overall_color = "#38a169"  # green default
    if "🔴" in llm_analysis:
        overall_color = "#e53e3e"
    elif "🟡" in llm_analysis:
        overall_color = "#d69e2e"

    llm_html = _section("AI-Generated Analysis & Insights", "🤖", f'<div style="background:#f0f4ff;border-radius:8px;padding:16px;font-size:13px;line-height:1.7">{_md_to_html(llm_analysis)}</div>')

    # ── Node health ──────────────────────────────────────────────────────────
    node_rows = []
    cpu_map = {n["instance"]: n["value"] for n in metrics["nodes"]["cpu_pct"]}
    ram_used_map = {n["instance"]: n["value"] for n in metrics["nodes"]["ram_used_gb"]}
    ram_total_map = {n["instance"]: n["value"] for n in metrics["nodes"]["ram_total_gb"]}
    disk_map = {n["instance"]: n["value"] for n in metrics["nodes"]["disk_pct"]}
    for node in cpu_map:
        cpu = cpu_map.get(node, 0.0)
        ru = ram_used_map.get(node, 0.0)
        rt = ram_total_map.get(node, 0.0)
        disk = disk_map.get(node, 0.0)
        ram_pct = round(ru / rt * 100, 1) if rt > 0 else 0.0
        node_rows.append([
            f'<code style="font-size:11px">{node}</code>',
            _badge(cpu, 60, 80, unit="%"),
            f'{_badge(ram_pct, 70, 85, unit="%")} <span style="color:#a0aec0;font-size:11px">({ru:.1f}/{rt:.1f} GB)</span>',
            _badge(disk, 70, 85, unit="%"),
        ])
    node_section = _section("Cluster Nodes", "🖥️", _table(["Node", "CPU", "RAM", "Disk"], node_rows))

    # ── Pod status ───────────────────────────────────────────────────────────
    pod_summary = f'''
    <div style="display:flex;gap:16px;margin-bottom:12px">
      <div style="flex:1;background:#f0fff4;border:1px solid #c6f6d5;border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:28px;font-weight:700;color:#38a169">{metrics["pods"]["running"]}</div>
        <div style="font-size:12px;color:#718096;margin-top:2px">Running</div>
      </div>
      <div style="flex:1;background:{"#fff5f5" if metrics["pods"]["failed"] > 0 else "#f7fafc"};border:1px solid {"#fed7d7" if metrics["pods"]["failed"] > 0 else "#e2e8f0"};border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:28px;font-weight:700;color:{"#e53e3e" if metrics["pods"]["failed"] > 0 else "#a0aec0"}">{metrics["pods"]["failed"]}</div>
        <div style="font-size:12px;color:#718096;margin-top:2px">Failed</div>
      </div>
      <div style="flex:1;background:{"#fffff0" if metrics["pods"]["pending"] > 0 else "#f7fafc"};border:1px solid {"#fefcbf" if metrics["pods"]["pending"] > 0 else "#e2e8f0"};border-radius:8px;padding:12px;text-align:center">
        <div style="font-size:28px;font-weight:700;color:{"#d69e2e" if metrics["pods"]["pending"] > 0 else "#a0aec0"}">{metrics["pods"]["pending"]}</div>
        <div style="font-size:12px;color:#718096;margin-top:2px">Pending</div>
      </div>
    </div>'''

    restart_rows = [
        [r["pod"], r["container"], _badge(r["value"], 3, 10, unit="x")]
        for r in sorted(metrics["pods"]["restarts"], key=lambda x: -x["value"])
    ]
    restart_table = _table(["Pod", "Container", "Restarts"], restart_rows)
    pod_section = _section("Pod Status", "📦", pod_summary + ('<b style="font-size:12px;color:#4a5568">Pods with Restarts:</b>' + restart_table if restart_rows else '<p style="color:#38a169;font-size:13px">✅ No pod restarts recorded</p>'))

    # ── Deployments ──────────────────────────────────────────────────────────
    desired = metrics["deployments"]["desired"]
    available = metrics["deployments"]["available"]
    unavailable = metrics["deployments"]["unavailable"]
    deploy_rows = []
    for d in sorted(desired.keys()):
        des = desired.get(d, 0)
        avl = available.get(d, 0)
        unav = unavailable.get(d, 0)
        status = "✅ Healthy" if unav == 0 else f'<span style="color:#e53e3e">⚠️ {unav} unavailable</span>'
        deploy_rows.append([d, str(des), str(avl), status])
    deploy_section = _section("Deployments", "🚀", _table(["Deployment", "Desired", "Available", "Status"], deploy_rows))

    # ── Container resources ───────────────────────────────────────────────────
    # Merge CPU and RAM by (pod, container) key
    cpu_lookup = {(c["pod"], c["container"]): c["value"] for c in metrics["containers"]["cpu_pct"]}
    ram_lookup = {(c["pod"], c["container"]): c["value"] for c in metrics["containers"]["ram_mb"]}
    limit_lookup = {(c["pod"], c["container"]): c["value"] for c in metrics["containers"]["ram_limit_mb"]}
    all_keys = set(cpu_lookup) | set(ram_lookup)
    container_rows = []
    for pod, container in sorted(all_keys):
        cpu = cpu_lookup.get((pod, container), 0.0)
        ram = ram_lookup.get((pod, container), 0.0)
        limit = limit_lookup.get((pod, container), 0.0)
        ram_pct = round(ram / limit * 100, 1) if limit > 0 else 0.0
        ram_str = f"{ram:.0f} MB" + (f" / {limit:.0f} MB ({_badge(ram_pct, 70, 85, unit='%')})" if limit > 0 else "")
        container_rows.append([
            f'<code style="font-size:11px">{pod[:40]}</code>',
            container,
            _badge(cpu, 50, 80, unit="%"),
            ram_str,
        ])
    container_rows = sorted(container_rows, key=lambda r: r[0])
    container_section = _section("Container Resources", "📊",
        _table(["Pod", "Container", "CPU", "RAM"], container_rows))

    # ── RabbitMQ ─────────────────────────────────────────────────────────────
    rmq_summary = f'''
    <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap">
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center;min-width:100px">
        <div style="font-size:20px;font-weight:700;color:#4a5568">{metrics["rabbitmq"]["connections"]:.0f}</div>
        <div style="font-size:11px;color:#718096">Connections</div>
      </div>
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center;min-width:100px">
        <div style="font-size:20px;font-weight:700;color:#4a5568">{metrics["rabbitmq"]["publish_rate"]:.1f}/s</div>
        <div style="font-size:11px;color:#718096">Publish Rate</div>
      </div>
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center;min-width:100px">
        <div style="font-size:20px;font-weight:700;color:#4a5568">{metrics["rabbitmq"]["deliver_rate"]:.1f}/s</div>
        <div style="font-size:11px;color:#718096">Deliver Rate</div>
      </div>
    </div>'''

    ready_lookup = {r["queue"]: r["value"] for r in metrics["rabbitmq"]["queues_ready"]}
    unacked_lookup = {r["queue"]: r["value"] for r in metrics["rabbitmq"]["queues_unacked"]}
    consumer_lookup = {r["queue"]: r["value"] for r in metrics["rabbitmq"]["consumers"]}
    all_queues = set(ready_lookup) | set(unacked_lookup)
    queue_rows = []
    for q_name in sorted(all_queues):
        ready = ready_lookup.get(q_name, 0)
        unacked = unacked_lookup.get(q_name, 0)
        consumers = consumer_lookup.get(q_name, 0)
        queue_rows.append([q_name, _badge(ready, 20, 100, unit=" msgs"), str(int(unacked)), str(int(consumers))])
    rmq_section = _section("RabbitMQ", "🐇", rmq_summary + _table(["Queue", "Ready", "Unacked", "Consumers"], queue_rows))

    # ── RL Training ───────────────────────────────────────────────────────────
    rl = metrics["rl"]
    rl_summary = f'''
    <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap">
      <div style="background:#f0fff4;border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:#38a169">{rl["jobs_success"]}</div>
        <div style="font-size:11px;color:#718096">Jobs Success</div>
      </div>
      <div style="background:{"#fff5f5" if rl["jobs_failure"]>0 else "#f7fafc"};border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:{"#e53e3e" if rl["jobs_failure"]>0 else "#a0aec0"}">{rl["jobs_failure"]}</div>
        <div style="font-size:11px;color:#718096">Jobs Failed</div>
      </div>
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:#667eea">{rl["jobs_in_flight"]}</div>
        <div style="font-size:11px;color:#718096">In Flight</div>
      </div>
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:#4a5568">{rl["failure_rate_pct"]}%</div>
        <div style="font-size:11px;color:#718096">Failure Rate</div>
      </div>
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:#4a5568">{rl["train_duration_p50_s"]:.0f}s</div>
        <div style="font-size:11px;color:#718096">Train p50</div>
      </div>
    </div>'''
    rl_rows = []
    oracle_lookup = {r["sku"]: r["value"] for r in rl["vs_oracle_pct_by_sku"]}
    for r in rl["best_reward_by_sku"]:
        sku = r["sku"]
        oracle_pct = oracle_lookup.get(sku, 0.0)
        rl_rows.append([sku, f'{r["value"]:,.0f}', _badge(oracle_pct, 85, 70, reverse=True, unit="%")])
    rl_section = _section("RL Training Performance", "🧠", rl_summary + _table(["SKU", "Best Reward", "vs Oracle"], rl_rows))

    # ── API performance ───────────────────────────────────────────────────────
    api = metrics["api"]
    api_summary = f'''
    <div style="display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap">
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:#4a5568">{api["rps"]:.1f}/s</div>
        <div style="font-size:11px;color:#718096">Requests/sec</div>
      </div>
      <div style="background:{"#fff5f5" if api["error_rate_pct"]>1 else "#f7fafc"};border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700">{_badge(api["error_rate_pct"], 1, 5, unit="%")}</div>
        <div style="font-size:11px;color:#718096">5xx Error Rate</div>
      </div>
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700;color:#4a5568">{api["p50_latency_ms"]:.0f}ms</div>
        <div style="font-size:11px;color:#718096">p50 Latency</div>
      </div>
      <div style="background:#f7fafc;border-radius:6px;padding:10px 16px;text-align:center">
        <div style="font-size:20px;font-weight:700">{_badge(api["p99_latency_ms"], 500, 2000, unit="ms")}</div>
        <div style="font-size:11px;color:#718096">p99 Latency</div>
      </div>
    </div>'''
    endpoint_rows = [[e["handler"], _badge(e["value"], 500, 2000, unit="ms")] for e in api["slowest_endpoints"]]
    api_section = _section("API Performance", "⚡", api_summary + _table(["Slowest Endpoints (p99)", "Latency"], endpoint_rows))

    # ── Storage ───────────────────────────────────────────────────────────────
    used_lookup = {p["persistentvolumeclaim"]: p["value"] for p in metrics["storage"]["pvc_used_gb"]}
    cap_lookup = {p["persistentvolumeclaim"]: p["value"] for p in metrics["storage"]["pvc_capacity_gb"]}
    pvc_rows = []
    for pvc in sorted(set(used_lookup) | set(cap_lookup)):
        used = used_lookup.get(pvc, 0.0)
        cap = cap_lookup.get(pvc, 0.0)
        pct = round(used / cap * 100, 1) if cap > 0 else 0.0
        pvc_rows.append([pvc, f"{used:.2f} GB", f"{cap:.2f} GB", _badge(pct, 70, 85, unit="%")])
    storage_section = _section("Persistent Storage (PVCs)", "💾", _table(["PVC", "Used", "Capacity", "Usage"], pvc_rows))

    # ── Assemble full email ───────────────────────────────────────────────────
    return f"""
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;max-width:780px;margin:auto;padding:24px;background:#ffffff">

  <div style="background:linear-gradient(135deg,{overall_color}22,#667eea22);border-radius:12px;padding:20px 24px;margin-bottom:28px;border-left:5px solid {overall_color}">
    <h1 style="margin:0 0 4px 0;font-size:20px;font-weight:800;color:#1a202c">Replenix Automated Health Report</h1>
    <p style="margin:0;color:#718096;font-size:13px">Generated: {ts} &nbsp;|&nbsp; Namespace: <code>{ns}</code></p>
  </div>

  {llm_html}
  {node_section}
  {pod_section}
  {deploy_section}
  {container_section}
  {rmq_section}
  {rl_section}
  {api_section}
  {storage_section}

  <p style="color:#a0aec0;font-size:11px;margin-top:32px;border-top:1px solid #e2e8f0;padding-top:12px">
    This is an automated report from the Replenix Insights Agent. Metrics sourced from Prometheus (<code>{NAMESPACE}</code>).
    To unsubscribe or change schedule, update <code>REPORT_EMAIL_TO</code> in your GitHub Secrets.
  </p>
</body></html>"""


# ── Email delivery ────────────────────────────────────────────────────────────

def send_email(html_body: str, subject: str, resend_api_key: str, to_emails: List[str], from_address: str) -> None:
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
    """Fetch → Analyse → Send. Returns the LLM analysis markdown."""
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

    emoji = "🔴" if "🔴" in analysis else ("🟡" if "🟡" in analysis else "🟢")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = f"{emoji} Replenix Health Report — {ts}"

    logger.info(f"[InsightsAgent] Building HTML report and sending to {to_emails}")
    html_body = build_html_report(metrics, analysis)
    send_email(html_body, subject, resend_api_key, to_emails, from_address)

    return analysis


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = run_insights_pipeline()
    print("\n" + "=" * 60)
    print(report)
