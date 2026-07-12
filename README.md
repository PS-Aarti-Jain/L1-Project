# DevAssist — RAG + MCP Engineering Knowledge Assistant

DevAssist is an engineering documentation assistant powered by Retrieval-Augmented Generation (RAG) and integrated with the Model Context Protocol (MCP). It enables grounded repository search and direct GitHub operations (such as code searches, issue creation, and PR commenting) with a secure human-in-the-loop validation flow.

This project is built from scratch as a single, coherent application demonstrating two of the most critical skills in AI engineering: **grounding (RAG)** and **tool orchestration (MCP)**.

---

## 🏗️ Architecture Overview

```
                          ┌────────────────────────────────────────────────────────────────┐
                          │                         Frontend (React)                       │
                          │   Chat UI · Citation panel · Tool-call timeline · Confirm modal│
                          │   📊 LIVE RAG QUALITY TELEMETRY MONITOR PANEL                 │
                          └───────────────────────────┬──────────────────────────────────┘
                                                      │ HTTPS / Event Stream (SSE)
                          ┌───────────────────────────▼──────────────────────────────────┐
                          │                    FastAPI Orchestrator Service                 │
                          │  - Auth (JWT/session, Pure hashlib SHA-256)                    │
                          │  - Bounded rate limit auto-retry with exponential backoff       │
                          │  - Conversation state & query rewriting manager                 │
                          │  - LLM client router (Gemini, OpenRouter, or Ollama)            │
                          │  - Routes tool calls → RAG tool OR MCP tool                     │
                          │  - Intercepts destructive actions for UI validation             │
                          │  - 🛡️ INSTANT OLLAMA FAILOVER CONTROLLER                       │
                          └──────────────┬───────────────────────────┬──────────────────┘
                                         │                           │
                             ┌───────────▼────────────┐   ┌──────────▼─────────────────┐
                             │   RAG Subsystem          │   │  MCP Client → MCP Server    │
                             │  - Pure Python DB        │   │  - github_search_code       │
                             │  - Flat index / Cosine   │   │  - github_create_issue      │
                             │  - Keyword fallback      │   │  - github_comment_pr        │
                             │  - Markdown & PDF parser │   │  - Stdio transport link     │
                             └──────────────────────────┘   └──────────────┬─────────────┘
                                                                           │
                                                                  ┌────────▼────────┐
                                                                  │   GitHub REST    │
                                                                  │   API            │
                                                                  └──────────────────┘
```

### Component Details
1. **Frontend (React)**: A single-page dashboard built with Vite, styled with a premium dark cyber aesthetic using Vanilla CSS. Includes a real-time message stream, interactive document citation sidebar, execution timeline tracker, action confirmation prompt, and a **RAG Quality Metrics monitor**.
2. **FastAPI Orchestrator**: The backend server which manages JWT sessions, parses chat request threads, triggers query rewrites, retrieves local documentation context (RAG), and routes actions to a standalone GitHub MCP server process.
3. **Resilient Vector Database**: A pure-Python vector and keyword store in `database.py`. It operates locally on a JSON-file database (`backend/chroma_db/document_store.json`). It calculates cosine similarity using Gemini embeddings if online, and automatically falls back to a custom word-frequency relevance check if offline, avoiding native compiled C++/Rust binding failures (ChromaDB dll blocks) on Windows hosts.
4. **GitHub MCP Server**: A standalone process in `github_mcp.py` exposing GitHub API tools through the Model Context Protocol (MCP). It runs as a lifecycle-managed stdio subprocess of the orchestrator.

---

## 🔄 End-to-End Execution Workflow

1. **User Query**: User sends a natural language question in the React Chat panel.
2. **Context Enrichment & Query Rewrite**: The orchestrator evaluates context history and generates a self-contained query using the active LLM.
3. **RAG Retrieval**: 
   - The query search string is sent to the local `document_store.json`.
   - The DB computes similarity matches and returns matching chunks.
   - Grounded context is formatted and appended to the LLM system prompt.
4. **Model Execution**:
   - The LLM receives the system prompt, history, and active document context.
   - If the LLM requests a read tool (`retrieve_docs` or `github_search_code`), the orchestrator runs it immediately and appends the result to the conversation.
   - If the LLM requests a destructive write tool (`github_create_issue` or `github_comment_pr`), the orchestrator suspends the thread, generates a confirmation session ID, and sends a validation prompt to the frontend.
5. **Human-in-the-loop Validation**: The React interface intercepts this flag and pops up an editable confirmation modal. The user reviews, clicks **Approve**, and the backend executes the API action via the GitHub MCP server.
6. **Streaming SSE Response**: Tokens, trace timelines, and document citations stream back to the UI in real-time.

