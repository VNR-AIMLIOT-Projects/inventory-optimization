import re

with open("apps/Backend-RL/src/services/monitoring_agent.py", "r") as f:
    content = f.read()

start_marker = "def _status_color"
end_marker = "</body></html>\"\"\""

start_idx = content.find(start_marker)
end_idx = content.find(end_marker) + len(end_marker)

if start_idx == -1 or end_idx == -1:
    print("Could not find markers")
    exit(1)

new_code = """def _status_color(value: float, yellow: float, red: float, reverse: bool = False) -> str:
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
    return f'<div style="border:1px solid #E5E7EB;border-radius:8px;overflow:hidden;margin:12px 0 24px"><table style="width:100%;border-collapse:collapse;background:#FFF">\\n<thead><tr style="background-color:#F3F4F6">{th}</tr></thead>\\n<tbody>{body}</tbody>\\n</table></div>'


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
        html = re.sub(r"^## (.+)$", r"<h4 style='font-size:14px;font-weight:700;margin:12px 0 6px;color:#111827'>\\1</h4>", md, flags=re.MULTILINE)
        html = re.sub(r"\\*\\*(.+?)\\*\\*", r"<strong>\\1</strong>", html)
        html = re.sub(r"^[-*] (.+)$", r"<li style='margin:4px 0'>\\1</li>", html, flags=re.MULTILINE)
        html = re.sub(r"(<li[^>]*>.*?</li>)", r"<ul style='margin:6px 0 12px 20px;padding:0;color:#4B5563'>\\1</ul>", html, flags=re.DOTALL)
        return html.replace("\\n\\n", "<br><br>")


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

    return f\"\"\"<!DOCTYPE html>
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
</body></html>\"\"\""""

content = content[:start_idx] + new_code + content[end_idx:]

with open("apps/Backend-RL/src/services/monitoring_agent.py", "w") as f:
    f.write(content)
print("Patched successfully")
