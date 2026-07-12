# Developer Setup for DevAssist

This document provides setup instructions for running the DevAssist application locally.

## Backend Configuration

The FastAPI backend requires Python 3.10+ and a set of environment variables defined in a `.env` file.

### Prerequisites

1. Install Python packages:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file with:
   - `GEMINI_API_KEY`: API key from Google AI Studio.
   - `ANTHROPIC_API_KEY`: API key from Anthropic Console (optional).
   - `GITHUB_PAT`: GitHub Personal Access Token.
   - `GITHUB_REPOSITORY`: Target repository in format `owner/repo` (e.g., `octocat/Hello-World`).

### Running the Orchestrator

Start the FastAPI application with Uvicorn:
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## Frontend Configuration

The frontend is built using React and Vite. It requires Node.js v18+.

### Setup and Running

1. Install Node modules:
   ```bash
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```
The frontend will run on `http://localhost:5173`. It expects the FastAPI backend to be running on `http://localhost:8000`.
