import sys
import os
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from datetime import datetime

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.api.app import app
from src.core.database import get_app_db
from src.core.models import User, ChatSession, Project
from src.core.security_auth import get_current_active_user
from src.core.config import settings

# Mock User
MOCK_USER = User(
    id=1,
    username="testuser",
    email="test@example.com",
    hashed_password="hash",
    is_active=True,
    role="user"
)

# Mock Dependency
def mock_get_current_active_user():
    return MOCK_USER

app.dependency_overrides[get_current_active_user] = mock_get_current_active_user

client = TestClient(app)

def test_session_flow():
    # 1. Create a Project (if not exists)
    # We might need to mock DB or ensure project exists.
    # For simplicity, let's assume project_id=1 exists or create it via direct DB access if possible.
    # Since we are using the real app DB, let's just try project_id=1.
    
    project_id = 1
    
    # 2. Create Session 1 via POST /chat
    print(f"\n[Test] Creating Session 1...")
    response = client.post("/api/chat", json={
        "message": "My name is Momo.",
        "project_id": project_id,
        "command": "start"
    })
    if response.status_code != 200:
        print(f"Error: {response.status_code} - {response.text}")
    assert response.status_code == 200
    
    # Extract thread_id from response headers or we can't easily?
    # StreamingResponse doesn't return body immediately.
    # But wait, the API generates thread_id if not provided.
    # To test properly, let's PROVIDE a thread_id.
    session1_id = "session-test-1"
    response = client.post("/api/chat", json={
        "message": "My name is Momo.",
        "project_id": project_id,
        "thread_id": session1_id,
        "command": "start"
    })
    assert response.status_code == 200
    # Consume stream to ensure processing happens
    for line in response.iter_lines():
        pass
        
    # 3. Create Session 2
    print("[Test] Creating Session 2...")
    session2_id = "session-test-2"
    response = client.post("/api/chat", json={
        "message": "What is my name?",
        "project_id": project_id,
        "thread_id": session2_id,
        "command": "start"
    })
    assert response.status_code == 200
    for line in response.iter_lines():
        pass

    # 4. List Sessions
    print("[Test] Listing Sessions...")
    response = client.post("/api/chat/sessions/list", json={"project_id": project_id})
    assert response.status_code == 200
    sessions = response.json()
    print(f"Found {len(sessions)} sessions")
    
    # Verify our sessions are there
    session_ids = [s["id"] for s in sessions]
    assert session1_id in session_ids
    assert session2_id in session_ids
    
    # Verify titles (should be auto-generated)
    s1 = next(s for s in sessions if s["id"] == session1_id)
    assert s1["title"] == "My name is Momo."
    
    # 5. Get History
    print("[Test] Getting History for Session 1...")
    response = client.post("/api/chat/sessions/history", json={"session_id": session1_id})
    assert response.status_code == 200
    history = response.json()
    # Should contain "My name is Momo."
    assert any("My name is Momo" in msg["content"] for msg in history)
    
    # 6. Update Title
    print("[Test] Updating Title...")
    new_title = "Identity Session"
    response = client.post("/api/chat/sessions/update", json={"session_id": session1_id, "title": new_title})
    assert response.status_code == 200
    assert response.json()["title"] == new_title
    
    # Verify update in list
    response = client.post("/api/chat/sessions/list", json={"project_id": project_id})
    sessions = response.json()
    s1 = next(s for s in sessions if s["id"] == session1_id)
    assert s1["title"] == new_title
    
    # 7. Delete Session
    print("[Test] Deleting Session 2...")
    response = client.post("/api/chat/sessions/delete", json={"session_id": session2_id})
    assert response.status_code == 200
    
    # Verify delete in list
    response = client.post("/api/chat/sessions/list", json={"project_id": project_id})
    sessions = response.json()
    session_ids = [s["id"] for s in sessions]
    assert session2_id not in session_ids # Should be gone (soft deleted)

    print("\n[Success] All session tests passed!")

if __name__ == "__main__":
    try:
        test_session_flow()
    except Exception as e:
        print(f"\n[Error] Test failed: {e}")
        import traceback
        traceback.print_exc()
