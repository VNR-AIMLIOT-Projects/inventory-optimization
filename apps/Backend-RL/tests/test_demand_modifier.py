import pandas as pd
import numpy as np
import pytest

from data_processing.demand_modifier import DemandModifier

@pytest.fixture
def sample_df():
    dates = pd.date_range(start="2023-01-01", periods=10, freq="D")
    demand = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    return pd.DataFrame({"Date": dates, "Demand": demand})

def test_init_and_reset(sample_df):
    modifier = DemandModifier(sample_df)
    assert modifier.current_df.equals(sample_df)
    
    # Modify it
    modifier.current_df.loc[0, 'Demand'] = 999
    assert not modifier.current_df.equals(sample_df)
    
    # Reset
    res = modifier.reset()
    assert res.equals(sample_df)
    assert modifier.current_df.equals(sample_df)

def test_add_spike_exact_date(sample_df):
    modifier = DemandModifier(sample_df)
    res = modifier.add_spike("2023-01-05", 25)
    
    assert res.loc[res['Date'] == "2023-01-05", 'Demand'].iloc[0] == 50 + 25
    # Check that clamp works (if amount is negative and drops below zero)
    res = modifier.add_spike("2023-01-05", -100)
    assert res.loc[res['Date'] == "2023-01-05", 'Demand'].iloc[0] == 0

def test_add_spike_nearest_date(sample_df):
    modifier = DemandModifier(sample_df)
    # The date is not in df but 01-10 is the last date
    res = modifier.add_spike("2023-01-15", 50)
    # The nearest date is 2023-01-10
    assert res.loc[res['Date'] == "2023-01-10", 'Demand'].iloc[0] == 100 + 50

def test_remove_units_exact_date(sample_df):
    modifier = DemandModifier(sample_df)
    res = modifier.remove_units("2023-01-03", 10)
    assert res.loc[res['Date'] == "2023-01-03", 'Demand'].iloc[0] == 30 - 10
    
    # Drops below zero should clamp to 0
    res = modifier.remove_units("2023-01-03", 100)
    assert res.loc[res['Date'] == "2023-01-03", 'Demand'].iloc[0] == 0

def test_remove_units_nearest_date(sample_df):
    modifier = DemandModifier(sample_df)
    # Not in df, closest is 2023-01-01
    res = modifier.remove_units("2022-12-25", 5)
    assert res.loc[res['Date'] == "2023-01-01", 'Demand'].iloc[0] == 10 - 5

def test_set_value(sample_df):
    modifier = DemandModifier(sample_df)
    res = modifier.set_value("2023-01-04", 999)
    assert res.loc[res['Date'] == "2023-01-04", 'Demand'].iloc[0] == 999

def test_set_value_nearest(sample_df):
    modifier = DemandModifier(sample_df)
    res = modifier.set_value("2023-01-12", 999)
    assert res.loc[res['Date'] == "2023-01-10", 'Demand'].iloc[0] == 999

def test_scale(sample_df):
    modifier = DemandModifier(sample_df)
    res = modifier.scale("2023-01-02", "2023-01-04", 1.5)
    assert res.loc[res['Date'] == "2023-01-02", 'Demand'].iloc[0] == 30 # 20 * 1.5
    assert res.loc[res['Date'] == "2023-01-03", 'Demand'].iloc[0] == 45 # 30 * 1.5
    assert res.loc[res['Date'] == "2023-01-04", 'Demand'].iloc[0] == 60 # 40 * 1.5
    assert res.loc[res['Date'] == "2023-01-05", 'Demand'].iloc[0] == 50 # Unchanged
    
    # Verify backward compat alias
    res2 = modifier.scale_period("2023-01-02", "2023-01-04", 2.0)
    assert res2.loc[res2['Date'] == "2023-01-02", 'Demand'].iloc[0] == 60

def test_adjust_range(sample_df):
    modifier = DemandModifier(sample_df)
    res = modifier.adjust_range("2023-01-02", "2023-01-04", 15)
    assert res.loc[res['Date'] == "2023-01-02", 'Demand'].iloc[0] == 20 + 15
    assert res.loc[res['Date'] == "2023-01-03", 'Demand'].iloc[0] == 30 + 15
    assert res.loc[res['Date'] == "2023-01-04", 'Demand'].iloc[0] == 40 + 15
    assert res.loc[res['Date'] == "2023-01-05", 'Demand'].iloc[0] == 50

def test_remove_spike(sample_df):
    modifier = DemandModifier(sample_df)
    modifier.add_spike("2023-01-05", 500) # add huge spike
    
    # now remove it
    res = modifier.remove_spike("2023-01-05")
    # window is 3 days around 01-05, excluding 01-05:
    # 01-02: 20, 01-03: 30, 01-04: 40, (01-05), 01-06: 60, 01-07: 70, 01-08: 80
    # Average of (20,30,40,60,70,80) = 300 / 6 = 50
    assert res.loc[res['Date'] == "2023-01-05", 'Demand'].iloc[0] == 50

    def test_remove_spike_nearest(sample_df):
        modifier = DemandModifier(sample_df)
        # date not in df
        res = modifier.remove_spike("2023-01-15") 
        # Will target the last date (01-10) which is 100
        # window around 01-15 is empty, so it uses the average of the whole series
        # Avg = (10+20+...+100) / 10 = 55
        assert res.loc[res['Date'] == "2023-01-10", 'Demand'].iloc[0] == 55

def test_remove_spike_all_spikes(sample_df):
    # If the window mask is empty (e.g. df only has 1 row)
    small_df = pd.DataFrame({"Date": pd.date_range("2023-01-01", periods=1), "Demand": [100]})
    modifier = DemandModifier(small_df)
    res = modifier.remove_spike("2023-01-01")
    assert res.loc[0, 'Demand'] == 100 # average of the whole series since window is empty

def test_get_data(sample_df):
    modifier = DemandModifier(sample_df)
    modifier.add_spike("2023-01-05", 500)
    df = modifier.get_data()
    
    assert 'is_spike' in df.columns
    assert 'promo_flag' in df.columns
    assert df.loc[df['Date'] == "2023-01-05", 'is_spike'].iloc[0] == 1
    # Check promo flag is 1 for previous 6 days
    assert df.loc[df['Date'] == "2023-01-01", 'promo_flag'].iloc[0] == 1

def test_exceptions_are_caught(sample_df, capsys):
    modifier = DemandModifier(sample_df)
    
    # Pass invalid inputs to trigger exceptions, which are caught and printed
    modifier.add_spike("invalid-date", "invalid-amount")
    captured = capsys.readouterr()
    assert "add_spike error" in captured.out
    
    modifier.remove_units("invalid-date", "invalid-amount")
    captured = capsys.readouterr()
    assert "remove_units error" in captured.out
    
    modifier.set_value("invalid-date", "invalid-amount")
    captured = capsys.readouterr()
    assert "set_value error" in captured.out
    
    modifier.scale("invalid-date", "invalid-date", "invalid-amount")
    captured = capsys.readouterr()
    assert "scale error" in captured.out
    
    modifier.adjust_range("invalid-date", "invalid-date", "invalid-amount")
    captured = capsys.readouterr()
    assert "adjust_range error" in captured.out
    
    modifier.remove_spike("invalid-date")
    captured = capsys.readouterr()
    assert "remove_spike error" in captured.out
