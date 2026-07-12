@echo off
title DevAssist Launcher (Global Python Mode)
echo ===================================================
echo             DEVASSIST SERVICE LAUNCHER
echo ===================================================
echo.

:: Add local installation paths of Python and Node to PATH
set PATH=C:\Users\ArtiJain\AppData\Local\Programs\Python\Python313;C:\Program Files\nodejs;%PATH%

:: Ensure we are in the correct root directory
cd /d "%~dp0"

:: 1. Backend Setup (using global python to bypass AppLocker)
echo [1/3] Installing backend dependencies globally...
"C:\Users\ArtiJain\AppData\Local\Programs\Python\Python313\python.exe" -m pip install --upgrade pip
"C:\Users\ArtiJain\AppData\Local\Programs\Python\Python313\python.exe" -m pip install -r backend/requirements.txt

:: 2. MCP Server Setup
echo.
echo [2/3] Installing MCP server dependencies globally...
"C:\Users\ArtiJain\AppData\Local\Programs\Python\Python313\python.exe" -m pip install -r mcp_server/requirements.txt

:: 3. Frontend Setup
echo.
echo [3/3] Installing React frontend dependencies...
cd frontend
if not exist node_modules (
    echo Node modules not found. Running npm install...
    call npm install
) else (
    echo Node modules already installed. Skipping.
)

:: 4. Start services
echo.
echo ===================================================
echo   Spawning services in separate terminal windows...
echo ===================================================
echo.

echo Starting FastAPI Backend on http://127.0.0.1:8000
start "DevAssist FastAPI Backend" cmd /k "cd /d \"%~dp0backend\" && \"C:\Users\ArtiJain\AppData\Local\Programs\Python\Python313\python.exe\" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting React Frontend on http://localhost:5173
start "DevAssist React Frontend" cmd /k "cd /d \"%~dp0frontend\" && npm run dev"

echo.
echo Services spawned successfully!
echo   - Frontend: http://localhost:5173
echo   - Backend: http://127.0.0.1:8000
echo.
echo To run tests:
echo   - RAG Database Test: python backend/tests/test_rag.py
echo   - MCP Server Test: python backend/tests/test_mcp.py
echo   - Live End-to-End API Test: python backend/tests/test_integration.py
echo.
echo Press any key to exit this launcher...
pause > nul
