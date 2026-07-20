import json
import logging
from contextlib import asynccontextmanager
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, status, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from .config import settings
from .auth import create_access_token, get_current_user, verify_password, MOCK_USERS
from .database import get_vector_store
from .ingestion import ingest_directory
from .mcp_client import get_mcp_client
from .llm import LLMOrchestrator
from pathlib import Path
import os

# Thread safety lock for running RAG evaluations in background
is_evaluating = False

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("devassist-main")

# Global variables
orchestrator = None
# In-memory dictionary to store pending actions requiring confirmation
# Schema: { confirmation_id: { "tool_name": str, "arguments": dict, "history": List[dict] } }
pending_confirms: Dict[str, Dict[str, Any]] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown lifecycles of backend services."""
    global orchestrator
    logger.info("Initializing DevAssist Backend Services...")
    
    # 1. Initialize vector store connection
    get_vector_store()
    
    # 2. Run initial document ingestion to seed vector DB
    try:
        logger.info("Running initial document ingestion...")
        ingest_result = ingest_directory()
        logger.info(f"Initial ingestion complete: {ingest_result}")
    except Exception as e:
        logger.error(f"Failed to run initial document ingestion: {str(e)}")
        
    # 3. Start GitHub MCP Server subprocess and Client Session
    try:
        mcp_client = get_mcp_client()
        await mcp_client.start()
    except Exception as e:
        logger.error(f"Could not connect to GitHub MCP Server on startup: {str(e)}")
        
    # 4. Initialize LLM Orchestrator
    try:
        orchestrator = LLMOrchestrator()
    except Exception as e:
        logger.error(f"Failed to initialize LLM Orchestrator: {str(e)}")
        
    yield
    
    # Clean up on shutdown
    logger.info("Shutting down DevAssist Backend Services...")
    try:
        mcp_client = get_mcp_client()
        await mcp_client.stop()
    except Exception as e:
        logger.error(f"Error stopping MCP client: {str(e)}")

# Initialize FastAPI
app = FastAPI(
    title="DevAssist Orchestrator Service",
    description="FastAPI gateway managing RAG retrieval, JWT authentication, and GitHub MCP tool routing.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for Vite dev server (usually localhost:5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For demo purposes, allow all; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas
class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str

class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage]

class ConfirmRequest(BaseModel):
    confirmation_id: str
    approved: bool
    edited_arguments: Optional[Dict[str, Any]] = None


# Endpoints

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticates user against mock database and returns JWT token."""
    user = MOCK_USERS.get(form_data.username)
    if not user or not verify_password(form_data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": user["username"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"]
    }

@app.post("/api/ingest")
async def trigger_ingestion(current_user: dict = Depends(get_current_user)):
    """Triggers manual ingestion of docs directory."""
    logger.info(f"User {current_user['username']} triggered manual document ingestion.")
    try:
        result = ingest_directory()
        return result
    except Exception as e:
        logger.error(f"Manual ingestion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {str(e)}"
        )

