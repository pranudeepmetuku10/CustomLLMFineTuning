"""
Test script for the Data Pipeline API

Tests dataset upload, processing, bias detection, and retrieval.
Uses existing test files: python.zip and code_dataset.json

Run with: python -m tests.test_data_api
Or: cd tests && python test_data_api.py
"""

import requests
import json
import os
from pathlib import Path
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
API_URL = f"{BASE_URL}/api"

# Test user credentials
TEST_EMAIL = f"datatest_{datetime.now().strftime('%H%M%S')}@example.com"
TEST_PASSWORD = "TestPassword123!"

# Test file paths (relative to this script)
SCRIPT_DIR = Path(__file__).parent
ZIP_PATH = SCRIPT_DIR / "python.zip"
JSON_PATH = SCRIPT_DIR / "code_dataset.json"


def print_response(name: str, response: requests.Response):
    """Pretty print API response."""
    print(f"\n{'='*60}")
    print(f"{name}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        # Truncate long responses
        text = json.dumps(data, indent=2)
        if len(text) > 2000:
            print(f"Response (truncated): {text[:2000]}...")
        else:
            print(f"Response: {text}")
    except:
        print(f"Response: {response.text[:500]}")
    return response


def main():
    print("\n" + "#"*60)
    print("#" + " "*18 + "DATA PIPELINE TESTS" + " "*19 + "#")
    print("#"*60)
    
    # Verify test files exist
    print(f"\nTest files:")
    print(f"  ZIP:  {ZIP_PATH} (exists: {ZIP_PATH.exists()})")
    print(f"  JSON: {JSON_PATH} (exists: {JSON_PATH.exists()})")
    
    if not ZIP_PATH.exists():
        print(f"\nERROR: ZIP file not found at {ZIP_PATH}")
        return
    if not JSON_PATH.exists():
        print(f"\nERROR: JSON file not found at {JSON_PATH}")
        return
    
    # Step 1: Create test user and login
    print("\n[Step 1] Creating test user and logging in...")
    
    signup_data = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "full_name": "Data Test User"
    }
    r = requests.post(f"{API_URL}/auth/signup", json=signup_data)
    if r.status_code != 201:
        print(f"Signup failed: {r.text}")
        return
    
    login_data = {"email": TEST_EMAIL, "password": TEST_PASSWORD}
    r = requests.post(f"{API_URL}/auth/login", json=login_data)
    if r.status_code != 200:
        print(f"Login failed: {r.text}")
        return
    
    tokens = r.json()
    access_token = tokens["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}
    print(f"Logged in as: {TEST_EMAIL}")
    
    # Step 2: Upload ZIP dataset (python.zip)
    print(f"\n[Step 2] Uploading ZIP dataset ({ZIP_PATH.name})...")
    print(f"  File size: {ZIP_PATH.stat().st_size / 1024:.1f} KB")
    
    with open(ZIP_PATH, 'rb') as f:
        files = {"file": (ZIP_PATH.name, f, "application/zip")}
        data = {"name": "Python Code Dataset", "description": "Python code files from tests folder"}
        r = requests.post(f"{API_URL}/datasets/upload", files=files, data=data, headers=headers)
    
    print_response("Upload ZIP Dataset", r)
    
    if r.status_code == 200:
        zip_dataset_id = r.json()["dataset_id"]
        print(f"\nDataset ID: {zip_dataset_id}")
    else:
        zip_dataset_id = None
        print("ZIP upload failed, continuing with JSON...")
    
    # Step 3: Upload JSON dataset (code_dataset.json)
    print(f"\n[Step 3] Uploading JSON dataset ({JSON_PATH.name})...")
    print(f"  File size: {JSON_PATH.stat().st_size / 1024:.1f} KB")
    
    with open(JSON_PATH, 'rb') as f:
        files = {"file": (JSON_PATH.name, f, "application/json")}
        data = {"name": "Code Snippets Dataset", "description": "Code snippets from JSON file"}
        r = requests.post(f"{API_URL}/datasets/upload", files=files, data=data, headers=headers)
    
    print_response("Upload JSON Dataset", r)
    
    if r.status_code == 200:
        json_dataset_id = r.json()["dataset_id"]
        print(f"\nDataset ID: {json_dataset_id}")
    else:
        json_dataset_id = None
    
    # Step 4: List datasets
    print("\n[Step 4] Listing datasets...")
    r = requests.get(f"{API_URL}/datasets/", headers=headers)
    print_response("List Datasets", r)
    
    # Step 5: Get dataset details
    target_dataset_id = zip_dataset_id or json_dataset_id
    if target_dataset_id:
        print(f"\n[Step 5] Getting dataset details for {target_dataset_id[:8]}...")
        r = requests.get(f"{API_URL}/datasets/{target_dataset_id}", headers=headers)
        print_response("Get Dataset Details", r)
    
    # Step 6: Get BIAS REPORT (Full)
    if target_dataset_id:
        print(f"\n[Step 6] Getting BIAS REPORT (Full)...")
        r = requests.get(f"{API_URL}/datasets/{target_dataset_id}/bias", headers=headers)
        print_response("Bias Report (Full)", r)
        
        if r.status_code == 200:
            bias = r.json()
            print(f"\n  *** BIAS ANALYSIS SUMMARY ***")
            print(f"  Overall Bias Score: {bias['overall_bias_score']:.3f}")
            print(f"  Severity Level: {bias['overall_severity'].upper()}")
            print(f"  Total Samples Analyzed: {bias['total_samples']}")
            
            # Language bias details
            if bias.get('language_bias'):
                lang_bias = bias['language_bias']
                print(f"\n  Language Distribution:")
                for lang, pct in lang_bias['percentages'].items():
                    print(f"    - {lang}: {pct:.1f}%")
                print(f"  Language Imbalance: {lang_bias['imbalance_score']:.3f} ({lang_bias['severity']})")
            
            # Recommendations
            if bias.get('recommendations'):
                print(f"\n  Recommendations:")
                for rec in bias['recommendations']:
                    print(f"    - {rec}")
    
    # Step 7: Get BIAS SUMMARY (Brief)
    if target_dataset_id:
        print(f"\n[Step 7] Getting BIAS SUMMARY (Brief)...")
        r = requests.get(f"{API_URL}/datasets/{target_dataset_id}/bias/summary", headers=headers)
        print_response("Bias Summary", r)
    
    # Step 8: Delete one dataset (if both exist, delete JSON)
    if json_dataset_id and zip_dataset_id:
        print(f"\n[Step 8] Deleting JSON dataset...")
        r = requests.delete(f"{API_URL}/datasets/{json_dataset_id}", headers=headers)
        print_response("Delete Dataset", r)
    
    # Step 9: Verify deletion
    print("\n[Step 9] Final dataset list...")
    r = requests.get(f"{API_URL}/datasets/", headers=headers)
    print_response("List Datasets After Delete", r)
    
    # Summary
    print("\n" + "#"*60)
    print("#" + " "*20 + "TEST COMPLETE" + " "*25 + "#")
    print("#"*60)
    
    if r.status_code == 200:
        datasets = r.json().get("datasets", [])
        print(f"\nDatasets remaining: {len(datasets)}")
        for d in datasets:
            print(f"  - {d['name']} (ID: {d['id'][:8]}..., Samples: {d.get('num_samples', 'N/A')})")


if __name__ == "__main__":
    main()

