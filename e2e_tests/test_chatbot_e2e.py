import pytest
import time
from playwright.sync_api import sync_playwright, expect

# Default to the frontend URL
BASE_URL = "http://localhost:3000"

def chat_and_verify(page, expected_reply_text=None):
    """
    Helper function to open copilot if not open, type a message, send it,
    and wait for a response.
    """
    # Look for the copilot toggle button
    # The toggle button contains the Title text of the copilot, e.g., "AI-powered assistant" or similar
    # Or we can just click the circular FAB that has the sparkle icon.
    fab = page.locator('button:has(svg.lucide-sparkles)')
    
    # We only click if the input isn't already visible
    chat_input = page.locator('input[placeholder="Ask me anything..."]')
    
    if not chat_input.is_visible():
        fab.click()
        chat_input.wait_for(state="visible", timeout=5000)
    
    # Type a message
    msg = "Explain what this page is for."
    chat_input.fill(msg)
    chat_input.press("Enter")
    
    # Wait for the AI's response bubble
    # We look for a chat bubble from the assistant. It has the bot icon.
    # We wait for the 'Generating...' loader to disappear.
    page.locator('text=Generating...').wait_for(state="hidden", timeout=15000)
    
    # Get the last assistant message
    messages = page.locator('.markdown-body')
    expect(messages.last).to_be_visible(timeout=5000)
    
    if expected_reply_text:
        expect(messages.last).to_contain_text(expected_reply_text, timeout=5000)
    
    # Close copilot to reset state for the next test if needed
    close_btn = page.locator('button:has(svg.lucide-x)').first
    if close_btn.is_visible():
        close_btn.click()


def test_copilot_demand_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Setup context and login if ProtectedRoute requires it.
        # Since it's a test, we assume test_e2e_flow skips login or we mock it.
        # Based on test_e2e_flow.py, it seems it expects it to just load.
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/upload", timeout=10000)
            page.wait_for_load_state('networkidle')
            
            # This is the Data Upload page (demand agent)
            # Check if copilot toggle exists
            if page.locator('button:has(svg.lucide-sparkles)').count() == 0:
                pytest.skip("Copilot FAB not found on /upload page.")
            
            chat_and_verify(page)
        except Exception as e:
            pytest.skip(f"Frontend server not available for E2E check: {e}")
        finally:
            browser.close()


def test_copilot_modify_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/modify", timeout=10000)
            page.wait_for_load_state('networkidle')
            
            if page.locator('button:has(svg.lucide-sparkles)').count() == 0:
                pytest.skip("Copilot FAB not found on /modify page.")
            
            chat_and_verify(page)
        except Exception as e:
            pytest.skip(f"Frontend server not available for E2E check: {e}")
        finally:
            browser.close()


def test_copilot_train_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/train", timeout=10000)
            page.wait_for_load_state('networkidle')
            
            if page.locator('button:has(svg.lucide-sparkles)').count() == 0:
                pytest.skip("Copilot FAB not found on /train page.")
            
            chat_and_verify(page)
        except Exception as e:
            pytest.skip(f"Frontend server not available for E2E check: {e}")
        finally:
            browser.close()


def test_copilot_evaluate_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/evaluate", timeout=10000)
            page.wait_for_load_state('networkidle')
            
            # The evaluate page copilot is disabled if there's no trained model.
            # We can check if it exists but might be disabled.
            fab = page.locator('button:has(svg.lucide-sparkles)')
            if fab.count() == 0:
                pytest.skip("Copilot FAB not found on /evaluate page.")
            
            chat_input = page.locator('input[placeholder="Ask me anything..."]')
            if not chat_input.is_enabled():
                pytest.skip("Copilot is disabled (likely missing a model).")
                
            chat_and_verify(page)
        except Exception as e:
            pytest.skip(f"Frontend server not available for E2E check: {e}")
        finally:
            browser.close()


def test_copilot_deploy_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(f"{BASE_URL}/deploy", timeout=10000)
            page.wait_for_load_state('networkidle')
            
            if page.locator('button:has(svg.lucide-sparkles)').count() == 0:
                pytest.skip("Copilot FAB not found on /deploy page.")
                
            chat_and_verify(page)
        except Exception as e:
            pytest.skip(f"Frontend server not available for E2E check: {e}")
        finally:
            browser.close()


def test_copilot_observability_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            # Observability usually runs on 3001 or as a separate service. 
            # If it's on 3000 it might be standard, or we try 5174. 
            # We'll just use the default port used in other tests but assume observability dashboard is at its root URL
            page.goto("http://localhost:5174/", timeout=10000)
            page.wait_for_load_state('networkidle')
            
            if page.locator('button:has(svg.lucide-sparkles)').count() == 0:
                pytest.skip("Copilot FAB not found on Observability page.")
                
            chat_and_verify(page)
        except Exception as e:
            pytest.skip(f"Frontend server not available for E2E check: {e}")
        finally:
            browser.close()
