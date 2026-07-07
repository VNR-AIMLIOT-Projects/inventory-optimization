import os
import io
from unittest.mock import patch, MagicMock

import pytest

# We need to set STORAGE_DIR before importing storage_service
os.environ["STORAGE_DIR"] = "/tmp/test_storage"

from services import storage_service

def test_storage_dirs_created():
    # Make sure the variables match our mock environ
    assert storage_service.STORAGE_DIR is not None
    assert storage_service.UPLOADS_DIR == os.path.join(storage_service.STORAGE_DIR, "uploads")
    assert storage_service.MODELS_DIR == os.path.join(storage_service.STORAGE_DIR, "models")
    assert storage_service.LOGS_DIR == os.path.join(storage_service.STORAGE_DIR, "logs")

def test_save_upload():
    with patch("builtins.open") as mock_open:
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        filepath = storage_service.save_upload("test.csv", b"test content")
        
        assert filepath == os.path.join(storage_service.UPLOADS_DIR, "test.csv")
        mock_open.assert_called_once_with(filepath, "wb")
        mock_file.write.assert_called_once_with(b"test content")

def test_save_model():
    with patch("torch.save") as mock_save:
        mock_agent = MagicMock()
        mock_agent.policy_net.state_dict.return_value = {"weight": "mock"}
        
        with patch("services.storage_service.datetime") as mock_datetime:
            mock_now = MagicMock()
            mock_now.strftime.return_value = "20230101_120000"
            mock_datetime.utcnow.return_value = mock_now
            
            filepath = storage_service.save_model(mock_agent, "SKU1", 10)
            
            expected_filename = "run_10_SKU1_20230101_120000.pt"
            expected_filepath = os.path.join(storage_service.MODELS_DIR, expected_filename)
            
            assert filepath == expected_filepath
            mock_save.assert_called_once_with({"weight": "mock"}, expected_filepath)

def test_load_model_weights():
    with patch("torch.load") as mock_load:
        mock_load.return_value = {"weight": "mock"}
        
        weights = storage_service.load_model_weights("path/to/model.pt")
        
        assert weights == {"weight": "mock"}
        mock_load.assert_called_once_with("path/to/model.pt", map_location="cpu", weights_only=True)

def test_save_eval_graph():
    mock_fig = MagicMock()
    
    with patch("services.storage_service.datetime") as mock_datetime:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20230101_120000"
        mock_datetime.utcnow.return_value = mock_now
        
        filepath = storage_service.save_eval_graph(mock_fig, "SKU1", 10)
        
        expected_filename = "eval_run_10_SKU1_20230101_120000.png"
        expected_filepath = os.path.join(storage_service.LOGS_DIR, expected_filename)
        
        assert filepath == expected_filepath
        mock_fig.savefig.assert_called_once_with(expected_filepath, format="png", bbox_inches="tight", dpi=120)

def test_get_upload_path():
    path = storage_service.get_upload_path("test.csv")
    assert path == os.path.join(storage_service.UPLOADS_DIR, "test.csv")
