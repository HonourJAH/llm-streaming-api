import httpx
import json
import os
from typing import AsyncGenerator

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")


async def stream_chat(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Call Ollama's /api/chat endpoint with streaming enabled and
    yield each token as it arrives.

    This is an async generator — it uses 'async def' + 'yield' together.
    Each yielded string is one token (or token fragment) from the model,
    produced the moment Ollama sends it, not after the full response
    is complete.

    messages is the full conversation history in the format:
    [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", OLLAMA_URL, json=payload) as response:
            response.raise_for_status()  # Check for HTTP errors

            # aiter_lines() reads the response body line by line as it arrives
            async for line in response.aiter_lines():
                if not line:
                    continue

                chunk = json.loads(line)

                # Each chunk looks like:
                # {"message": {"role": "assistant", "content": "Hello"}, "done": false}
                token = chunk.get("message", {}).get("content", "")

                if token:
                    yield f"data: {token}\n\n"

                if chunk.get("done"):
                    yield "data: [DONE]\n\n"
                    break
