import json
import asyncio
import logging
from uuid import uuid4
from open_webui.utils.misc import (
    openai_chat_chunk_message_template,
    openai_chat_completion_message_template,
)

log = logging.getLogger(__name__)


# OpenAI Response API Transformation Functions

def _tool(rsp_call: dict) -> dict:
    """Convert RSP tool_call → CCA tool_call."""
    return {
        "id": rsp_call.get("id"),
        "type": "function",
        "function": {
            "name": rsp_call.get("name"),
            "arguments": rsp_call.get("arguments")
        }
    }


def rsp_to_cca(rsp: dict) -> dict:
    """Convert Response object → synthetic Chat‑Completions object"""
    log.debug(f"Converting Response API response to CCA format: {rsp}")
    
    latest = rsp["output"][-1]
    
    # Extract content with better handling of different formats
    content = ""
    if "content" in latest:
        if isinstance(latest["content"], str):
            # Direct string content
            content = latest["content"]
        elif isinstance(latest["content"], list):
            # Array of content parts
            content = "".join(
                p.get("text", "") for p in latest["content"] 
                if isinstance(p, dict) and p.get("type") == "text"
            )
    
    chat_msg = {
        "role": latest["role"],
        "content": content
    }
    
    # Handle tool calls
    if latest.get("type") == "tool_call":
        chat_msg["tool_calls"] = [_tool(latest)]
    
    log.debug(f"Converted message: {chat_msg}")

    return {
        "id": rsp["id"],
        "object": "chat.completion",
        "created": rsp["created_at"],
        "model": rsp["model"],
        "choices": [{
            "index": 0,
            "message": chat_msg,
            "finish_reason": "stop"
        }],
        "usage": rsp.get("usage", {})
    }


def _wrap(x):
    """Wrap delta content for CCA format"""
    return f"data: {json.dumps({'choices': [x]})}\n\n"


async def rsp_sse_to_cca(response_content):
    """Convert Response API SSE events to CCA format"""
    async for line in response_content:
        try:
            line_str = line.decode('utf-8').strip()
            if line_str.startswith('data: '):
                data_part = line_str[6:]  # Remove 'data: ' prefix
                if data_part == '[DONE]':
                    yield "data: [DONE]\n\n"
                    continue
                    
                try:
                    data = json.loads(data_part)
                    
                    # Handle Response API events
                    if 'event' in data:
                        event_type = data['event']
                        if event_type == "response.text.delta":
                            content = data.get('data', {}).get('delta', '')
                            yield f"data: {json.dumps({'choices': [{'delta': {'content': content}}]})}\n\n"
                        elif event_type == "response.tool_call.partial":
                            call_data = data.get('data', {})
                            tool_call = {
                                "id": call_data.get("id"),
                                "type": "function",
                                "function": {
                                    "name": call_data.get("name"),
                                    "arguments": call_data.get("arguments")
                                }
                            }
                            yield f"data: {json.dumps({'choices': [{'delta': {'tool_calls': [tool_call]}}]})}\n\n"
                        elif event_type == "response.done":
                            yield "data: [DONE]\n\n"
                        elif event_type == "response.error":
                            error_data = data.get('data', {})
                            yield f"data: {json.dumps({'error': error_data})}\n\n"
                    else:
                        # Pass through other events as-is
                        yield line_str + "\n"
                except json.JSONDecodeError:
                    # Pass through non-JSON lines as-is
                    yield line_str + "\n"
            else:
                # Pass through non-data lines as-is
                yield line_str + "\n"
        except Exception as e:
            log.error(f"Error processing SSE line: {e}")
            continue


def convert_ollama_tool_call_to_openai(tool_calls: dict) -> dict:
    openai_tool_calls = []
    for tool_call in tool_calls:
        openai_tool_call = {
            "index": tool_call.get("index", 0),
            "id": tool_call.get("id", f"call_{str(uuid4())}"),
            "type": "function",
            "function": {
                "name": tool_call.get("function", {}).get("name", ""),
                "arguments": json.dumps(
                    tool_call.get("function", {}).get("arguments", {})
                ),
            },
        }
        openai_tool_calls.append(openai_tool_call)
    return openai_tool_calls