---

## 📊 RAG Quality & Performance Telemetry

DevAssist features a built-in automated **Quality Audit Pipeline** to measure retrieval accuracy and factual alignment. Results are logged to the file system and displayed in real-time in the React dashboard's control panel.

### Monitored Metrics:
* **Retrieval Recall@3**: Measures if the target documentation chunk is retrieved within the top 3 results (Target $\ge 80\%$).
* **Lexical Groundedness**: Resilient, zero-latency metric checking if expected keywords and technical phrases appear in the generated response (Target $\ge 60\%$).
* **LLM Judge Auditor**: Uses an LLM-as-a-judge prompt to score response faithfulness.
* **Latency**: Logs response times, tracking performance speedups.

---

## 🛡️ Security Design

* **Least Privilege Scope**: The GitHub Personal Access Token (PAT) used by the MCP server is scoped strictly to a target repository (`contents:read` and `issues:write`).
* **Human-in-the-loop (HI-Loop) Interception**: Destructive write actions are suspended on the backend. No code executes until an explicit user approval click arrives on the `/api/confirm` endpoint.
* **Prompt Injection Defense**: Retrieved documentation content is wrapped inside explicit untrusted tags in the system prompt. The model is strictly instructed that instructions found in retrieved documents must never be followed.
* **Bulletproof Local Failover (Ollama)**: Configured the LLM orchestrator to catch all API errors (including quota exhaustion, expired keys, payment credit errors, and DNS dropouts) from *both* Gemini and OpenRouter. The orchestrator now instantly redirects the session to the local Ollama instance (`llama3.1:8b`) with a visual trace notification, ensuring the developer experience is never blocked.

---

## 🚀 Quick Start Setup

### Prerequisites
- **Python 3.10+** (Python 3.13 is fully tested and supported)
- **Node.js v18+**
- **Ollama** installed locally (for running in free offline mode or fallback failover)

---

### Run Modes & Configuration

1. Copy the environment configuration template:
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Open the [backend/.env](file:///c:/RAG-Project/backend/.env) file to configure your desired execution mode.

#### Mode A: 100% Free Local Execution (Ollama)
No API keys or cloud accounts needed.
1. Download and install Ollama from [ollama.com/download](https://ollama.com/download).
2. Open a terminal and pull the Llama 3.1 8B model:
   ```bash
   ollama pull llama3.1:8b
   ```
3. Set your `.env` settings:
   ```ini
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=llama3.1:8b
   ```

#### Mode B: Cloud Execution (Google Gemini)
1. Obtain an API key from [Google AI Studio](https://aistudio.google.com/).
2. Set your `.env` settings:
     ```ini
     LLM_PROVIDER=gemini
     GEMINI_API_KEY=your_gemini_api_key
     DEFAULT_GEMINI_MODEL=gemini-2.0-flash-lite
     ```

#### Mode C: Cloud Execution (OpenRouter)
1. Obtain an API key from [OpenRouter](https://openrouter.ai/).
2. Set your `.env` settings:
     ```ini
     LLM_PROVIDER=openrouter
     OPENROUTER_API_KEY=your_openrouter_api_key
     OPENROUTER_MODEL=google/gemini-2.5-flash
     ```

---

### Running the Application

Simply double-click the master launcher script in the root directory:
```bash
run.bat
```
This script will:
1. Install necessary global python modules (`fastapi`, `uvicorn`, `openai`, `google-genai`).
2. Run Vite frontend package installations (`npm install`).
3. Start the FastAPI server on `http://127.0.0.1:8000`.
4. Start the React development frontend on `http://localhost:5173`.

Log into the frontend dashboard:
- **Username**: `admin`
- **Password**: `password123`

---

## 🧪 Testing & Verification

We provide four verification scripts in `backend/tests/`:

1. **RAG Database Test**: Verifies document chunking, content hashing, database insertions, and semantic queries:
   ```bash
   python backend/tests/test_rag.py
   ```

2. **MCP Server Test**: Launches the GitHub MCP server, initializes a stdio transport client, and validates exposed tool schemas:
   ```bash
   python backend/tests/test_mcp.py
   ```

3. **Live API Integration Test**: Verifies active FastAPI server endpoints (Auth login, Status health-checks, Manual Ingestion, and Streaming Chat responses):
   ```bash
   python backend/tests/test_integration.py
   ```

4. **RAG Quality Evaluation Pipeline**: Measures RAG accuracy, including Retrieval Recall@3, response faithfulness (Groundedness via LLM-as-a-judge), and latency over a golden test dataset. This can also be triggered directly from the React dashboard UI:
   ```bash
   python backend/tests/test_evaluation.py
   ```
