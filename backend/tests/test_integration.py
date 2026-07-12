import sys
import requests
from pathlib import Path

BACKEND_URL = "http://127.0.0.1:8000"

def run_integration_test():
    print("=== RUNNING API INTEGRATION TEST ===")
    print(f"Target server URL: {BACKEND_URL}")
    
    # 1. Test Login
    print("Attempting to log in as admin...")
    login_url = f"{BACKEND_URL}/api/auth/login"
    payload = {
        "username": "admin",
        "password": "password123"
    }
    try:
        response = requests.post(login_url, data=payload)
        if response.status_code != 200:
            print(f"[FAIL] Login failed. Status: {response.status_code}. Response: {response.text}")
            print("Make sure the FastAPI server is running (run 'uvicorn app.main:app' in backend directory).")
            sys.exit(1)
            
        token_data = response.json()
        token = token_data.get("access_token")
        print("[SUCCESS] Logged in successfully. Token received.")
        
    except requests.exceptions.ConnectionError:
        print(f"[FAIL] Could not connect to the server at {BACKEND_URL}.")
        print("Please ensure the FastAPI server is running with 'uvicorn app.main:app' and port 8000 is open.")
        sys.exit(1)

    headers = {
        "Authorization": f"Bearer {token}"
    }

    # 2. Test status endpoint
    print("\nFetching system status...")
    status_url = f"{BACKEND_URL}/api/status"
    res_status = requests.get(status_url, headers=headers)
    assert res_status.status_code == 200, f"Status failed: {res_status.text}"
    status_data = res_status.json()
    
    print("[SUCCESS] Status details:")
    print(f" - LLM Provider: {status_data.get('llm_provider')}")
    print(f" - Vector Store Total Chunks: {status_data.get('vector_store', {}).get('total_chunks')}")
    print(f" - MCP Active: {status_data.get('mcp_server', {}).get('active')}")
    print(f" - Exposed tools: {status_data.get('mcp_server', {}).get('tools')}")

    # 3. Test ingestion endpoint
    print("\nTriggering manual ingestion...")
    ingest_url = f"{BACKEND_URL}/api/ingest"
    res_ingest = requests.post(ingest_url, headers=headers)
    assert res_ingest.status_code == 200, f"Ingestion failed: {res_ingest.text}"
    ingest_data = res_ingest.json()
    print(f"[SUCCESS] Ingest complete: Indexed {ingest_data.get('files_indexed')} files.")

    # 4. Test Chat endpoint (Streaming)
    print("\nTesting chat prompt endpoint (streaming response)...")
    chat_url = f"{BACKEND_URL}/api/chat"
    chat_payload = {
        "message": "Verify the developer setup steps.",
        "history": []
    }
    
    # We read line-by-line streaming responses
    res_chat = requests.post(chat_url, headers=headers, json=chat_payload, stream=True)
    assert res_chat.status_code == 200, f"Chat endpoint failed: {res_chat.text}"
    
    print("Streaming events:")
    for line in res_chat.iter_lines():
        if line:
            import json
            event = json.loads(line.decode('utf-8'))
            evt_type = event.get("type")
            if evt_type == "token":
                sys.stdout.write(event.get("token", ""))
                sys.stdout.flush()
            elif evt_type == "trace":
                print(f"\n[Trace] {event.get('stage')}: {event.get('details')}")
            elif evt_type == "requires_confirmation":
                print(f"\n[HI-LOOP CONFIRMATION INTERCEPTED]")
                print(f" - ID: {event.get('confirmation_id')}")
                print(f" - Tool: {event.get('tool_name')}")
                print(f" - Args: {event.get('arguments')}")
            elif evt_type == "retrieved_chunks":
                print(f"\n[RAG Chunk cached: {len(event.get('chunks', []))} entries]")

    print("\n\n[SUCCESS] Integration Test Complete. All endpoints working correctly!")

if __name__ == "__main__":
    run_integration_test()