def convert_ollama_usage_to_openai(data: dict) -> dict:
    return {
        "response_token/s": (
            round(
                (
                    (
                        data.get("eval_count", 0)
                        / ((data.get("eval_duration", 0) / 10_000_000))
                    )
                    * 100
                ),
                2,
            )
            if data.get("eval_duration", 0) > 0
            else "N/A"
        ),
        "prompt_token/s": (
            round(
                (
                    (
                        data.get("prompt_eval_count", 0)
                        / ((data.get("prompt_eval_duration", 0) / 10_000_000))
                    )
                    * 100
                ),
                2,
            )
            if data.get("prompt_eval_duration", 0) > 0
            else "N/A"
        ),
        "total_duration": data.get("total_duration", 0),
        "load_duration": data.get("load_duration", 0),
        "prompt_eval_count": data.get("prompt_eval_count", 0),
        "prompt_tokens": int(
            data.get("prompt_eval_count", 0)
        ),  # This is the OpenAI compatible key
        "prompt_eval_duration": data.get("prompt_eval_duration", 0),
        "eval_count": data.get("eval_count", 0),
        "completion_tokens": int(
            data.get("eval_count", 0)
        ),  # This is the OpenAI compatible key
        "eval_duration": data.get("eval_duration", 0),
        "approximate_total": (lambda s: f"{s // 3600}h{(s % 3600) // 60}m{s % 60}s")(
            (data.get("total_duration", 0) or 0) // 1_000_000_000
        ),
        "total_tokens": int(  # This is the OpenAI compatible key
            data.get("prompt_eval_count", 0) + data.get("eval_count", 0)
        ),
        "completion_tokens_details": {  # This is the OpenAI compatible key
            "reasoning_tokens": 0,
            "accepted_prediction_tokens": 0,
            "rejected_prediction_tokens": 0,
        },
    }


def convert_response_ollama_to_openai(ollama_response: dict) -> dict:
    model = ollama_response.get("model", "ollama")
    message_content = ollama_response.get("message", {}).get("content", "")
    reasoning_content = ollama_response.get("message", {}).get("thinking", None)
    tool_calls = ollama_response.get("message", {}).get("tool_calls", None)
    openai_tool_calls = None

    if tool_calls:
        openai_tool_calls = convert_ollama_tool_call_to_openai(tool_calls)

    data = ollama_response

    usage = convert_ollama_usage_to_openai(data)

    response = openai_chat_completion_message_template(
        model, message_content, reasoning_content, openai_tool_calls, usage
    )
    return response


async def convert_streaming_response_ollama_to_openai(ollama_streaming_response):
    async for data in ollama_streaming_response.body_iterator:
        data = json.loads(data)

        model = data.get("model", "ollama")
        message_content = data.get("message", {}).get("content", None)
        reasoning_content = data.get("message", {}).get("thinking", None)
        tool_calls = data.get("message", {}).get("tool_calls", None)
        openai_tool_calls = None

        if tool_calls:
            openai_tool_calls = convert_ollama_tool_call_to_openai(tool_calls)

        done = data.get("done", False)

        usage = None
        if done:
            usage = convert_ollama_usage_to_openai(data)

        data = openai_chat_chunk_message_template(
            model, message_content, reasoning_content, openai_tool_calls, usage
        )

        line = f"data: {json.dumps(data)}\n\n"
        yield line

    yield "data: [DONE]\n\n"


def convert_embedding_response_ollama_to_openai(response) -> dict:
    """
    Convert the response from Ollama embeddings endpoint to the OpenAI-compatible format.

    Args:
        response (dict): The response from the Ollama API,
            e.g. {"embedding": [...], "model": "..."}
            or {"embeddings": [{"embedding": [...], "index": 0}, ...], "model": "..."}

    Returns:
        dict: Response adapted to OpenAI's embeddings API format.
            e.g. {
                "object": "list",
                "data": [
                    {"object": "embedding", "embedding": [...], "index": 0},
                    ...
                ],
                "model": "...",
            }
    """
    # Ollama batch-style output
    if isinstance(response, dict) and "embeddings" in response:
        openai_data = []
        for i, emb in enumerate(response["embeddings"]):
            openai_data.append(
                {
                    "object": "embedding",
                    "embedding": emb.get("embedding"),
                    "index": emb.get("index", i),
                }
            )
        return {
            "object": "list",
            "data": openai_data,
            "model": response.get("model"),
        }
    # Ollama single output
    elif isinstance(response, dict) and "embedding" in response:
        return {
            "object": "list",
            "data": [
                {
                    "object": "embedding",
                    "embedding": response["embedding"],
                    "index": 0,
                }
            ],
            "model": response.get("model"),
        }
    # Already OpenAI-compatible?
    elif (
        isinstance(response, dict)
        and "data" in response
        and isinstance(response["data"], list)
    ):
        return response

    # Fallback: return as is if unrecognized
    return response
