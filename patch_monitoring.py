import re

with open("apps/Backend-RL/src/services/monitoring_agent.py", "r") as f:
    content = f.read()

# 1. Remove NAMESPACE = ...
content = re.sub(r'NAMESPACE = os.environ.get\("NAMESPACE", "replenix-prod"\)\n', '', content)

# 2. Update fetch_all_metrics definition and usages
content = content.replace("def fetch_all_metrics(prometheus_url: str) -> Dict[str, Any]:", "def fetch_all_metrics(prometheus_url: str, namespace: str) -> Dict[str, Any]:")
content = content.replace("{NAMESPACE}", "{namespace}")

# 3. We'll use AST or regex to replace build_html_report and run_insights_pipeline.
# Actually, since build_html_report is the end of the file up to send_email and run_insights_pipeline,
# I will just replace everything from `def build_html_report` to the end of the file.
start_marker = "def build_html_report("
start_idx = content.find(start_marker)

new_code = """def build_html_report(results: list) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Determine overall status (worst case wins)
    overall_status = "HEALTHY"
    overall_accent = "#16A34A"
    for r in results:
        if r["status"] == "CRITICAL":
            overall_status = "CRITICAL"
            overall_accent = "#DC2626"
            break
        elif r["status"] == "WARNING":
            overall_status = "WARNING"
            overall_accent = "#D97706"

    sections_html = ""
    for r in results:
        ns = r["namespace"]
        metrics = r["metrics"]
        llm_analysis = r["analysis"]
        
        if r["status"] == "CRITICAL":
            accent = "#DC2626"
            bg_accent = "#FEF2F2"
        elif r["status"] == "WARNING":
            accent = "#D97706"
            bg_accent = "#FFFBEB"
        else:
            accent = "#16A34A"
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
            [row["pod"], row["container"], _badge(row["value"], 3, 10, unit=" restarts")]
            for row in sorted(p["restarts"], key=lambda x: -x["value"])
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
            status_text = (
                '<span style="color:#DC2626;font-weight:700">Degraded</span>'
                if un > 0 else
                '<span style="color:#16A34A;font-weight:600">Healthy</span>'
            )
            deploy_rows.append([d, str(des), str(avl), status_text])
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
        oracle_lk = {row["sku"]: row["value"] for row in rl["vs_oracle_pct_by_sku"]}
        for row in rl["best_reward_by_sku"]:
            sku = row["sku"]
            op  = oracle_lk.get(sku, 0.0)
            rl_rows.append([sku, f'{row["value"]:,.0f}', _badge(op, 85, 70, unit="%", reverse=True)])
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

        # Add an environment header for this section
        sections_html += f'''
        <div style="margin-top: 40px; margin-bottom: 24px; padding-bottom: 12px; border-bottom: 3px solid {accent}; display: flex; justify-content: space-between; align-items: baseline;">
          <h2 style="margin: 0; font-size: 22px; font-weight: 800; color: #111827; text-transform: uppercase; letter-spacing: 0.02em;">{ns}</h2>
          <span style="font-size: 14px; font-weight: 700; color: {accent}; letter-spacing: 0.05em; text-transform: uppercase;">{r["status"]}</span>
        </div>
        '''
        sections_html += llm_section + node_section + pod_section + deploy_section + cont_section + rmq_section + rl_section + api_section + storage_section


    return f\"\"\"<!DOCTYPE html>
<html><body style="font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;margin:0;padding:40px 20px;background-color:#F3F4F6;color:#111827">
  <div style="max-width:800px;margin:0 auto;background:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1),0 2px 4px -1px rgba(0,0,0,0.06)">
    
    <!-- Header -->
    <div style="background-color:{overall_accent};padding:32px 40px;color:#FFFFFF">
      <table style="width:100%;border-collapse:collapse">
        <tr>
          <td style="vertical-align:middle">
            <h1 style="margin:0;font-size:28px;font-weight:800;letter-spacing:-0.02em">Unified Health Report</h1>
            <div style="font-size:13px;opacity:0.9;margin-top:6px;font-weight:500">{ts} &nbsp;&middot;&nbsp; Environments: {', '.join([r['namespace'] for r in results])}</div>
          </td>
          <td style="vertical-align:middle;text-align:right;width:120px">
            <span style="display:inline-block;background-color:#FFFFFF;color:{overall_accent};font-size:12px;font-weight:800;letter-spacing:0.1em;padding:6px 14px;border-radius:9999px;text-transform:uppercase;box-shadow:0 2px 4px rgba(0,0,0,0.1)">
              {overall_status}
            </span>
          </td>
        </tr>
      </table>
    </div>

    <!-- Body -->
    <div style="padding: 10px 40px 40px 40px">
      {sections_html}
    </div>

    <!-- Footer -->
    <div style="background-color:#F9FAFB;border-top:1px solid #E5E7EB;padding:24px 40px;text-align:center">
      <p style="font-size:13px;color:#6B7280;margin:0;line-height:1.5">
        Automated report from the <strong>Replenix Insights Agent</strong>.<br>
        Source: Prometheus
      </p>
    </div>
  </div>
</body></html>\"\"\"

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

def run_insights_pipeline() -> List[str]:
    prometheus_url = os.environ.get(
        "PROMETHEUS_URL",
        "http://replenix-prometheus-kube-p-prometheus.monitoring.svc.cluster.local:9090",
    )
    groq_api_key   = os.environ["GROQ_API_KEY"]
    resend_api_key = os.environ["RESEND_API_KEY"]
    from_address   = os.environ.get("RESEND_FROM", "Replenix System <noreply@replenix.app>")
    to_raw         = os.environ.get("REPORT_EMAIL_TO", "sujaynsv@gmail.com,rishitsura@gmail.com")
    to_emails      = [e.strip() for e in to_raw.split(",") if e.strip()]
    
    namespaces_raw = os.environ.get("NAMESPACES", "replenix-prod,replenix-preprod")
    namespaces = [n.strip() for n in namespaces_raw.split(",") if n.strip()]

    results = []
    analyses = []
    
    for ns in namespaces:
        logger.info(f"[InsightsAgent] Fetching metrics for {ns} from {prometheus_url}")
        metrics = fetch_all_metrics(prometheus_url, ns)

        logger.info(f"[InsightsAgent] Running LLM analysis for {ns}...")
        analysis = generate_llm_analysis(metrics, groq_api_key)
        
        status = "CRITICAL" if "Red" in analysis[:60] else ("WARNING" if "Yellow" in analysis[:60] else "HEALTHY")
        
        results.append({
            "namespace": ns,
            "metrics": metrics,
            "analysis": analysis,
            "status": status
        })
        analyses.append(analysis)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    overall_status = "HEALTHY"
    for r in results:
        if r["status"] == "CRITICAL":
            overall_status = "CRITICAL"
            break
        elif r["status"] == "WARNING":
            overall_status = "WARNING"
            
    subject = f"[{overall_status}] Unified Replenix Health Report — {ts}"

    logger.info(f"[InsightsAgent] Sending to {to_emails}")
    html_body = build_html_report(results)
    send_email(html_body, subject, resend_api_key, to_emails, from_address)

    return analyses


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    reports = run_insights_pipeline()
    for report in reports:
        print("\\n" + "=" * 60 + "\\n" + report)
"""

content = content[:start_idx] + new_code

with open("apps/Backend-RL/src/services/monitoring_agent.py", "w") as f:
    f.write(content)
print("Patched Python file")
