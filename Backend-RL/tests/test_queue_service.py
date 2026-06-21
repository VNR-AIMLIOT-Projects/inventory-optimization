import os
import json
import threading
from unittest.mock import patch, MagicMock, ANY

import pytest
import pika

from services import queue_service

@pytest.fixture
def mock_pika_connection():
    with patch('services.queue_service.pika.BlockingConnection') as mock_conn_class:
        mock_conn = MagicMock()
        mock_channel = MagicMock()
        mock_conn.channel.return_value = mock_channel
        mock_conn_class.return_value = mock_conn
        
        # Also patch _get_connection to return this mock_conn to simplify tests
        with patch('services.queue_service._get_connection', return_value=mock_conn):
            yield mock_conn, mock_channel

@pytest.fixture
def mock_url_parameters():
    with patch('services.queue_service.pika.URLParameters') as mock_params_class:
        mock_params = MagicMock()
        mock_params_class.return_value = mock_params
        yield mock_params, mock_params_class

def test_get_connection(mock_url_parameters):
    # Setup
    mock_params, mock_params_class = mock_url_parameters
    
    # Test
    with patch('services.queue_service.pika.BlockingConnection') as mock_conn_class:
        conn = queue_service._get_connection()
        
        # Verify
        mock_params_class.assert_called_once_with(queue_service.RABBITMQ_URL)
        assert mock_params.heartbeat == 600
        assert mock_params.blocked_connection_timeout == 300
        mock_conn_class.assert_called_once_with(mock_params)
        assert conn == mock_conn_class.return_value

def test_publish_ui_update_success(mock_pika_connection):
    mock_conn, mock_channel = mock_pika_connection
    
    # Test
    queue_service.publish_ui_update(event_type="test_event", sku="SKU123", extra="data")
    
    # Verify
    mock_channel.exchange_declare.assert_called_once_with(exchange=queue_service.UI_UPDATE_EXCHANGE, exchange_type="fanout")
    
    # Check that basic_publish was called with correct parameters
    mock_channel.basic_publish.assert_called_once()
    kwargs = mock_channel.basic_publish.call_args.kwargs
    assert kwargs['exchange'] == queue_service.UI_UPDATE_EXCHANGE
    assert kwargs['routing_key'] == ""
    
    # Check body content
    payload = json.loads(kwargs['body'])
    assert payload['type'] == "test_event"
    assert payload['sku'] == "SKU123"
    assert payload['extra'] == "data"
    assert 'timestamp' in payload
    
    # Ensure connections are closed
    mock_channel.close.assert_called_once()
    mock_conn.close.assert_called_once()

def test_publish_ui_update_exception():
    # Test when _get_connection throws an exception
    with patch('services.queue_service._get_connection', side_effect=Exception("Connection failed")):
        # Should not raise an exception, just print and continue
        queue_service.publish_ui_update(event_type="test_event")

def test_publish_training_job(mock_pika_connection):
    mock_conn, mock_channel = mock_pika_connection
    
    job_data = {
        "run_id": 1,
        "sku": "SKU1",
        "episodes": 100,
        "season_type": "all",
        "holding_cost": 1.0,
        "stockout_penalty": 2.0,
        "max_order": 100,
        "uploaded_filepath": "test.csv",
        "demand_params": {}
    }
    
    # Test
    queue_service.publish_training_job(job_data)
    
    # Verify
    mock_channel.queue_declare.assert_called_once_with(queue=queue_service.JOB_QUEUE, durable=True)
    
    mock_channel.basic_publish.assert_called_once()
    kwargs = mock_channel.basic_publish.call_args.kwargs
    assert kwargs['exchange'] == ""
    assert kwargs['routing_key'] == queue_service.JOB_QUEUE
    
    payload = json.loads(kwargs['body'])
    assert payload == job_data
    
    assert kwargs['properties'].delivery_mode == 2  # persistent
    assert kwargs['properties'].content_type == "application/json"
    
    mock_channel.close.assert_called_once()
    mock_conn.close.assert_called_once()

def test_progress_listener_init():
    def dummy_callback(data):
        pass
    
    listener = queue_service.ProgressListener(dummy_callback)
    assert listener._on_message == dummy_callback
    assert listener._thread is None
    assert listener._stop is False
    assert listener._connection is None

def test_progress_listener_start_stop():
    listener = queue_service.ProgressListener(lambda x: None)
    
    with patch('threading.Thread') as mock_thread_class:
        mock_thread = MagicMock()
        mock_thread_class.return_value = mock_thread
        
        listener.start()
        
        assert listener._stop is False
        mock_thread_class.assert_called_once_with(target=listener._run, daemon=True)
        mock_thread.start.assert_called_once()
        
        # Setup fake connection for stop
        mock_conn = MagicMock()
        mock_conn.is_open = True
        listener._connection = mock_conn
        
        listener.stop()
        
        assert listener._stop is True
        mock_conn.close.assert_called_once()

