"""
API Test Script for Authentication Endpoints

Tests all auth endpoints: signup, login, refresh, profile, change-password
Run with: python test_auth_api.py
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

# Test user credentials
TEST_EMAIL = f"testuser_{datetime.now().strftime('%H%M%S')}@example.com"
TEST_PASSWORD = "TestPassword123!"
TEST_NAME = "Test User"


def print_response(name: str, response: requests.Response):
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response: {json.dumps(data, indent=2)}")
    except:
        print(f"Response: {response.text[:500]}")
    return response


def test_health():
    """Test health endpoints."""
    print("\n" + "="*60)
    print("HEALTH CHECKS")
    print("="*60)
    
    # Root
    r = requests.get(f"{BASE_URL}/")
    print_response("Root Endpoint", r)
    
    # Health
    r = requests.get(f"{BASE_URL}/health")
    print_response("Health Check", r)
    
    # Ready
    r = requests.get(f"{BASE_URL}/ready")
    print_response("Readiness Check", r)
    
    return r.status_code == 200


def test_signup():
    """Test user registration."""
    print("\n" + "="*60)
    print("USER SIGNUP")
    print("="*60)
    
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": TEST_NAME
    }
    
    r = requests.post(f"{API_URL}/auth/signup", json=data)
    print_response("Signup", r)
    
    if r.status_code == 201:
        print("Signup successful!")
        return r.json()
    else:
        print("Signup failed!")
        return None


def test_login():
    """Test user login."""
    print("\n" + "="*60)
    print("USER LOGIN")
    print("="*60)
    
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    }
    
    r = requests.post(f"{API_URL}/auth/login", json=data)
    print_response("Login", r)
    
    if r.status_code == 200:
        print("Login successful!")
        return r.json()
    else:
        print("Login failed!")
        return None


def test_profile(access_token: str):
    """Test getting user profile."""
    print("\n" + "="*60)
    print("USER PROFILE")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    r = requests.get(f"{API_URL}/auth/me", headers=headers)
    print_response("Get Profile", r)
    
    if r.status_code == 200:
        print("Profile retrieved!")
        return r.json()
    else:
        print("Profile retrieval failed!")
        return None


def test_refresh_token(refresh_token: str):
    """Test token refresh."""
    print("\n" + "="*60)
    print("TOKEN REFRESH")
    print("="*60)
    
    data = {"refresh_token": refresh_token}
    
    r = requests.post(f"{API_URL}/auth/refresh", json=data)
    print_response("Refresh Token", r)
    
    if r.status_code == 200:
        print("Token refreshed!")
        return r.json()
    else:
        print("Token refresh failed!")
        return None


def test_change_password(access_token: str):
    """Test password change."""
    print("\n" + "="*60)
    print("CHANGE PASSWORD")
    print("="*60)
    
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {
        "current_password": TEST_PASSWORD,
        "new_password": "NewPassword456!"
    }
    
    r = requests.post(f"{API_URL}/auth/change-password", json=data, headers=headers)
    print_response("Change Password", r)
    
    if r.status_code == 200:
        print("Password changed!")
        return True
    else:
        print("Password change failed!")
        return False


def test_invalid_token():
    """Test with invalid token."""
    print("\n" + "="*60)
    print("INVALID TOKEN TEST")
    print("="*60)
    
    headers = {"Authorization": "Bearer invalid_token_here"}
    
    r = requests.get(f"{API_URL}/auth/me", headers=headers)
    print_response("Invalid Token", r)
    
    if r.status_code == 401:
        print("Correctly rejected invalid token!")
        return True
    else:
        print("Should have rejected invalid token!")
        return False


def test_duplicate_signup():
    """Test duplicate email registration."""
    print("\n" + "="*60)
    print("DUPLICATE SIGNUP TEST")
    print("="*60)
    
    data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": TEST_NAME
    }
    
    r = requests.post(f"{API_URL}/auth/signup", json=data)
    print_response("Duplicate Signup", r)
    
    if r.status_code == 400:
        print("Correctly rejected duplicate email!")
        return True
    else:
        print("Should have rejected duplicate email!")
        return False


def main():
    """Run all API tests."""
    print("\n" + "#"*60)
    print("#" + " "*20 + "AUTH API TESTS" + " "*24 + "#")
    print("#"*60)
    print(f"Testing against: {BASE_URL}")
    print(f"Test email: {TEST_EMAIL}")
    
    results = {
        "passed": 0,
        "failed": 0
    }
    
    # Test health
    if test_health():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test signup
    user = test_signup()
    if user:
        results["passed"] += 1
    else:
        results["failed"] += 1
        print("\nCannot continue without successful signup")
        return
    
    # Test duplicate signup
    if test_duplicate_signup():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test login
    tokens = test_login()
    if tokens:
        results["passed"] += 1
    else:
        results["failed"] += 1
        print("\nCannot continue without successful login")
        return
    
    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")
    
    # Test profile
    if test_profile(access_token):
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test invalid token
    if test_invalid_token():
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Test token refresh
    new_tokens = test_refresh_token(refresh_token)
    if new_tokens:
        results["passed"] += 1
        access_token = new_tokens.get("access_token")
    else:
        results["failed"] += 1
    
    # Test change password
    if test_change_password(access_token):
        results["passed"] += 1
    else:
        results["failed"] += 1
    
    # Summary
    print("\n" + "#"*60)
    print("#" + " "*20 + "TEST SUMMARY" + " "*26 + "#")
    print("#"*60)
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Total:  {results['passed'] + results['failed']}")
    
    if results["failed"] == 0:
        print("\nAll tests passed!")
    else:
        print(f"\n{results['failed']} test(s) failed")


if __name__ == "__main__":
    main()
