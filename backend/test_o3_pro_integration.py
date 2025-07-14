#!/usr/bin/env python3
"""
Test script for o3-pro Response API integration
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'open_webui'))

from routers.openai import (
    openai_o_series_handler,
    should_use_response_api,
    get_chat_completions_endpoint,
    convert_to_azure_payload
)

def test_o3_pro_handler():
    """Test o3-pro specific parameter handling"""
    print("Testing o3-pro parameter handling...")
    
    # Test basic payload transformation
    payload = {
        "model": "o3-pro",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 100,
        "temperature": 0.5,  # Should be removed for o3-pro
        "top_p": 0.9,  # Should be removed for o3-pro
    }
    
    result = openai_o_series_handler(payload.copy())
    
    # Check that max_tokens was converted
    assert "max_completion_tokens" in result
    assert result["max_completion_tokens"] == 100
    assert "max_tokens" not in result
    
    # Check that temperature was removed
    assert "temperature" not in result
    assert "top_p" not in result
    
    # Check that system role was converted to developer
    assert result["messages"][0]["role"] == "developer"
    
    # Check that reasoning_effort was added with default
    assert "reasoning_effort" in result
    assert result["reasoning_effort"] == "medium"
    
    print("✓ o3-pro parameter handling test passed")

def test_reasoning_effort_handling():
    """Test reasoning_effort parameter validation"""
    print("Testing reasoning_effort parameter validation...")
    
    # Test valid reasoning_effort
    payload = {
        "model": "o3-pro",
        "messages": [{"role": "user", "content": "Hello"}],
        "reasoning_effort": "high"
    }
    
    result = openai_o_series_handler(payload.copy())
    assert result["reasoning_effort"] == "high"
    
    # Test invalid reasoning_effort (should be corrected to medium)
    payload["reasoning_effort"] = "extreme"
    result = openai_o_series_handler(payload.copy())
    assert result["reasoning_effort"] == "medium"
    
    print("✓ reasoning_effort validation test passed")

def test_response_api_detection():
    """Test Response API endpoint detection"""
    print("Testing Response API endpoint detection...")
    
    # Test o3-pro should use Response API
    assert should_use_response_api("o3-pro") == True
    assert should_use_response_api("O3-PRO") == True
    assert should_use_response_api("o3-pro-preview") == True
    
    # Test other models should not use Response API
    assert should_use_response_api("o1-mini") == False
    assert should_use_response_api("gpt-4") == False
    assert should_use_response_api("o3-mini") == False
    
    print("✓ Response API detection test passed")

def test_endpoint_generation():
    """Test endpoint URL generation"""
    print("Testing endpoint URL generation...")
    
    # Test Azure endpoint for o3-pro
    azure_config = {"azure": True, "api_version": "2024-02-15-preview"}
    url = get_chat_completions_endpoint("https://myazure.openai.azure.com", "o3-pro", azure_config)
    expected = "https://myazure.openai.azure.com/openai/deployments/o3-pro/responses?api-version=2024-02-15-preview"
    assert url == expected, f"Expected {expected}, got {url}"
    
    # Test regular OpenAI endpoint for o3-pro
    regular_config = {}
    url = get_chat_completions_endpoint("https://api.openai.com/v1", "o3-pro", regular_config)
    expected = "https://api.openai.com/v1/responses"
    assert url == expected, f"Expected {expected}, got {url}"
    
    # Test regular model endpoint
    url = get_chat_completions_endpoint("https://api.openai.com/v1", "gpt-4", regular_config)
    expected = "https://api.openai.com/v1/chat/completions"
    assert url == expected, f"Expected {expected}, got {url}"
    
    print("✓ Endpoint generation test passed")

def test_azure_payload_conversion():
    """Test Azure payload conversion for o3-pro"""
    print("Testing Azure payload conversion...")
    
    payload = {
        "model": "o3-pro",
        "messages": [{"role": "user", "content": "Hello"}],
        "temperature": 0.7,
        "reasoning_effort": "high",
        "unsupported_param": "value"
    }
    
    url, converted = convert_to_azure_payload("https://myazure.openai.azure.com", payload.copy())
    
    # Check URL transformation
    assert url == "https://myazure.openai.azure.com/openai/deployments/o3-pro"
    
    # Check that temperature was removed for o3-pro
    assert "temperature" not in converted
    
    # Check that reasoning_effort is preserved
    assert "reasoning_effort" in converted
    assert converted["reasoning_effort"] == "high"
    
    # Check that unsupported parameters are filtered out
    assert "unsupported_param" not in converted
    
    print("✓ Azure payload conversion test passed")

def test_legacy_o_series_compatibility():
    """Test that existing o1 models still work correctly"""
    print("Testing legacy o-series model compatibility...")
    
    # Test o1-mini
    payload = {
        "model": "o1-mini",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 100,
        "temperature": 1.0
    }
    
    result = openai_o_series_handler(payload.copy())
    
    # Check max_tokens conversion
    assert "max_completion_tokens" in result
    assert "max_tokens" not in result
    
    # Check system role conversion for legacy models (should be user)
    assert result["messages"][0]["role"] == "user"
    
    # Check temperature handling (should be preserved for o1 if value is 1)
    assert "temperature" in result
    
    print("✓ Legacy o-series compatibility test passed")

def main():
    """Run all tests"""
    print("Running o3-pro Response API integration tests...\n")
    
    try:
        test_o3_pro_handler()
        test_reasoning_effort_handling()
        test_response_api_detection()
        test_endpoint_generation()
        test_azure_payload_conversion()
        test_legacy_o_series_compatibility()
        
        print("\n🎉 All tests passed! o3-pro Response API integration is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)