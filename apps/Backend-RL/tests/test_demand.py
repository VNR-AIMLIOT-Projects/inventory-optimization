import pytest
from data_processing.demand import generate_demand, prepare_env_data

def test_generate_demand_summer():
    df = generate_demand(season_type="summer", num_days=365)
    assert len(df) == 365
    assert "Date" in df.columns
    assert "Demand" in df.columns
    # Check that demand isn't entirely 0
    assert df["Demand"].mean() > 0

def test_generate_demand_winter():
    df = generate_demand(season_type="winter", num_days=365)
    assert len(df) == 365
    assert "Date" in df.columns
    assert "Demand" in df.columns
    # Check that demand isn't entirely 0
    assert df["Demand"].mean() > 0

def test_prepare_env_data():
    raw_df = generate_demand(season_type="summer", num_days=365)
    prepared_df = prepare_env_data(raw_df, season_type="summer")
    
    expected_cols = ["date", "demand", "day_of_week", "promo_flag"]
    for col in expected_cols:
        assert col in prepared_df.columns
        
    assert len(prepared_df) == 365
    
    # Check "Professor's Fix"
    assert "promo_flag" in prepared_df.columns
    # 15-19 is festival, promo flag starts 7 days prior (day 8)
    # Check day 10
    assert prepared_df.iloc[10]["promo_flag"] == 1
