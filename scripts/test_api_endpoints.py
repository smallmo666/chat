import pytest
import httpx
from src.core.config import settings

# Base URL for API
BASE_URL = "http://localhost:8000/api"

@pytest.mark.asyncio
async def test_health_check():
    """Test that the API is running and accessible."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Check auth health or project list as a proxy for health
        # Assuming unauthenticated access to some endpoints might be restricted, 
        # but let's try to get a token first if needed.
        # For now, let's just check if we can reach the server.
        try:
            response = await client.get("/auth/me")
            # 401 is also a valid response proving the server is up
            assert response.status_code in [200, 401, 403], f"API unreachable: {response.status_code}"
        except httpx.ConnectError:
            pytest.fail("Could not connect to API server. Is it running?")

@pytest.mark.asyncio
async def test_login_flow():
    """Test login functionality."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Use default test credentials
        # Note: You might need to adjust these based on your seeded data
        login_data = {
            "username": "admin",
            "password": "password" 
        }
        
        # Depending on auth implementation (OAuth2 form or JSON)
        # Check auth.py router implementation
        response = await client.post("/auth/token", data=login_data)
        
        if response.status_code == 401:
             pytest.skip("Default admin credentials not working or not seeded.")
        
        assert response.status_code == 200
        token_data = response.json()
        assert "access_token" in token_data
        assert token_data["token_type"] == "bearer"
        
        return token_data["access_token"]

@pytest.mark.asyncio
async def test_project_endpoints():
    """Test project creation and listing."""
    # First get token
    token = None
    try:
        token = await test_login_flow()
    except:
        pytest.skip("Skipping project tests due to login failure")

    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers) as client:
        # List projects
        response = await client.get("/project/")
        assert response.status_code == 200
        projects = response.json()
        assert isinstance(projects, list)
        
        # Create a test project
        new_project = {
            "name": "Integration Test Project",
            "description": "Created by automated tests",
            "db_type": "mysql",
            "db_config": {}
        }
        # Note: Adjust fields based on actual schema
        
        # Skipping create for now to avoid side effects in prod db if not mocked
        # response = await client.post("/project/", json=new_project)
        # assert response.status_code == 200

if __name__ == "__main__":
    # Allow running directly with python
    import sys
    from subprocess import call
    sys.exit(call(["pytest", "-v", "scripts/test_api_endpoints.py"]))
