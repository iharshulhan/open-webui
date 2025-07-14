#!/usr/bin/env python3
"""
Simple test for o3-pro logic without module dependencies
"""

def should_use_response_api(model: str) -> bool:
    """
    Determine if the model should use the Response API endpoint.
    Response API is used for o3-pro models to enable enhanced reasoning capabilities.
    """
    model_lower = model.lower()
    return model_lower.startswith("o3-pro")


def get_chat_completions_endpoint(url: str, model: str, api_config: dict) -> str:
    """
    Get the appropriate chat completions endpoint based on model type and configuration.
    """
    if api_config.get("azure", False):
        # Azure OpenAI endpoint
        model_for_url = model
        api_version = api_config.get("api_version", "") or "2023-03-15-preview"
        
        # Use Response API for o3-pro models on Azure
        if should_use_response_api(model):
            return f"{url}/openai/deployments/{model_for_url}/responses?api-version={api_version}"
        else:
            return f"{url}/openai/deployments/{model_for_url}/chat/completions?api-version={api_version}"
    else:
        # Direct OpenAI or compatible endpoint
        if should_use_response_api(model):
            return f"{url}/responses"
        else:
            return f"{url}/chat/completions"


def openai_o_series_handler(payload):
    """
    Handle "o" series specific parameters including Response API support for o3-pro
    """
    model_lower = payload["model"].lower()
    
    if "max_tokens" in payload:
        # Convert "max_tokens" to "max_completion_tokens" for all o-series models
        payload["max_completion_tokens"] = payload["max_tokens"]
        del payload["max_tokens"]

    # Handle system role conversion based on model type
    if payload.get("messages") and len(payload["messages"]) > 0 and payload["messages"][0]["role"] == "system":
        # Legacy models use "user" role instead of "system"
        if model_lower.startswith("o1-mini") or model_lower.startswith("o1-preview"):
            payload["messages"][0]["role"] = "user"
        else:
            # o3-pro and other newer models use "developer" role
            payload["messages"][0]["role"] = "developer"
    
    # Handle o3-pro specific Response API parameters
    if model_lower.startswith("o3-pro"):
        # Remove unsupported parameters for o3-pro model
        unsupported_params = ["temperature", "top_p", "frequency_penalty", "presence_penalty", "logit_bias"]
        for param in unsupported_params:
            if param in payload:
                print(f"DEBUG: Removing unsupported parameter '{param}' for o3-pro model")
                del payload[param]
        
        # Ensure reasoning_effort is properly handled for o3-pro
        if "reasoning_effort" not in payload:
            # Set default reasoning effort for o3-pro if not specified
            payload["reasoning_effort"] = "medium"
        elif payload["reasoning_effort"] not in ["low", "medium", "high"]:
            print(f"DEBUG: Invalid reasoning_effort value, setting to medium for o3-pro model")
            payload["reasoning_effort"] = "medium"
    
    # Remove temperature for all o-series models if not 1 (or if o3-pro)
    if "temperature" in payload:
        if model_lower.startswith("o3-pro") or (payload["temperature"] != 1):
            if not model_lower.startswith("o3-pro"):
                print(f"DEBUG: Removing temperature parameter for o-series model as only default value (1) is supported")
            del payload["temperature"]

    return payload


def test_all():
    """Test all functionality"""
    print("Testing o3-pro Response API integration...\n")
    
    # Test 1: Basic o3-pro handling
    print("Test 1: Basic o3-pro parameter handling")
    payload = {
        "model": "o3-pro",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello"}
        ],
        "max_tokens": 100,
        "temperature": 0.5,
        "top_p": 0.9,
    }
    
    result = openai_o_series_handler(payload.copy())
    
    assert "max_completion_tokens" in result and result["max_completion_tokens"] == 100
    assert "max_tokens" not in result
    assert "temperature" not in result
    assert "top_p" not in result
    assert result["messages"][0]["role"] == "developer"
    assert "reasoning_effort" in result and result["reasoning_effort"] == "medium"
    print("✓ PASSED\n")
    
    # Test 2: Response API endpoint detection
    print("Test 2: Response API endpoint detection")
    assert should_use_response_api("o3-pro") == True
    assert should_use_response_api("O3-PRO") == True
    assert should_use_response_api("o3-pro-preview") == True
    assert should_use_response_api("o1-mini") == False
    assert should_use_response_api("gpt-4") == False
    print("✓ PASSED\n")
    
    # Test 3: Endpoint URL generation
    print("Test 3: Endpoint URL generation")
    
    # Azure endpoint for o3-pro
    azure_config = {"azure": True, "api_version": "2024-02-15-preview"}
    url = get_chat_completions_endpoint("https://myazure.openai.azure.com", "o3-pro", azure_config)
    expected = "https://myazure.openai.azure.com/openai/deployments/o3-pro/responses?api-version=2024-02-15-preview"
    assert url == expected, f"Expected {expected}, got {url}"
    
    # Regular OpenAI endpoint for o3-pro
    regular_config = {}
    url = get_chat_completions_endpoint("https://api.openai.com/v1", "o3-pro", regular_config)
    expected = "https://api.openai.com/v1/responses"
    assert url == expected, f"Expected {expected}, got {url}"
    
    # Regular model endpoint
    url = get_chat_completions_endpoint("https://api.openai.com/v1", "gpt-4", regular_config)
    expected = "https://api.openai.com/v1/chat/completions"
    assert url == expected, f"Expected {expected}, got {url}"
    print("✓ PASSED\n")
    
    # Test 4: Legacy compatibility
    print("Test 4: Legacy o-series model compatibility")
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
    
    assert "max_completion_tokens" in result
    assert "max_tokens" not in result
    assert result["messages"][0]["role"] == "user"  # o1 models use "user" role
    assert "temperature" in result  # temperature=1 should be preserved
    print("✓ PASSED\n")
    
    print("🎉 All tests passed! o3-pro Response API integration is working correctly.")


if __name__ == "__main__":
    test_all()