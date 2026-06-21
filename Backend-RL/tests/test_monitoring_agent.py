"""
Tests for the monitoring_agent service.
All external calls (Prometheus, Groq, Resend) are mocked.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _prom_result(value: float) -> list:
    """Minimal Prometheus instant-query result for a single scalar."""
    return [{"metric": {}, "value": [0, str(value)]}]


def _prom_result_with_label(label_key: str, label_val: str, value: float) -> list:
    return [{"metric": {label_key: label_val}, "value": [0, str(value)]}]


# ── fetch_prometheus_metrics ──────────────────────────────────────────────────

class TestFetchPrometheusMetrics:
    def _make_prom_responses(self, overrides: dict = None) -> dict:
        """Build default Prometheus HTTP responses for all queries."""
        defaults = {
            "cpu_pct": _prom_result(45.0),
            "ram_pct": _prom_result(60.0),
            "queue_depth": _prom_result(5),
            "rl_jobs_success": _prom_result(100),
            "rl_jobs_failure": _prom_result(2),
            "rl_jobs_in_flight": _prom_result(3),
            "rl_best_reward": _prom_result_with_label("sku", "SKU_A", 12000.0),
            "rl_vs_oracle_pct": _prom_result_with_label("sku", "SKU_A", 91.5),
            "p99_latency_ms": _prom_result(120.0),
        }
        if overrides:
            defaults.update(overrides)
        return defaults

    @patch("services.monitoring_agent.requests.get")
    def test_healthy_metrics(self, mock_get):
        from services.monitoring_agent import fetch_prometheus_metrics, _PROM_QUERIES

        responses = self._make_prom_responses()
        query_keys = list(_PROM_QUERIES.keys())

        call_count = 0

        def side_effect(url, params, timeout):
            nonlocal call_count
            key = query_keys[call_count % len(query_keys)]
            call_count += 1
            m = MagicMock()
            m.json.return_value = {"data": {"result": responses[key]}}
            m.raise_for_status.return_value = None
            return m

        mock_get.side_effect = side_effect

        metrics = fetch_prometheus_metrics("http://prometheus:9090")

        assert metrics["cpu_pct"] == 45.0
        assert metrics["ram_pct"] == 60.0
        assert metrics["queue_depth"] == 5
        assert metrics["rl_jobs_success_total"] == 100
        assert metrics["rl_jobs_failure_total"] == 2
        assert metrics["rl_failure_rate_pct"] == pytest.approx(1.96, abs=0.1)
        assert "SKU_A" in metrics["rl_best_reward_by_sku"]
        assert metrics["rl_vs_oracle_pct_by_sku"]["SKU_A"] == 91.5
        assert metrics["api_p99_latency_ms"] == 120.0

    @patch("services.monitoring_agent.requests.get")
    def test_prometheus_unreachable_returns_zeros(self, mock_get):
        """If Prometheus is down, metrics should gracefully return zeros, not raise."""
        mock_get.side_effect = Exception("Connection refused")

        from services.monitoring_agent import fetch_prometheus_metrics

        metrics = fetch_prometheus_metrics("http://dead-prometheus:9090")
        # All numeric fields should be zero / empty, not an exception
        assert metrics["cpu_pct"] == 0.0
        assert metrics["ram_pct"] == 0.0
        assert metrics["rl_failure_rate_pct"] == 0.0


# ── generate_health_report ────────────────────────────────────────────────────

class TestGenerateHealthReport:
    def _sample_metrics(self) -> dict:
        return {
            "timestamp": "2026-01-01T08:00:00+00:00",
            "cpu_pct": 45.0,
            "ram_pct": 60.0,
            "queue_depth": 5,
            "rl_jobs_in_flight": 2,
            "rl_jobs_success_total": 100,
            "rl_jobs_failure_total": 2,
            "rl_failure_rate_pct": 1.96,
            "rl_best_reward_by_sku": {"SKU_A": 12000.0},
            "rl_vs_oracle_pct_by_sku": {"SKU_A": 91.5},
            "api_p99_latency_ms": 120.0,
        }

    @patch("services.monitoring_agent.groq.Groq")
    def test_returns_llm_content(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="## 🟢 Green\nAll systems healthy."))]
        )

        from services.monitoring_agent import generate_health_report

        report = generate_health_report(self._sample_metrics(), "fake-key")
        assert "🟢" in report or "Green" in report

    @patch("services.monitoring_agent.groq.Groq")
    def test_groq_receives_metrics_json(self, mock_groq_cls):
        """Confirm metrics are serialised and sent to Groq."""
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="🟢 OK"))]
        )

        from services.monitoring_agent import generate_health_report

        metrics = self._sample_metrics()
        generate_health_report(metrics, "fake-key")

        call_kwargs = mock_client.chat.completions.create.call_args
        user_content = call_kwargs[1]["messages"][-1]["content"]
        assert "cpu_pct" in user_content
        assert "45.0" in user_content


# ── send_email_report ─────────────────────────────────────────────────────────

class TestSendEmailReport:
    @patch("services.monitoring_agent.requests.post")
    def test_posts_to_resend(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "abc123"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        from services.monitoring_agent import send_email_report

        send_email_report(
            report_md="## 🟢 Green\nAll good.",
            resend_api_key="re_test",
            to_emails=["sujaynsv@gmail.com", "rishitsura@gmail.com"],
            from_address="Replenix <noreply@replenix.app>",
        )

        assert mock_post.called
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.resend.com/emails"
        payload = call_args[1]["json"]
        assert "sujaynsv@gmail.com" in payload["to"]
        assert "rishitsura@gmail.com" in payload["to"]
        assert "Replenix Health Report" in payload["subject"]

    @patch("services.monitoring_agent.requests.post")
    def test_red_status_in_subject(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"id": "x"})
        mock_post.return_value.raise_for_status = MagicMock()

        from services.monitoring_agent import send_email_report

        send_email_report(
            report_md="## 🔴 Red\nCPU critical!",
            resend_api_key="re_test",
            to_emails=["sujaynsv@gmail.com"],
            from_address="Replenix <noreply@replenix.app>",
        )

        payload = mock_post.call_args[1]["json"]
        assert "🔴" in payload["subject"]
