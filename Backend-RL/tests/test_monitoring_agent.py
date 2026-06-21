import json
from unittest.mock import patch, MagicMock
import pytest

from services.monitoring_agent import (
    fetch_all_metrics,
    generate_llm_analysis,
    build_html_report,
    send_email
)


class TestFetchPrometheusMetrics:
    @patch("services.monitoring_agent.requests.get")
    def test_healthy_metrics(self, mock_get):
        # Mock responses
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"result": [{"metric": {"pod": "test-pod"}, "value": [123, "1.0"]}]}
        }
        mock_get.return_value = mock_response

        metrics = fetch_all_metrics("http://fake-prom:9090")
        
        assert "timestamp" in metrics
        assert metrics["namespace"] == "replenix-prod"
        assert metrics["pods"]["running"] >= 0

    @patch("services.monitoring_agent.requests.get")
    def test_prometheus_unreachable_returns_zeros(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        metrics = fetch_all_metrics("http://fake-prom:9090")
        
        # Should return gracefully with zeros/empty lists
        assert metrics["nodes"]["cpu"] == []
        assert metrics["api"]["rps"] == 0.0


class TestGenerateLLMAnalysis:
    @patch("services.monitoring_agent.groq.Groq")
    def test_returns_llm_content(self, mock_groq_cls):
        mock_client = MagicMock()
        mock_groq_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="## Health Status: Green\nAll systems healthy."))]
        )

        dummy_metrics = {
            "namespace": "replenix-prod",
            "timestamp": "2026-06-22",
            "nodes": {"cpu": [], "ram_used_gb": [], "ram_total_gb": [], "disk_pct": []},
            "pods": {"running": 1, "failed": 0, "pending": 0, "running_names": [], "failed_names": [], "pending_names": [], "restarts": []},
            "deployments": {"desired": {}, "available": {}, "unavailable": {}},
            "containers": {"cpu": [], "ram_mb": [], "ram_limit": []},
            "rabbitmq": {"connections": 0, "channels": 0, "consumers": 0, "queue_ready": 0, "queue_unacked": 0, "publish_rate": 0, "deliver_rate": 0},
            "rl": {"jobs_success": 0, "jobs_failure": 0, "jobs_in_flight": 0, "failure_rate_pct": 0, "best_reward_by_sku": [], "vs_oracle_pct_by_sku": []},
            "api": {"rps": 0, "error_rate_pct": 0, "p50_ms": 0, "p99_ms": 0},
            "storage": {"used_gb": [], "capacity_gb": []}
        }

        report = generate_llm_analysis(dummy_metrics, "fake_key")
        assert "Green" in report


class TestBuildHTMLReport:
    def test_html_report_rendering(self):
        dummy_metrics = {
            "namespace": "replenix-prod",
            "timestamp": "2026-06-22",
            "nodes": {"cpu": [], "ram_used_gb": [], "ram_total_gb": [], "disk_pct": []},
            "pods": {"running": 1, "failed": 0, "pending": 0, "running_names": [], "failed_names": [], "pending_names": [], "restarts": []},
            "deployments": {"desired": {}, "available": {}, "unavailable": {}},
            "containers": {"cpu": [], "ram_mb": [], "ram_limit": []},
            "rabbitmq": {"connections": 0, "channels": 0, "consumers": 0, "queue_ready": 0, "queue_unacked": 0, "publish_rate": 0, "deliver_rate": 0},
            "rl": {"jobs_success": 0, "jobs_failure": 0, "jobs_in_flight": 0, "failure_rate_pct": 0, "best_reward_by_sku": [], "vs_oracle_pct_by_sku": []},
            "api": {"rps": 0, "error_rate_pct": 0, "p50_ms": 0, "p99_ms": 0},
            "storage": {"used_gb": [], "capacity_gb": []}
        }
        
        html = build_html_report(dummy_metrics, "## Health Status: Green\nAll good.")
        assert "<html>" in html
        assert "All good." in html


class TestSendEmail:
    @patch("services.monitoring_agent.requests.post")
    def test_posts_to_resend(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "abc123"},
        )
        mock_post.return_value.raise_for_status = MagicMock()

        send_email(
            html_body="<p>Test</p>",
            subject="Test Report",
            resend_api_key="fake_key",
            to_emails=["test@example.com"],
            from_address="noreply@example.com"
        )
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["to"] == ["test@example.com"]
        assert kwargs["json"]["subject"] == "Test Report"
