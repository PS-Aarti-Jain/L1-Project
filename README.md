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
                             │  - Qdrant Vector DB      │   │  - github_search_code       │
                             │  - HNSW Index / Cosine   │   │  - github_create_issue      │
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
3. **Resilient Vector Database**: A disk-persistent Qdrant vector database store in `database.py`. It operates locally under the `backend/qdrant_db/` directory. It uses HNSW graph indexing for fast semantic vector search, coupled with a custom Hybrid Lexical-Semantic Reranker (combining cosine similarity with TF-IDF keyword overlap). Includes a fallback local word-frequency keyword search if the embedding service is offline.
4. **GitHub MCP Server**: A standalone process in `github_mcp.py` exposing GitHub API tools through the Model Context Protocol (MCP). It runs as a lifecycle-managed stdio subprocess of the orchestrator.

---

## 🔄 End-to-End Execution Workflow

1. **User Query**: User sends a natural language question in the React Chat panel.
2. **Context Enrichment & Query Rewrite**: The orchestrator evaluates context history and generates a self-contained query using the active LLM.
3. **RAG Retrieval**: 
   - The query search string is sent to the local Qdrant vector database.
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
* **Retrieval Recall@5**: Measures if the target documentation chunk is retrieved within the top 5 results (Goal: ≥ 80%).
* **Lexical Groundedness**: Resilient, zero-latency metric checking if expected keywords and technical phrases appear in the generated response (Goal: ≥ 60%).
* **LLM Judge Auditor**: Uses an LLM-as-a-judge prompt to score response faithfulness. Failures are recorded as "Not evaluated" — never substituted with a perfect score.
* **Latency**: Logs response times per query.

See [`evaluation_report.md`](./evaluation_report.md) for a committed run of the evaluation pipeline.

---

## 🛡️ Security Design

* **Least Privilege Scope**: The GitHub Personal Access Token (PAT) used by the MCP server is scoped strictly to a target repository (`contents:read` and `issues:write`).
* **Human-in-the-loop (HI-Loop) Interception**: Destructive write actions are suspended on the backend. No code executes until an explicit user approval click arrives on the `/api/confirm` endpoint.
* **Prompt Injection Defense**: Retrieved documentation content is wrapped inside explicit untrusted tags in the system prompt. The model is strictly instructed that instructions found in retrieved documents must never be followed.
* **Resilient Local Failover (Ollama)**: The LLM orchestrator catches API errors from Gemini and OpenRouter (quota exhaustion, expired keys, DNS dropouts) and redirects to a local Ollama instance when available.
* **Secure MCP Confirmation Tokens**: Pending destructive-action confirmations use cryptographically random, full-length tokens (`secrets.token_urlsafe(32)`). Each pending action is bound to the originating user session and expires after 10 minutes. Edited arguments are revalidated against the tool schema and repository scope at execution time.

> ⚠️ **Demo Authentication Notice**: The default username/password (`admin`/`password123`), JWT secret, and SHA-256 password hashing are for **local development use only**. Tokens are stored in browser local storage. Do not expose this configuration to any public or production network.

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
2. Open `backend/.env` and configure your desired execution mode.

#### Embedding Provider Configuration
Embedding and generation providers are configured separately. By default the system uses the **FastEmbed** local model for embeddings (no API key required). You can override these in `.env`:
```ini
# Embedding settings (independent of LLM generation provider)
EMBEDDING_PROVIDER=fastembed          # Options: fastembed, sentence-transformers, gemini, ollama
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RELEVANCE_THRESHOLD=0.45              # Chunks below this combined score are filtered out
```

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

4. **RAG Quality Evaluation Pipeline**: Measures RAG accuracy, including Retrieval Recall@5, lexical groundedness, and latency over 9 golden test cases (including unanswerable, adversarial, paraphrase-only, and conflicting-source cases). LLM-judge failures are recorded as `Not evaluated` — not substituted with a perfect 1.0. Results are saved to `backend/tests/eval_results.json` and a summary is committed in [`evaluation_report.md`](./evaluation_report.md). This can also be triggered from the React dashboard UI:
   ```bash
   python backend/tests/test_evaluation.py
   ```
