# LLM Streaming API

A FastAPI service that streams LLM responses token by token using Server-Sent Events (SSE), powered by a locally running Ollama model — built from scratch without LangChain or any LLM framework, to understand exactly how streaming works at the HTTP level.

---

## How It Works

```
POST /chat  →  validate conversation history → call Ollama with stream=true
            →  yield each token as it arrives → stream back to client as SSE

GET /health →  health check
```

---

## Table of Contents

- [Why Streaming?](#why-streaming)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Running Tests](#running-tests)
- [API Endpoints](#api-endpoints)
- [Request & Response Schemas](#request--response-schemas)
- [Example Usage](#example-usage)
- [Docker](#docker)

---

## Why Streaming?

LLMs generate text one token at a time. The full response doesn't exist until generation is completely finished. Without streaming, a client has to wait for the entire response before seeing anything, which feels slow for longer answers.

This API exposes each token to the client the instant it's generated, using **Server-Sent Events (SSE)**, the same mechanism behind the word-by-word text you see on claude.ai and ChatGPT.

---

## Project Structure

```
llm-streaming-api/
├── .github/
│   └── workflows/
│       └── ci.yml                — GitHub Actions CI pipeline
├── app/
│   ├── __init__.py
│   ├── main.py                   — FastAPI app and /chat endpoint
│   ├── schema.py                 — Message, ChatRequest schemas
│   ├── services/
│   │   ├── __init__.py
│   │   └── llm.py                — Streams tokens from Ollama
│   └── test/
│       ├── __init__.py
│       └── test_main.py          — Full test suite
├── .dockerignore
├── .env                          — Environment variables
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pytest.ini
├── README.md
└── requirements.txt
```

---

## Requirements

- Python 3.12+
- [Ollama](https://ollama.com) installed and running locally
- Docker (optional, for containerized runs)

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/HonourJAH/llm-streaming-api.git
cd llm-streaming-api
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Ollama and pull a model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
```

### 5. Make sure Ollama is reachable

By default Ollama only listens on `127.0.0.1`. If you plan to run this API inside Docker, Ollama needs to accept connections from outside its own loopback interface:

```bash
sudo systemctl edit ollama
```

Add:

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 6. Set up environment variables

```
OLLAMA_URL=http://localhost:11434/api/chat
OLLAMA_MODEL=llama3.2
```

### 7. Start the API server

```bash
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`
Interactive docs at `http://localhost:8000/docs`

> **Note:** Swagger UI's "Try it out" does not render streaming responses correctly, it buffers the full response before displaying it. Use `curl -N` or a real HTTP client to observe actual token-by-token streaming.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434/api/chat` | Ollama's chat endpoint |
| `OLLAMA_MODEL` | `llama3.2:latest` | Which pulled Ollama model to use |

---

## Running Tests

All Ollama calls are mocked — no real Ollama instance is required to run the test suite.

```bash
pytest -v
```

Run with coverage:

```bash
pytest -v --cov=app --cov-report=term-missing
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/chat` | Submit conversation history, stream the model's response |
| `GET` | `/health` | Health check |

---

## Request & Response Schemas

### `POST /chat`

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `messages` | `array` | ✅ | Full conversation history, at least 1 message |
| `messages[].role` | `string` | ✅ | Either `user` or `assistant` |
| `messages[].content` | `string` | ✅ | Message text, minimum 1 character |

**Example request:**

```json
{
  "messages": [
    { "role": "user", "content": "My name is Michael" },
    { "role": "assistant", "content": "Nice to meet you, Michael!" },
    { "role": "user", "content": "What's my name?" }
  ]
}
```

**Response:**

A `text/event-stream` response. Each event looks like:

```
data: Your

data:  name

data:  is

data:  Michael

data: [DONE]

```

The client reads these incrementally as they arrive rather than waiting for one complete response. `data: [DONE]` signals the end of the stream.

---

### `GET /health`

```json
{ "status": "healthy" }
```

---

## Example Usage

### Stream a response with curl

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Count from 1 to 10"}]}'
```

The `-N` flag disables curl's output buffering so you can see tokens appear progressively.

### Multi-turn conversation

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "My name is Michael"},
      {"role": "assistant", "content": "Nice to meet you, Michael!"},
      {"role": "user", "content": "What is my name?"}
    ]
  }'
```

### Consuming the stream in Python

```python
import httpx

with httpx.stream(
    "POST",
    "http://localhost:8000/chat",
    json={"messages": [{"role": "user", "content": "Count from 1 to 10"}]},
    timeout=None,
) as response:
    for chunk in response.iter_text():
        print(chunk, end="", flush=True)
```

---

## Docker

Ollama runs on the **host machine**, not inside Docker — it needs direct CPU/GPU access. The API container reaches it via `host.docker.internal`.

### Run with Docker Compose

```bash
docker compose up --build
```

### Build the image only

```bash
docker build -t llm-streaming-api .
```

### Linux-specific note

`host.docker.internal` doesn't resolve automatically on native Linux. This is already handled in `docker-compose.yml` via:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Combined with Ollama listening on `0.0.0.0` (set up in [Getting Started](#getting-started) step 5), the container can reach Ollama running on your host.