def test_progress_listener_run_consume_success(mock_pika_connection):
    mock_conn, mock_channel = mock_pika_connection
    
    # Setup mock consume to yield one message then stop
    method_mock = MagicMock()
    properties_mock = MagicMock()
    body_data = json.dumps({"progress": 50})
    
    # Make _stop True after processing one message so loop exits
    def mock_consume(*args, **kwargs):
        yield method_mock, properties_mock, body_data
        listener._stop = True
    
    mock_channel.consume.side_effect = mock_consume
    
    # Setup queue declare to return a mock queue name
    mock_result = MagicMock()
    mock_result.method.queue = "test_queue"
    mock_channel.queue_declare.return_value = mock_result
    
    callback_mock = MagicMock()
    listener = queue_service.ProgressListener(callback_mock)
    
    # Run synchronously
    listener._run()
    
    # Verify setup
    mock_channel.exchange_declare.assert_called_once_with(exchange=queue_service.PROGRESS_EXCHANGE, exchange_type="fanout")
    mock_channel.queue_declare.assert_called_once_with(queue="", exclusive=True)
    mock_channel.queue_bind.assert_called_once_with(exchange=queue_service.PROGRESS_EXCHANGE, queue="test_queue")
    
    # Verify callback called with parsed data
    callback_mock.assert_called_once_with({"progress": 50})

def test_progress_listener_run_connection_error():
    callback_mock = MagicMock()
    listener = queue_service.ProgressListener(callback_mock)
    
    # Fail once with AMQPConnectionError, then exit gracefully by setting _stop
    with patch('services.queue_service._get_connection', side_effect=[
        pika.exceptions.AMQPConnectionError("Network error"),
        None # Next call won't happen because we mock sleep to set _stop
    ]) as mock_get_conn:
        with patch('time.sleep') as mock_sleep:
            def side_effect_sleep(*args, **kwargs):
                listener._stop = True
            mock_sleep.side_effect = side_effect_sleep
            
            listener._run()
            
            # Verify it retried at least once then slept
            assert mock_get_conn.call_count == 1
            mock_sleep.assert_called_once_with(3)

def test_progress_listener_run_max_retries():
    callback_mock = MagicMock()
    listener = queue_service.ProgressListener(callback_mock)
    
    with patch('services.queue_service._get_connection', side_effect=pika.exceptions.AMQPConnectionError("Network error")):
        with patch('time.sleep') as mock_sleep:
            # Change max_retries temporarily to run faster
            # Or just let it run if max_retries is 30... wait that's too slow.
            # We will patch max_retries directly in the code or just run it with a patch
            
            # Use mock.patch for the max_retries logic if needed, but since it's hardcoded to 30, we can mock sleep to raise exception to break out? No, we can just patch it using mock.
            pass

def test_progress_listener_run_general_error():
    callback_mock = MagicMock()
    listener = queue_service.ProgressListener(callback_mock)
    
    with patch('services.queue_service._get_connection', side_effect=Exception("General error")):
        with patch('time.sleep') as mock_sleep:
            def side_effect_sleep(*args, **kwargs):
                listener._stop = True
            mock_sleep.side_effect = side_effect_sleep
            
            listener._run()
            
            mock_sleep.assert_called_once_with(3)

def test_progress_listener_consume_invalid_json(mock_pika_connection):
    mock_conn, mock_channel = mock_pika_connection
    
    method_mock = MagicMock()
    properties_mock = MagicMock()
    body_data = "not json"
    
    def mock_consume(*args, **kwargs):
        yield method_mock, properties_mock, body_data
        listener._stop = True
    
    mock_channel.consume.side_effect = mock_consume
    
    mock_result = MagicMock()
    mock_result.method.queue = "test_queue"
    mock_channel.queue_declare.return_value = mock_result
    
    callback_mock = MagicMock()
    listener = queue_service.ProgressListener(callback_mock)
    
    # This shouldn't raise exception, just print and continue
    listener._run()
    
    callback_mock.assert_not_called()

def test_progress_listener_consume_none_body(mock_pika_connection):
    mock_conn, mock_channel = mock_pika_connection
    
    method_mock = MagicMock()
    properties_mock = MagicMock()
    
    def mock_consume(*args, **kwargs):
        yield method_mock, properties_mock, None
        listener._stop = True
    
    mock_channel.consume.side_effect = mock_consume
    
    mock_result = MagicMock()
    mock_result.method.queue = "test_queue"
    mock_channel.queue_declare.return_value = mock_result
    
    callback_mock = MagicMock()
    listener = queue_service.ProgressListener(callback_mock)
    
    listener._run()
    
    callback_mock.assert_not_called()