@app.post("/api/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Accepts conversation messages, queries the database, executes the RAG LLM loop,
    and returns a stream of tokens, trace steps, and action confirmation prompts.
    """
    if orchestrator is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM Orchestrator is not initialized or configured incorrectly."
        )

    # 1. Format incoming history to internal dict format
    history_dicts = []
    for msg in request.history:
        history_dicts.append(msg.model_dump(exclude_none=True))
        
    # 2. Append the new user message
    user_query = request.message
    history_dicts.append({"role": "user", "content": user_query})

    async def event_generator():
        # Step A: Perform query rewriting if history exists to optimize search
        nonlocal user_query
        just_chat_history = [m for m in history_dicts[:-1] if m["role"] in ["user", "assistant"]]
        if len(just_chat_history) > 0:
            yield json.dumps({"type": "trace", "stage": "Query Rewriting", "details": "Analyzing context to refine query..."}) + "\n"
            rewritten = await orchestrator.rewrite_query(user_query, history_dicts[:-1])
            if rewritten != user_query:
                # Update the RAG query term
                user_query = rewritten
                yield json.dumps({"type": "trace", "stage": "Query Rewriting", "details": f"Refined search query: '{rewritten}'"}) + "\n"

        # Step B: Run the agent conversation turn
        async for event in orchestrator.execute_chat_turn(history_dicts, pending_confirms, username=current_user["username"]):
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/confirm")
async def confirm_action(request: ConfirmRequest, current_user: dict = Depends(get_current_user)):
    """
    Confirms or cancels a pending destructive action (e.g. creating an issue).
    If approved, executes the tool on the MCP server and continues conversation.
    """
    import time
    conf_id = request.confirmation_id
    if conf_id not in pending_confirms:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Confirmation session '{conf_id}' not found or already completed."
        )
        
    pending = pending_confirms[conf_id]
    
    # 1. Bind pending actions to user/session
    if pending.get("username") != current_user["username"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to confirm this action."
        )
        
    # 2. Expire pending actions (e.g., after 10 minutes)
    if time.time() - pending.get("created_at", 0) > 600:
        pending_confirms.pop(conf_id)
        raise HTTPException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            detail="Confirmation session has expired."
        )
        
    pending_confirms.pop(conf_id)
    tool_name = pending["tool_name"]
    arguments = request.edited_arguments or pending["arguments"]
    history = pending["history"]  # retrieves history up to the interception
    
    # 3. Revalidate repository scope and edited arguments schema at execution time
    repo = arguments.get("repo")
    if repo and repo.lower() != settings.GITHUB_REPOSITORY.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: repository '{repo}' is outside the authorized scope '{settings.GITHUB_REPOSITORY}'."
        )
        
    if tool_name == "github_create_issue":
        if not arguments.get("title") or not isinstance(arguments.get("title"), str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid parameter 'title'")
        if not arguments.get("body") or not isinstance(arguments.get("body"), str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid parameter 'body'")
    elif tool_name == "github_comment_pr":
        try:
            pr_num = int(arguments.get("pr_number"))
            arguments["pr_number"] = pr_num
        except (ValueError, TypeError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid parameter 'pr_number'")
        if not arguments.get("comment") or not isinstance(arguments.get("comment"), str):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing or invalid parameter 'comment'")

    if not request.approved:
        logger.info(f"User rejected action {tool_name} for confirmation ID {conf_id}")
        
        # Add cancellation detail to thread
        async def cancel_generator():
            yield json.dumps({"type": "trace", "stage": "Action Cancelled", "details": f"User cancelled execution of '{tool_name}'."}) + "\n"
            # Add user cancellation to history
            history.append({
                "role": "tool",
                "name": tool_name,
                "content": f"Action cancelled by the user. Do not call this tool again. Inform the user you aborted."
            })
            # Resume conversation
            async for event in orchestrator.execute_chat_turn(history, pending_confirms, username=current_user["username"]):
                yield json.dumps(event) + "\n"
                
        return StreamingResponse(cancel_generator(), media_type="text/event-stream")

    # Sanitize arguments in log output to avoid log exposure details
    sanitized_args = {k: (f"<str len={len(v)}>" if isinstance(v, str) else v) for k, v in arguments.items()}
    logger.info(f"User approved execution of '{tool_name}' with arguments {sanitized_args}")
    
    async def execution_generator():
        yield json.dumps({"type": "trace", "stage": "Tool Execution", "details": f"Executing approved action: {tool_name}"}) + "\n"
        
        try:
            # 1. Execute the tool on the MCP server
            mcp = get_mcp_client()
            result = await mcp.call_tool(tool_name, arguments)
            
            yield json.dumps({"type": "trace", "stage": "Tool Response", "details": f"Action executed successfully."}) + "\n"
            
            # 2. Append tool result to history
            history.append({
                "role": "tool",
                "name": tool_name,
                "content": result
            })
            
            # 3. Resume conversation loop to stream final summary
            async for event in orchestrator.execute_chat_turn(history, pending_confirms, username=current_user["username"]):
                yield json.dumps(event) + "\n"
                
        except Exception as e:
            logger.error(f"Error executing approved MCP tool: {str(e)}")
            yield json.dumps({"type": "error", "error": f"Failed to execute action: {str(e)}"}) + "\n"
            
    return StreamingResponse(execution_generator(), media_type="text/event-stream")

@app.get("/api/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """Returns statistics about the application, vector store, and MCP connections."""
    db = get_vector_store()
    db_stats = db.get_stats()
    
    mcp = get_mcp_client()
    mcp_active = mcp.session is not None
    mcp_tools = mcp.get_cached_tools()
    
    # Read latest evaluation report if it exists
    eval_report = None
    eval_file = Path(__file__).resolve().parent.parent / "tests" / "eval_results.json"
    if eval_file.exists():
        try:
            with open(eval_file, "r", encoding="utf-8") as ef:
                eval_report = json.load(ef)
        except Exception:
            pass
            
    return {
        "status": "healthy",
        "llm_provider": settings.LLM_PROVIDER,
        "vector_store": {
            "total_chunks": db_stats["total_chunks"],
            "collection_name": db_stats["collection_name"],
            "path": settings.CHROMA_DB_DIR
        },
        "mcp_server": {
            "active": mcp_active,
            "tool_count": len(mcp_tools),
            "tools": [t["name"] for t in mcp_tools]
        },
        "pending_confirmations_count": len(pending_confirms),
        "is_evaluating": is_evaluating,
        "latest_evaluation": eval_report
    }

@app.post("/api/evaluation/run")
async def trigger_evaluation(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """Triggers the evaluation pipeline in the background."""
    global is_evaluating
    if is_evaluating:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An evaluation run is already in progress."
        )
        
    def run_eval_thread():
        global is_evaluating
        try:
            from tests.test_evaluation import run_evaluation
            logger.info("Starting background RAG evaluation pipeline run...")
            run_evaluation()
            logger.info("Background RAG evaluation pipeline completed successfully.")
        except Exception as err:
            logger.error(f"Background evaluation task failed: {str(err)}")
        finally:
            is_evaluating = False
            
    is_evaluating = True
    background_tasks.add_task(run_eval_thread)
    return {"status": "started", "message": "RAG Evaluation Pipeline initiated."}

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
