import os
import tempfile
import pandas as pd
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from data_processing.extracts_demand import (
    detect_demand_parameters,
    regenerate_demand_from_params,
    load_and_process_data,
    plot_demand_preview,
    list_all_skus,
    load_all_skus_data
)

@pytest.fixture
def sample_csv():
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, 'w') as f:
        f.write("Date,SKU,Demand\n")
        f.write("01-01-2023,SKU1,100\n")
        f.write("02-01-2023,SKU1,120\n")
        f.write("03-01-2023,SKU1,110\n")
        f.write("01-01-2023,SKU2,50\n")
        f.write("02-01-2023,SKU2,60\n")
    yield path
    os.remove(path)

@pytest.fixture
def sample_excel():
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    df = pd.DataFrame({
        "Date": ["01-01-2023", "02-01-2023", "03-01-2023"],
        "SKU": ["SKU1", "SKU1", "SKU1"],
        "Demand": [100, 120, 110]
    })
    df.to_excel(path, index=False)
    yield path
    os.remove(path)

@pytest.fixture
def sample_wide_csv():
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, 'w') as f:
        f.write("Date,SKU1,SKU2\n")
        f.write("01-01-2023,100,50\n")
        f.write("02-01-2023,120,60\n")
        f.write("03-01-2023,110,70\n")
    yield path
    os.remove(path)

@pytest.fixture
def demand_df():
    dates = pd.date_range("2023-01-01", periods=100)
    # Baseline ~100
    demand = np.random.normal(100, 10, 100)
    # Add a season
    demand[30:60] += 50
    # Add a festival spike
    demand[80:85] += 100
    
    df = pd.DataFrame({
        "Date": dates,
        "Demand": demand
    })
    return df

def test_detect_demand_parameters(demand_df):
    params = detect_demand_parameters(demand_df)
    
    assert "detected_season_type" in params
    assert "baseline" in params
    assert "seasonal" in params
    assert "festival" in params
    assert "ramp_days" in params
    assert "num_days" in params
    
    assert params["num_days"] == 100
    assert params["baseline"]["start"] > 0
    assert params["seasonal"]["num_seasons"] >= 0
    assert params["festival"]["num_festivals"] >= 0

def test_detect_demand_parameters_summer_winter():
    # Make peak in summer
    dates = pd.date_range("2023-01-01", periods=365)
    demand = np.zeros(365) + 100
    # Add summer peak (June/July)
    summer_start = 150
    summer_end = 210
    demand[summer_start:summer_end] += 200
    
    df_summer = pd.DataFrame({"Date": dates, "Demand": demand})
    params_summer = detect_demand_parameters(df_summer)
    assert params_summer["detected_season_type"] == "summer"
    
    # Make peak in winter
    demand_winter = np.zeros(365) + 100
    # Add winter peak (Nov/Dec)
    winter_start = 300
    winter_end = 360
    demand_winter[winter_start:winter_end] += 200
    
    df_winter = pd.DataFrame({"Date": dates, "Demand": demand_winter})
    params_winter = detect_demand_parameters(df_winter)
    assert params_winter["detected_season_type"] == "winter"

def test_regenerate_demand_from_params(demand_df):
    params = detect_demand_parameters(demand_df)
    
    # Regenerate with identical params
    regen_df = regenerate_demand_from_params(demand_df, params, seed=42)
    
    assert len(regen_df) == len(demand_df)
    assert "Date" in regen_df.columns
    assert "Demand" in regen_df.columns
    assert "is_spike" in regen_df.columns
    assert "is_season" in regen_df.columns
    assert "promo_flag" in regen_df.columns
    assert "season_flag" in regen_df.columns
    
    # Check changing num_days
    params["num_days"] = 110
    regen_ext_df = regenerate_demand_from_params(demand_df, params, seed=42)
    assert len(regen_ext_df) == 110
    
    params["num_days"] = 50
    regen_short_df = regenerate_demand_from_params(demand_df, params, seed=42)
    assert len(regen_short_df) == 50

def test_load_and_process_data_csv(sample_csv):
    df = load_and_process_data(sample_csv, target_sku="SKU1")
    assert len(df) == 3
    assert df["Demand"].iloc[0] == 100
    
    # Auto-select SKU
    df_auto = load_and_process_data(sample_csv)
    assert len(df_auto) > 0

def test_load_and_process_data_excel(sample_excel):
    df = load_and_process_data(sample_excel)
    assert len(df) == 3
    assert df["Demand"].iloc[0] == 100

def test_load_and_process_data_wide_csv(sample_wide_csv):
    df = load_and_process_data(sample_wide_csv, target_sku="SKU1")
    assert len(df) == 3
    assert df["Demand"].iloc[0] == 100
    
    # Auto-select
    df_auto = load_and_process_data(sample_wide_csv)
    assert len(df_auto) == 3

def test_load_and_process_data_exceptions(sample_csv, sample_wide_csv):
    with pytest.raises(ValueError, match="not found"):
        load_and_process_data(sample_csv, target_sku="SKU999")
        
    with pytest.raises(ValueError, match="not found"):
        load_and_process_data(sample_wide_csv, target_sku="SKU999")

def test_plot_demand_preview(demand_df):
    params = detect_demand_parameters(demand_df)
    demand_df.attrs["detected_params"] = params
    
    # Add required flags
    demand_df["is_season"] = 0
    demand_df["is_spike"] = 0
    
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    
    try:
        plot_demand_preview(demand_df, filename=path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        if os.path.exists(path):
            os.remove(path)

def test_list_all_skus(sample_csv, sample_wide_csv):
    skus = list_all_skus(sample_csv)
    assert sorted(skus) == ["SKU1", "SKU2"]
    
    skus_wide = list_all_skus(sample_wide_csv)
    # The columns in wide are Date, SKU1, SKU2, so skus should be SKU1, SKU2
    # Though list_all_skus converts to lower, so it returns ['sku1', 'sku2']
    assert sorted([s.lower() for s in skus_wide]) == ["sku1", "sku2"]

def test_load_all_skus_data(sample_csv):
    res = load_all_skus_data(sample_csv)
    assert "SKU1" in res
    assert "SKU2" in res
    assert len(res["SKU1"]) == 3
    assert len(res["SKU2"]) == 2

