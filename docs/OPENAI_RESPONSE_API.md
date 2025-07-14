# OpenAI Response API Integration for o3-pro Model Support

This document describes the integration of OpenAI's Response API to support the o3-pro model in Open WebUI.

## Overview

The o3-pro model is OpenAI's latest reasoning model that uses the Response API instead of the traditional Chat Completions API. This integration ensures proper parameter handling and endpoint routing for o3-pro models while maintaining compatibility with existing o-series models (o1-mini, o1-preview).

## Key Features

### Enhanced Parameter Handling

The o3-pro model has specific parameter requirements:

- **`max_tokens` → `max_completion_tokens`**: Automatic conversion for all o-series models
- **`reasoning_effort`**: New parameter specific to o3-pro (values: "low", "medium", "high")
- **Unsupported parameters**: Automatic removal of `temperature`, `top_p`, `frequency_penalty`, `presence_penalty`, `logit_bias`
- **System role conversion**: System messages are converted to "developer" role for o3-pro models

### Response API Endpoint Routing

The integration automatically detects o3-pro models and routes them to the appropriate endpoints:

- **Direct OpenAI**: `https://api.openai.com/v1/responses`
- **Azure OpenAI**: `https://{endpoint}/openai/deployments/{model}/responses?api-version={version}`
- **Other models**: Continue using standard `/chat/completions` endpoint

## Configuration

### Basic Setup

No additional configuration is required beyond standard OpenAI API setup. The integration automatically detects o3-pro models based on the model name.

### Azure OpenAI Configuration

For Azure OpenAI deployments with o3-pro models:

```json
{
  "azure": true,
  "api_version": "2024-02-15-preview"
}
```

### Example Request Payload

```json
{
  "model": "o3-pro",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant that provides detailed explanations."
    },
    {
      "role": "user", 
      "content": "Explain quantum computing"
    }
  ],
  "max_completion_tokens": 1000,
  "reasoning_effort": "high"
}
```

### Automatic Parameter Conversion

The following conversions happen automatically for o3-pro models:

**Input:**
```json
{
  "model": "o3-pro",
  "messages": [{"role": "system", "content": "..."}],
  "max_tokens": 100,
  "temperature": 0.7,
  "top_p": 0.9
}
```

**Output (processed):**
```json
{
  "model": "o3-pro", 
  "messages": [{"role": "developer", "content": "..."}],
  "max_completion_tokens": 100,
  "reasoning_effort": "medium"
}
```

## Model Support Matrix

| Model | Endpoint | System Role | Temperature | Reasoning Effort |
|-------|----------|-------------|-------------|------------------|
| o1-mini | Chat Completions | user | 1.0 only | ❌ |
| o1-preview | Chat Completions | user | 1.0 only | ❌ |
| o3-pro | Response API | developer | ❌ | ✅ |
| o3-mini | Chat Completions | developer | 1.0 only | ❌ |

## Reasoning Effort Parameter

The `reasoning_effort` parameter controls how much computational effort the o3-pro model uses:

- **"low"**: Faster responses, less computational cost
- **"medium"**: Balanced performance (default)
- **"high"**: More thorough reasoning, higher computational cost

## Error Handling

The integration includes robust error handling:

1. **Invalid reasoning_effort values**: Automatically set to "medium"
2. **Missing reasoning_effort**: Automatically set to "medium"
3. **Unsupported parameters**: Automatically removed with debug logging
4. **Endpoint routing**: Automatic fallback to chat completions for non-o3-pro models

## Backward Compatibility

This integration maintains full backward compatibility:

- Existing o1-mini and o1-preview models continue to work unchanged
- Standard models (GPT-4, GPT-3.5, etc.) are unaffected
- All existing API configurations continue to work

## Testing

The integration includes comprehensive tests covering:

- Parameter transformation for o3-pro models
- Reasoning effort validation
- Endpoint routing for different model types
- Azure OpenAI compatibility
- Legacy model compatibility

## Implementation Details

### Key Functions

- `openai_o_series_handler()`: Handles parameter conversion for all o-series models
- `should_use_response_api()`: Determines if a model should use Response API
- `get_chat_completions_endpoint()`: Routes to appropriate API endpoint
- `convert_to_azure_payload()`: Handles Azure-specific transformations

### Code Changes

The implementation required minimal changes to the existing codebase:

1. Enhanced `openai_o_series_handler()` with o3-pro specific logic
2. Added Response API endpoint routing
3. Updated Azure payload conversion
4. Added `reasoning_effort` to allowed parameters

## Security Considerations

- All parameter validation maintains existing security standards
- No new authentication or authorization changes required
- Logging includes debug information for troubleshooting
- Input sanitization follows existing patterns

## Future Enhancements

Potential future improvements include:

- UI controls for reasoning_effort parameter
- Model-specific cost tracking for Response API calls
- Enhanced monitoring and analytics for o3-pro usage
- Support for additional Response API features as they become available