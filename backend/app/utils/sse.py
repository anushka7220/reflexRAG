# sse.py
#
# Server-Sent Events helper utilities.
# SSE is how the chat endpoint streams tokens to the frontend
# one piece at a time over a persistent HTTP connection.
#
# HOW SSE WORKS:
# The client opens one long-lived HTTP GET/POST connection.
# The server writes lines in this format:
#   data: {"type": "token", "content": "The bug"}
#   data: {"type": "token", "content": " was fixed"}
#   data: {"type": "done", "message_id": "uuid"}
#
# Each line must end with two newlines for the browser's EventSource
# API to recognise it as a complete event.
#
# WHY SSE OVER WEBSOCKETS:
# SSE is one-directional (server to client) and works over plain HTTP.
# For streaming LLM responses, we only need server to client streaming.
# SSE is simpler to implement, debug, and deploy than WebSockets.

import json
from typing import AsyncGenerator


async def token_event(content: str) -> str:
    """Formats a single token as an SSE data line."""
    return f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"


async def citations_event(citations: list) -> str:
    """Formats the citations block as an SSE data line."""
    data = [c.model_dump() if hasattr(c, 'model_dump') else c for c in citations]
    return f"data: {json.dumps({'type': 'citations', 'data': data})}\n\n"


async def staleness_event(flags: list) -> str:
    """Formats staleness flags as an SSE data line."""
    data = [f.model_dump() if hasattr(f, 'model_dump') else f for f in flags]
    return f"data: {json.dumps({'type': 'staleness', 'data': data})}\n\n"


async def done_event(message_id: str, tokens_used: int) -> str:
    """Formats the terminal done event as an SSE data line."""
    return f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'tokens_used': tokens_used})}\n\n"


async def error_event(detail: str) -> str:
    """Formats an error as an SSE data line."""
    return f"data: {json.dumps({'type': 'error', 'detail': detail})}\n\n"


async def stream_rag_response(
    final_answer: str,
    citations: list,
    staleness_flags: list,
    message_id: str,
    tokens_used: int,
) -> AsyncGenerator[str, None]:
    """
    Yields SSE formatted strings for a complete RAG response.

    Streams in this order:
        1. Answer text token by token (word level, not character level)
        2. Citations block as one event
        3. Staleness flags if any exist
        4. Done event with message_id and token count

    Usage in a FastAPI route:
        from sse_starlette.sse import EventSourceResponse
        return EventSourceResponse(
            stream_rag_response(answer, citations, flags, msg_id, tokens)
        )
    """
    # Stream answer word by word so the frontend renders progressively
    words = final_answer.split(" ")
    for i, word in enumerate(words):
        # Add space back except after the last word
        content = word if i == len(words) - 1 else word + " "
        yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"

    # Citations arrive after the full answer text
    if citations:
        data = [c.model_dump() if hasattr(c, 'model_dump') else c for c in citations]
        yield f"data: {json.dumps({'type': 'citations', 'data': data})}\n\n"

    # Staleness flags only if the critic found something
    if staleness_flags:
        data = [f.model_dump() if hasattr(f, 'model_dump') else f for f in staleness_flags]
        yield f"data: {json.dumps({'type': 'staleness', 'data': data})}\n\n"

    # Done event signals the frontend to stop listening
    yield f"data: {json.dumps({'type': 'done', 'message_id': message_id, 'tokens_used': tokens_used})}\n\n"
