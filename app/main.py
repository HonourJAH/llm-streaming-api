from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.schema import ChatRequest
from app.services.llm import stream_chat

app = FastAPI()


@app.post("/chat")
async def chat(request: ChatRequest):
    """Accepts a conversation history and streams the model's
    response back to the client token by token.

    StreamingResponse takes an async generator and sends each
    yielded value to the client as soon as it's produced — instead
    of waiting for the generator to finish and sending one big response.
    """
    # Convert Pydantic Message objects into plain dicts
    # Ollama expects [{"role": "...", "content": "..."}]
    messages = [m.model_dump() for m in request.messages]

    return StreamingResponse(
        stream_chat(messages),
        media_type="text/event-stream",
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
