import pytest
from services.export_service import generate_excel_report, generate_pdf_report

def test_generate_excel_report_empty():
    metrics = {
        "total_days": 10,
        "cumulative_reward": 150.5,
        "total_revenue": 1000.0,
        "total_cost": 200.0,
        "stockout_days": 1,
        "avg_inventory": 15.2
    }
    history = []
    
    excel_io = generate_excel_report("SKU-123", metrics, history)
    assert excel_io is not None
    excel_io.seek(0)
    data = excel_io.read()
    assert len(data) > 0

def test_generate_excel_report_with_history():
    metrics = {
        "total_days": 1,
        "cumulative_reward": 10.0,
        "total_revenue": 100.0,
        "total_cost": 20.0,
        "stockout_days": 0,
        "avg_inventory": 5.0
    }
    history = [
        {
            "day": 0,
            "date": "2025-01-01",
            "demand": 10,
            "inventory": 5,
            "rl_action": 20,
            "human_action": None,
            "final_action": 20,
            "reward": 10.0,
            "pipeline": [0, 0]
        }
    ]
    
    excel_io = generate_excel_report("SKU-123", metrics, history)
    assert excel_io is not None
    excel_io.seek(0)
    data = excel_io.read()
    assert len(data) > 0

def test_generate_pdf_report():
    metrics = {
        "total_days": 1,
        "cumulative_reward": -5.0,  # Negative to cover negative branch
        "total_revenue": 100.0,
        "total_cost": 20.0,
        "stockout_days": 0,
        "avg_inventory": 5.0
    }
    history = [
        {
            "day": 0,
            "date": "2025-01-01",
            "demand": 10,
            "inventory": 5,
            "rl_action": 20,
            "human_action": 10, # Override branch
            "final_action": 10,
            "reward": -5.0,     # Negative reward branch
            "pipeline": [0, 0]
        },
        {
            "day": 1,
            "date": "2025-01-02",
            "demand": 15,
            "inventory": 0,
            "rl_action": 10,
            "human_action": None,
            "final_action": 10,
            "reward": 5.0,      # Positive reward branch
            "pipeline": [0, 0]
        }
    ]
    
    pdf_io = generate_pdf_report("SKU-123", metrics, history)
    assert pdf_io is not None
    pdf_io.seek(0)
    data = pdf_io.read()
    assert len(data) > 0
    assert data.startswith(b"%PDF")
