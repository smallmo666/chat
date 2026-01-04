import requests
import sys

BASE_URL = "http://localhost:8000"

def test_api():
    print(f"Testing API at {BASE_URL}...")
    
    # 1. Login
    login_data = {
        "username": "testuser",
        "password": "password123"
    }
    
    # Try to register first (in case user doesn't exist)
    try:
        reg_res = requests.post(f"{BASE_URL}/api/auth/register", json={
            "username": "testuser",
            "password": "password123",
            "email": "test@example.com"
        })
        print(f"Register status: {reg_res.status_code}")
    except Exception as e:
        print(f"Register failed (connection error): {e}")
        return

    # Login
    try:
        print("Attempting login...")
        # OAuth2 form data
        login_res = requests.post(f"{BASE_URL}/api/auth/login", data=login_data)
        
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.status_code} {login_res.text}")
            return
            
        token = login_res.json()["access_token"]
        print("Login successful. Got token.")
        
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Test Projects
        print("Testing GET /api/projects...")
        proj_res = requests.get(f"{BASE_URL}/api/projects", headers=headers)
        print(f"Projects status: {proj_res.status_code}")
        if proj_res.status_code == 200:
            print(f"Projects data: {proj_res.json()}")
        else:
            print(f"Projects error: {proj_res.text}")

        # 3. Test DataSources
        print("Testing GET /api/datasources...")
        ds_res = requests.get(f"{BASE_URL}/api/datasources", headers=headers)
        print(f"DataSources status: {ds_res.status_code}")
        if ds_res.status_code == 200:
            print(f"DataSources data: {ds_res.json()}")
        else:
            print(f"DataSources error: {ds_res.text}")
            
    except Exception as e:
        print(f"API Test failed with exception: {e}")

if __name__ == "__main__":
    test_api()
